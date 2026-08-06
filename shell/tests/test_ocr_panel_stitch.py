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
