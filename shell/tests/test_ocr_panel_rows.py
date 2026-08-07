from shell.app.ocr.panel.tokens import tokens_from_json
from shell.app.ocr.panel.rows import assemble_rows

def _tok(text, x0, y0, w=0.2, h=0.03, conf=0.98, color=None):
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + w, "y1": y0 + h, "conf": conf, "color": color}

def test_single_column_rows_pair_label_and_value():
    toks = tokens_from_json([
        _tok("Troops' Attack", 0.05, 0.10), _tok("748.49%", 0.70, 0.101),
        _tok("Infantry Attack", 0.05, 0.16), _tok("658.25%", 0.70, 0.161),
    ])
    rows, warnings = assemble_rows(toks, two_column=False)
    got = {r.canonical: r.value for r in rows}
    assert got == {"Troops|Attack": 748.49, "Infantry|Attack": 658.25}
    assert all(r.side is None for r in rows)
    assert warnings == []

def test_two_column_battle_row_sides_by_geometry_and_color():
    toks = tokens_from_json([
        _tok("+4859.0%", 0.03, 0.20, color="green"), _tok("Infantry Attack", 0.38, 0.201),
        _tok("+694.3%", 0.78, 0.202, color="red"),
    ])
    rows, _ = assemble_rows(toks, two_column=True)
    sides = {(r.canonical, r.side): r.value for r in rows}
    assert sides[("Infantry|Attack", "left")] == 4859.0
    assert sides[("Infantry|Attack", "right")] == 694.3

def test_color_beats_geometry_with_conflict_flag():
    toks = tokens_from_json([
        _tok("Infantry Attack", 0.38, 0.20),
        _tok("+694.3%", 0.05, 0.201, color="red"),  # red but geometrically left
    ])
    rows, _ = assemble_rows(toks, two_column=True)
    (r,) = rows
    assert r.side == "right" and "col_conflict" in r.flags

def test_low_conf_and_missing_value_flags():
    toks = tokens_from_json([
        _tok("Infantry Health", 0.05, 0.30), _tok("3197.4%", 0.70, 0.301, conf=0.55),
        _tok("Lancer Health", 0.05, 0.36),
    ])
    assembled, _ = assemble_rows(toks, two_column=False)
    rows = {r.canonical: r for r in assembled}
    assert "low_conf" in rows["Infantry|Health"].flags
    assert rows["Lancer|Health"].value is None and "missing_value" in rows["Lancer|Health"].flags

def test_qa_defect_001_drifted_value_is_orphaned_not_misattributed():
    # QA probe: the value drifts ~half a row and joins the PREVIOUS label's
    # group. It may not be emitted under either label — both keep missing_value
    # and the stray number is reported as an orphan warning.
    toks = tokens_from_json([
        _tok("Infantry Attack", 0.05, 0.100),    # label band .100-.130 (centre .115)
        _tok("Infantry Defense", 0.05, 0.150),   # label band .150-.180 (centre .165)
        _tok("3979.1%", 0.70, 0.115),            # value centre .130 — between the rows
    ])
    rows, warnings = assemble_rows(toks, two_column=False)
    by_canon = {r.canonical: r for r in rows}
    for key in ("Infantry|Attack", "Infantry|Defense"):
        assert by_canon[key].value is None, key
        assert "missing_value" in by_canon[key].flags, key
    assert warnings == ["orphan value near y=0.130"]

def test_qa_defect_001_in_band_value_still_pairs():
    # Guardrail for the fix: normal jitter (well inside 0.35 * median height)
    # must keep pairing exactly as before.
    toks = tokens_from_json([
        _tok("Infantry Attack", 0.05, 0.100), _tok("4491.6%", 0.70, 0.108),
    ])
    rows, warnings = assemble_rows(toks, two_column=False)
    assert [(r.canonical, r.value) for r in rows] == [("Infantry|Attack", 4491.6)]
    assert warnings == []
