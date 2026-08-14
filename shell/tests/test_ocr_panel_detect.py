from shell.app.ocr.panel.rows import PanelRow
from shell.app.ocr.panel.detect import detect_panel_type

def _r(c, side=None, v=100.0):
    return PanelRow(c, side, v, "pct", 0.99, c, ())

def test_detects_citystats_by_troops_rows():
    assert detect_panel_type([_r("Troops|Attack"), _r("Infantry|Attack")]) == "citystats"

def test_detects_battle_by_two_sides():
    rows = [_r("Infantry|Attack", "left"), _r("Infantry|Attack", "right"),
            _r("Infantry|Defense", "left"), _r("Infantry|Defense", "right"),
            _r("Lancer|Attack", "left"), _r("Lancer|Attack", "right"),
            _r("Lancer|Defense", "left"), _r("Lancer|Defense", "right")]
    assert detect_panel_type(rows) == "battle"

def test_detects_scout_single_sided():
    rows = [_r(f"{c}|{s}") for c in ("Infantry", "Lancer") for s in ("Attack", "Defense", "Lethality")]
    assert detect_panel_type(rows) == "scout"

def test_unknown_for_garbage():
    assert detect_panel_type([]) == "unknown"
