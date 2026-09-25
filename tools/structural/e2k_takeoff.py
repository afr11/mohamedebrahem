"""Concrete quantity takeoff from an ETABS text model (.e2k / .$et).

Reads stories, sections, points, lines and areas from the exported text file
and estimates concrete volume per story and element type (columns, beams,
slabs, walls). Quantities are gross: beam/slab and column/beam overlaps are
not deducted. Units follow the model's length unit (see the UNITS line).

Usage:
    python tools/structural/e2k_takeoff.py model.e2k [-o takeoff.xlsx]
"""

import argparse
import math
import shlex
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Model:
    units: str = ""
    story_order: list = field(default_factory=list)  # top to bottom
    story_elev: dict = field(default_factory=dict)
    points: dict = field(default_factory=dict)  # label -> (x, y)
    frame_sections: dict = field(default_factory=dict)  # name -> area
    shell_thickness: dict = field(default_factory=dict)
    lines: dict = field(default_factory=dict)  # label -> (type, i, j, n)
    areas: dict = field(default_factory=dict)  # label -> (type, pts, offs)
    line_assigns: list = field(default_factory=list)  # (label, story, sec)
    area_assigns: list = field(default_factory=list)


def _kv(tokens):
    """Turn [KEY, value, KEY, value, ...] into a dict (upper-case keys)."""
    return {tokens[i].upper(): tokens[i + 1] for i in range(0, len(tokens) - 1, 2)}


def _section_area(kv):
    shape = kv.get("SHAPE", "").lower()
    d = float(kv.get("D", 0))
    b = float(kv.get("B", 0))
    if "circle" in shape or "circular" in shape:
        return math.pi * d * d / 4
    return d * b


def parse_e2k(text):
    m = Model()
    stories = []  # (name, height or None, elev or None), top to bottom
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("$"):
            continue
        try:
            t = shlex.split(line)
        except ValueError:
            continue
        key = t[0].upper()

        if key == "UNITS" and len(t) >= 3:
            m.units = f"{t[1]}, {t[2]}"
        elif key == "STORY":
            kv = _kv(t[2:])
            height = float(kv["HEIGHT"]) if "HEIGHT" in kv else None
            elev = float(kv["ELEV"]) if "ELEV" in kv else None
            stories.append((t[1], height, elev))
        elif key == "POINT" and len(t) >= 4:
            m.points[t[1]] = (float(t[2]), float(t[3]))
        elif key == "FRAMESECTION":
            m.frame_sections[t[1]] = _section_area(_kv(t[2:]))
        elif key in ("SHELLPROP", "SLAB", "WALL", "DECK"):
            kv = _kv(t[2:])
            for k, v in kv.items():
                if k.endswith("THICKNESS"):
                    m.shell_thickness[t[1]] = float(v)
                    break
        elif key == "LINE" and len(t) >= 6:
            m.lines[t[1]] = (t[2].upper(), t[3], t[4], int(t[5]))
        elif key == "AREA" and len(t) >= 4:
            n = int(t[3])
            pts = t[4:4 + n]
            offs = [int(x) for x in t[4 + n:4 + 2 * n]]
            m.areas[t[1]] = (t[2].upper(), pts, offs)
        elif key == "LINEASSIGN" and len(t) >= 3:
            sec = _kv(t[3:]).get("SECTION")
            if sec:
                m.line_assigns.append((t[1], t[2], sec))
        elif key == "AREAASSIGN" and len(t) >= 3:
            sec = _kv(t[3:]).get("SECTION")
            if sec:
                m.area_assigns.append((t[1], t[2], sec))

    # Resolve story elevations from the bottom (story with ELEV) upward.
    elev = 0.0
    for name, height, base_elev in reversed(stories):
        if base_elev is not None:
            elev = base_elev
        else:
            elev += height or 0.0
        m.story_elev[name] = elev
    m.story_order = [s[0] for s in stories]
    return m


def _story_below(m, story, n):
    idx = m.story_order.index(story) + n
    return m.story_order[min(idx, len(m.story_order) - 1)]


def _dist(m, a, b):
    (x1, y1), (x2, y2) = m.points[a], m.points[b]
    return math.hypot(x2 - x1, y2 - y1)


def _polygon_area(coords):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:] + coords[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def takeoff(m):
    """Return rows of (story, element, count, quantity, volume)."""
    acc = defaultdict(lambda: [0, 0.0, 0.0])  # count, length/area, volume

    for label, story, sec in m.line_assigns:
        if label not in m.lines or sec not in m.frame_sections:
            continue
        kind, i, j, n = m.lines[label]
        if kind == "COLUMN":
            length = m.story_elev[story] - m.story_elev[_story_below(m, story, n)]
            element = "Columns"
        elif kind == "BEAM":
            length = _dist(m, i, j)
            element = "Beams"
        else:
            continue
        r = acc[(story, element)]
        r[0] += 1
        r[1] += length
        r[2] += length * m.frame_sections[sec]

    for label, story, sec in m.area_assigns:
        if label not in m.areas or sec not in m.shell_thickness:
            continue
        kind, pts, offs = m.areas[label]
        thk = m.shell_thickness[sec]
        if kind == "FLOOR":
            area = _polygon_area([m.points[p] for p in pts])
            element = "Slabs"
        elif kind == "PANEL":
            # Wall panel: two top points (offset 0) and two bottom points.
            top = [p for p, o in zip(pts, offs) if o == 0]
            n = max(offs) or 1
            height = m.story_elev[story] - m.story_elev[_story_below(m, story, n)]
            area = _dist(m, top[0], top[1]) * height if len(top) >= 2 else 0.0
            element = "Walls"
        else:
            continue
        r = acc[(story, element)]
        r[0] += 1
        r[1] += area
        r[2] += area * thk

    order = {s: k for k, s in enumerate(m.story_order)}
    return [
        (story, element, c, q, v)
        for (story, element), (c, q, v) in sorted(
            acc.items(), key=lambda kv: (order.get(kv[0][0], 0), kv[0][1])
        )
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("e2k", help="ETABS .e2k / .$et text file")
    ap.add_argument("-o", "--output", help="write results to .xlsx or .csv")
    args = ap.parse_args()

    with open(args.e2k, encoding="utf-8", errors="replace") as f:
        model = parse_e2k(f.read())
    rows = takeoff(model)

    print(f"Units: {model.units or 'unknown'}")
    print(f"{'Story':<12}{'Element':<10}{'Count':>6}{'Len/Area':>12}{'Volume':>12}")
    total = 0.0
    for story, element, count, qty, vol in rows:
        print(f"{story:<12}{element:<10}{count:>6}{qty:>12.2f}{vol:>12.3f}")
        total += vol
    print(f"{'TOTAL CONCRETE VOLUME':<40}{total:>12.3f}")

    if args.output:
        import pandas as pd

        df = pd.DataFrame(
            rows, columns=["Story", "Element", "Count", "Length/Area", "Volume"]
        )
        if args.output.lower().endswith(".csv"):
            df.to_csv(args.output, index=False)
        else:
            df.to_excel(args.output, index=False)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
