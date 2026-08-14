from shell.app.ocr.panel.rows import PanelRow
from shell.app.ocr.panel.stitch import stitch

def _r(c, v, conf=0.98, side=None, flags=()):
    return PanelRow(c, side, v, "pct", conf, c, tuple(flags))

def test_overlap_dedup_keeps_higher_conf():
    a = [_r("Infantry|Attack", 4491.6, 0.95), _r("Infantry|Defense", 3979.1, 0.97)]
    b = [_r("Infantry|Defense", 3979.1, 0.99), _r("Infantry|Lethality", 2794.3, 0.98)]
    merged, warns = stitch([a, b])
    got = {r.canonical: (r.value, r.conf) for r in merged}
    assert got["Infantry|Defense"] == (3979.1, 0.99) and len(merged) == 3 and warns == []

def test_conflicting_duplicate_never_guesses():
    merged, warns = stitch([[_r("Infantry|Attack", 4491.6)], [_r("Infantry|Attack", 4431.6)]])
    (r,) = merged
    assert r.value is None and "conflict" in r.flags and len(warns) == 1

def test_qa_defect_003_conflict_is_sticky_across_further_shots():
    # QA probe: 4491.6 / 4431.6 / 1111.1 — a third screenshot must NOT erase an
    # already-detected conflict, in any order.
    shots = [[_r("Infantry|Attack", 4491.6)], [_r("Infantry|Attack", 4431.6)],
             [_r("Infantry|Attack", 1111.1)]]
    for order in ((0, 1, 2), (2, 0, 1), (1, 2, 0), (2, 1, 0)):
        merged, warns = stitch([shots[i] for i in order])
        (r,) = merged
        assert r.value is None, order
        assert "conflict" in r.flags, order
        assert len(warns) == 1, (order, warns)

def test_qa_defect_003_conflicted_row_survives_a_higher_conf_repeat():
    merged, warns = stitch([[_r("Infantry|Attack", 4491.6, 0.91)],
                            [_r("Infantry|Attack", 4431.6, 0.92)],
                            [_r("Infantry|Attack", 4431.6, 0.99)]])
    (r,) = merged
    assert r.value is None and "conflict" in r.flags and len(warns) == 1
