# mohamedebrahem

Structural engineering website and toolkit. The owner writes in Egyptian Arabic;
reply in Arabic unless asked otherwise.

## Setup
`.claude/hooks/session-start.sh` installs `requirements.txt` in web sessions
(pandas, openpyxl, ezdxf, matplotlib, pypdf, python-docx, yfinance, pytest).

## Tools
- `tools/structural/e2k_takeoff.py` — concrete quantity takeoff (الحصر) from an
  ETABS text export (`File > Export > ETABS .e2k Text File`). Gross volumes per
  story for columns, beams, slabs and walls; `-o file.xlsx` saves to Excel.
- ETABS `.EDB` and SAFE `.FDB` files are binary and cannot be read directly.
  Ask for the `.e2k` export, or for Excel tables exported via
  `File > Export > Database Tables to Excel` (read those with pandas).
- AutoCAD drawings: read/write `.dxf` with `ezdxf` (`.dwg` must be saved as DXF first).

## Checks
    python -m pytest -q
