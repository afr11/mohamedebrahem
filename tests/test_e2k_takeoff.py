from pathlib import Path

import pytest

from tools.structural.e2k_takeoff import parse_e2k, takeoff

SAMPLE = Path(__file__).parent.parent / "tools/structural/samples/two_story.e2k"


def test_two_story_sample():
    model = parse_e2k(SAMPLE.read_text())
    assert model.units == "KN, M"
    assert model.story_elev == {"Story2": 6.0, "Story1": 3.0, "Base": 0.0}

    vols = {(s, e): v for s, e, _, _, v in takeoff(model)}
    for story in ("Story1", "Story2"):
        assert vols[(story, "Columns")] == pytest.approx(4 * 3 * 0.25)
        assert vols[(story, "Beams")] == pytest.approx(22 * 0.18)
        assert vols[(story, "Slabs")] == pytest.approx(30 * 0.2)
        assert vols[(story, "Walls")] == pytest.approx(6 * 3 * 0.25)
