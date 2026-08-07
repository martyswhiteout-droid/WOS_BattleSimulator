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

def test_qa_defect_001_drifted_value_never_lands_under_wrong_label():
    r = extract_panel([_drift_shot()], side_hint=None, panel_hint=None)
    assert r["stats"] == {}
    assert "stats.Infantry|Attack" in r["unreadable_fields"]
    assert "stats.Infantry|Defense" in r["unreadable_fields"]
    assert r["warnings"] == ["orphan value near y=0.130"]
    assert r["status"] == "failed"
