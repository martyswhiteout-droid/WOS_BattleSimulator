import json
from shell.app.ocr.panel.service import extract_panel

def _shot_scout():
    toks, y = [], 0.10
    for cls in ("Infantry", "Lancer", "Marksman"):
        for st, v in (("Attack", "+4491.6%"), ("Defense", "+3979.1%"), ("Lethality", "+2794.3%"), ("Health", "+3197.4%")):
            toks.append({"text": f"{cls} {st}", "x0": 0.05, "y0": y, "x1": 0.4, "y1": y + 0.03, "conf": 0.99})
            toks.append({"text": v, "x0": 0.7, "y0": y, "x1": 0.95, "y1": y + 0.03, "conf": 0.97})
            y += 0.05
    return toks

def test_scout_extraction_ok_and_deterministic():
    r1 = extract_panel([_shot_scout()], side_hint="enemy", panel_hint=None)
    r2 = extract_panel([_shot_scout()], side_hint="enemy", panel_hint=None)
    assert r1["status"] == "ok" and r1["panel_type"] == "scout"
    assert r1["stats"]["Infantry|Attack"] == 4491.6 and len(r1["stats"]) == 12
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

def test_low_conf_field_is_unreadable_not_guessed():
    shot = _shot_scout()
    shot[1]["conf"] = 0.55   # Infantry Attack value token
    r = extract_panel([shot], side_hint="enemy", panel_hint=None)
    assert r["status"] == "partial"
    assert "Infantry|Attack" not in r["stats"]
    assert "stats.Infantry|Attack" in r["unreadable_fields"]

def test_empty_input_fails_cleanly():
    r = extract_panel([[]], side_hint=None, panel_hint=None)
    assert r["status"] == "failed" and r["stats"] == {}

def _drift_shot():
    # QA D-001 probe: label rows at .100-.130 and .150-.180, one value centred
    # at .130 (drifted half a row out of its own row band).
    return [
        {"text": "Infantry Attack", "x0": 0.05, "y0": 0.100, "x1": 0.40, "y1": 0.130, "conf": 0.99},
        {"text": "Infantry Defense", "x0": 0.05, "y0": 0.150, "x1": 0.40, "y1": 0.180, "conf": 0.99},
        {"text": "3979.1%", "x0": 0.70, "y0": 0.115, "x1": 0.95, "y1": 0.145, "conf": 0.99},
    ]

CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")

def _tok(text, x0, y0, x1, y1, conf=0.99, color=None):
    t = {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "conf": conf}
    if color is not None:
        t["color"] = color
    return t

def _shot_battle(right_rows=None):
    """Two-column battle shot. ``right_rows`` limits which rows carry a right
    value (None = all 12)."""
    toks, y = [], 0.10
    for cls in CLASSES:
        for st in STATS:
            key = f"{cls}|{st}"
            toks.append(_tok(f"{cls} {st}", 0.38, y, 0.58, y + 0.03))
            toks.append(_tok("+4859.0%", 0.03, y, 0.23, y + 0.03, color="green"))
            if right_rows is None or key in right_rows:
                toks.append(_tok("+694.3%", 0.70, y, 0.90, y + 0.03, color="red"))
            y += 0.05
    return toks

def test_qa_defect_002_col_conflict_is_never_silently_attributed():
    # QA probe: colour contradicts geometry on every row — the values may not be
    # attributed to either column.
    toks, y = [], 0.10
    for cls in CLASSES:
        for st in STATS:
            toks.append(_tok(f"{cls} {st}", 0.38, y, 0.58, y + 0.03))
            toks.append(_tok("+4859.0%", 0.03, y, 0.23, y + 0.03, color="red"))
            toks.append(_tok("+694.3%", 0.70, y, 0.90, y + 0.03, color="green"))
            y += 0.05
    r = extract_panel([toks], side_hint="you", panel_hint=None)
    assert r["panel_type"] == "battle"
    assert r["stats_left"] == {} and r["stats_right"] == {}
    assert r["status"] == "failed"
    for cls in CLASSES:
        for st in STATS:
            assert f"stats_left.{cls}|{st}" in r["unreadable_fields"]
            assert f"stats_right.{cls}|{st}" in r["unreadable_fields"]

def test_qa_defect_003_third_shot_cannot_erase_a_conflict():
    def shot(value):
        return [_tok("Infantry Attack", 0.05, 0.10, 0.40, 0.13),
                _tok(value, 0.70, 0.10, 0.95, 0.13)]
    r = extract_panel([shot("4491.6%"), shot("4431.6%"), shot("1111.1%")],
                      side_hint=None, panel_hint=None)
    assert "Infantry|Attack" not in r["stats"]
    assert "stats.Infantry|Attack" in r["unreadable_fields"]
    assert len(r["warnings"]) == 1

def test_qa_defect_004_low_conf_special_is_unreadable_not_folded():
    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83, conf=0.05))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == []
    assert "specials.Attack Bonus (Pet Skill)" in r["unreadable_fields"]

def test_qa_defect_004_valueless_special_is_unreadable():
    shot = _shot_scout()
    shot.append(_tok("Defense Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == []
    assert "specials.Defense Bonus (Pet Skill)" in r["unreadable_fields"]

def test_qa_defect_006_never_seen_scout_fields_are_listed_unreadable():
    shot = [t for t in _shot_scout() if not t["text"].startswith("Marksman")]
    r = extract_panel([shot], side_hint="enemy", panel_hint=None)
    assert r["status"] == "partial"
    for st in STATS:
        assert f"stats.Marksman|{st}" in r["unreadable_fields"]

def test_qa_defect_006_missing_battle_column_fields_are_listed_unreadable():
    seen = {f"Infantry|{st}" for st in STATS}
    r = extract_panel([_shot_battle(right_rows=seen)], side_hint="you", panel_hint=None)
    assert r["panel_type"] == "battle" and r["status"] == "partial"
    assert len(r["stats_right"]) == 4
    for cls in ("Lancer", "Marksman"):
        for st in STATS:
            assert f"stats_right.{cls}|{st}" in r["unreadable_fields"]
    assert not any(f.startswith("stats_left.") for f in r["unreadable_fields"])

def test_qa_defect_001_drifted_value_never_lands_under_wrong_label():
    r = extract_panel([_drift_shot()], side_hint=None, panel_hint=None)
    assert r["stats"] == {}
    assert "stats.Infantry|Attack" in r["unreadable_fields"]
    assert "stats.Infantry|Defense" in r["unreadable_fields"]
    assert r["warnings"] == ["orphan value near y=0.130"]
    assert r["status"] == "failed"
