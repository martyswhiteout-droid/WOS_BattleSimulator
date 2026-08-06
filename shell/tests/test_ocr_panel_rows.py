from shell.app.ocr.panel.tokens import tokens_from_json
from shell.app.ocr.panel.rows import assemble_rows

def _tok(text, x0, y0, w=0.2, h=0.03, conf=0.98, color=None):
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + w, "y1": y0 + h, "conf": conf, "color": color}

def test_single_column_rows_pair_label_and_value():
    toks = tokens_from_json([
        _tok("Troops' Attack", 0.05, 0.10), _tok("748.49%", 0.70, 0.101),
        _tok("Infantry Attack", 0.05, 0.16), _tok("658.25%", 0.70, 0.161),
    ])
    rows = assemble_rows(toks, two_column=False)
    got = {r.canonical: r.value for r in rows}
    assert got == {"Troops|Attack": 748.49, "Infantry|Attack": 658.25}
    assert all(r.side is None for r in rows)

def test_two_column_battle_row_sides_by_geometry_and_color():
    toks = tokens_from_json([
        _tok("+4859.0%", 0.03, 0.20, color="green"), _tok("Infantry Attack", 0.38, 0.201),
        _tok("+694.3%", 0.78, 0.202, color="red"),
    ])
    rows = assemble_rows(toks, two_column=True)
    sides = {(r.canonical, r.side): r.value for r in rows}
    assert sides[("Infantry|Attack", "left")] == 4859.0
    assert sides[("Infantry|Attack", "right")] == 694.3

def test_color_beats_geometry_with_conflict_flag():
    toks = tokens_from_json([
        _tok("Infantry Attack", 0.38, 0.20),
        _tok("+694.3%", 0.05, 0.201, color="red"),  # red but geometrically left
    ])
    rows = assemble_rows(toks, two_column=True)
    (r,) = rows
    assert r.side == "right" and "col_conflict" in r.flags

def test_low_conf_and_missing_value_flags():
    toks = tokens_from_json([
        _tok("Infantry Health", 0.05, 0.30), _tok("3197.4%", 0.70, 0.301, conf=0.55),
        _tok("Lancer Health", 0.05, 0.36),
    ])
    rows = {r.canonical: r for r in assemble_rows(toks, two_column=False)}
    assert "low_conf" in rows["Infantry|Health"].flags
    assert rows["Lancer|Health"].value is None and "missing_value" in rows["Lancer|Health"].flags
