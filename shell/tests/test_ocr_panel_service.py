import json
import pytest
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
    # QA probe: colour contradicts geometry on every row â€” the values may not be
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

def test_qa_defect_005_service_reports_whether_specials_were_observed():
    clean = extract_panel([_shot_scout()], side_hint="you", panel_hint=None)
    assert clean["specials_observed"] == "none"

    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83, conf=0.05))
    seen = extract_panel([shot], side_hint="you", panel_hint=None)
    # Row was seen but rejected: specials stay empty and the state says so.
    assert seen["specials"] == [] and seen["specials_observed"] == "partial"

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

def test_qa_defect_011_requested_side_is_echoed_and_aliased_both_ways():
    # Left column belongs to the report viewer: side=you => you is the LEFT
    # column; side=enemy => the uploader is looking at the enemy's report, so
    # you is the RIGHT column.
    you = extract_panel([_shot_battle()], side_hint="you", panel_hint=None)
    assert you["requested_side"] == "you"
    assert you["stats_you"] == you["stats_left"] and you["stats_enemy"] == you["stats_right"]
    assert you["stats_you_conf"] == you["stats_left_conf"]
    assert you["stats_enemy_conf"] == you["stats_right_conf"]

    enemy = extract_panel([_shot_battle()], side_hint="enemy", panel_hint=None)
    assert enemy["requested_side"] == "enemy"
    assert enemy["stats_you"] == enemy["stats_right"] and enemy["stats_enemy"] == enemy["stats_left"]
    assert enemy["stats_you_conf"] == enemy["stats_right_conf"]

def test_qa_defect_011_single_sided_panel_has_no_side_aliases():
    r = extract_panel([_shot_scout()], side_hint="you", panel_hint=None)
    assert r["requested_side"] == "you"
    assert "stats_you" not in r and "stats_enemy" not in r

def test_qa_defect_012_contradicting_panel_hint_fails_closed():
    r = extract_panel([_shot_scout()], side_hint="you", panel_hint="citystats")
    assert r["status"] == "failed"
    assert r["stats"] == {}
    assert "stats_left" not in r and "stats_right" not in r
    assert "panel hint citystats contradicts detected scout" in r["warnings"]

def test_qa_defect_012_agreeing_hint_is_accepted():
    r = extract_panel([_shot_scout()], side_hint="enemy", panel_hint="scout")
    assert r["status"] == "ok" and r["panel_type"] == "scout"

def test_qa_defect_012_hint_still_applies_when_detection_is_unknown():
    shot = [_tok("Infantry Attack", 0.05, 0.10, 0.40, 0.13),
            _tok("+4491.6%", 0.70, 0.10, 0.95, 0.13),
            _tok("Infantry Defense", 0.05, 0.16, 0.40, 0.19),
            _tok("+3979.1%", 0.70, 0.16, 0.95, 0.19)]
    r = extract_panel([shot], side_hint="you", panel_hint="scout")
    assert r["panel_type"] == "scout" and r["status"] == "partial"
    assert r["stats"]["Infantry|Attack"] == 4491.6

def test_qa_defect_018_battle_response_omits_the_empty_stats_key():
    r = extract_panel([_shot_battle()], side_hint="you", panel_hint=None)
    assert "stats" not in r
    assert "stats_left" in r and "stats_right" in r

def test_qa_defect_008_out_of_range_class_values_are_unreadable():
    # QA probe: -4491.6% and 999999999% used to come back status=ok.
    shot = _shot_scout()
    shot[1]["text"] = "-4491.6%"    # Infantry Attack value
    shot[3]["text"] = "999999999%"  # Infantry Defense value
    r = extract_panel([shot], side_hint="enemy", panel_hint=None)
    assert "Infantry|Attack" not in r["stats"] and "Infantry|Defense" not in r["stats"]
    assert "stats.Infantry|Attack" in r["unreadable_fields"]
    assert "stats.Infantry|Defense" in r["unreadable_fields"]
    assert r["status"] == "partial"

def test_qa_defect_008_range_endpoints_stay_readable():
    shot = _shot_scout()
    shot[1]["text"] = "0.0%"
    shot[3]["text"] = "6000.0%"
    r = extract_panel([shot], side_hint="enemy", panel_hint=None)
    assert r["stats"]["Infantry|Attack"] == 0.0
    assert r["stats"]["Infantry|Defense"] == 6000.0
    assert r["status"] == "ok"

def test_qa_defect_008_implausible_special_is_unreadable():
    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+250.0%", 0.70, 0.80, 0.95, 0.83))
    shot.append(_tok("Defense Bonus (Pet Skill)", 0.05, 0.86, 0.40, 0.89))
    shot.append(_tok("+10.0%", 0.70, 0.86, 0.95, 0.89))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": "Defense Bonus (Pet Skill)", "value": 10.0, "side": None}]
    assert "specials.Attack Bonus (Pet Skill)" in r["unreadable_fields"]

def test_qa_defect_001_drifted_value_never_lands_under_wrong_label():
    r = extract_panel([_drift_shot()], side_hint=None, panel_hint=None)
    assert r["stats"] == {}
    assert "stats.Infantry|Attack" in r["unreadable_fields"]
    assert "stats.Infantry|Defense" in r["unreadable_fields"]
    assert r["warnings"] == ["orphan value near y=0.130"]
    assert r["status"] == "failed"

def test_qa_defect_019_extract_panel_rejects_malformed_token_shots():
    for bad in ("nope", [{"text": "Infantry Attack"}], [None], 7):
        with pytest.raises(ValueError):
            extract_panel(bad, side_hint=None, panel_hint=None)

def test_qa_defect_022_all_unreadable_specials_report_partial_not_read():
    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83, conf=0.20))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [] and r["specials_observed"] == "partial"

def test_qa_defect_022_partially_readable_specials_report_partial():
    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83, conf=0.20))
    shot.append(_tok("Defense Bonus (Pet Skill)", 0.05, 0.86, 0.40, 0.89))
    shot.append(_tok("+8.0%", 0.70, 0.86, 0.95, 0.89))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": "Defense Bonus (Pet Skill)", "value": 8.0, "side": None}]
    assert r["specials_observed"] == "partial"

def test_qa_defect_022_specials_panel_header_with_no_rows_reads_clean():
    # The legal zero-specials account: the panel WAS captured and read.
    shot = _shot_scout()
    shot.append(_tok("Stat Bonuses", 0.05, 0.80, 0.40, 0.83))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [] and r["specials_observed"] == "read"

def test_qa_defect_022_no_rows_and_no_header_is_none():
    assert extract_panel([_shot_scout()], side_hint="you",
                         panel_hint=None)["specials_observed"] == "none"

def test_qa_defect_022_all_readable_specials_report_read():
    shot = _shot_scout()
    shot.append(_tok("Attack Bonus (Pet Skill)", 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": "Attack Bonus (Pet Skill)", "value": 10.0, "side": None}]
    assert r["specials_observed"] == "read"

def _shot_citystats():
    toks, y = [], 0.10
    for st, v in (("Attack", "748.49%"), ("Defense", "612.10%"),
                  ("Lethality", "540.00%"), ("Health", "601.25%")):
        toks.append(_tok(f"Troops' {st}", 0.05, y, 0.40, y + 0.03))
        toks.append(_tok(v, 0.70, y, 0.95, y + 0.03))
        y += 0.05
    for cls in CLASSES:
        for st in STATS:
            toks.append(_tok(f"{cls} {st}", 0.05, y, 0.40, y + 0.03))
            toks.append(_tok("120.00%", 0.70, y, 0.95, y + 0.03))
            y += 0.05
    return toks

def test_qa_defect_021_incompatible_hint_detection_pairs_still_fail_closed():
    cases = [
        ("citystats", _shot_scout(), "scout"),
        ("citystats", _shot_battle(), "battle"),
        ("battle", _shot_citystats(), "citystats"),
        ("scout", _shot_citystats(), "citystats"),
        ("scout", _shot_battle(), "battle"),
    ]
    for hint, shot, detected in cases:
        r = extract_panel([shot], side_hint="you", panel_hint=hint)
        assert r["status"] == "failed", (hint, detected)
        assert r["stats"] == {}, (hint, detected)
        assert "stats_left" not in r and "stats_right" not in r, (hint, detected)
        assert f"panel hint {hint} contradicts detected {detected}" in r["warnings"]

def test_qa_defect_021_battle_hint_on_one_column_shot_is_a_partial_battle_read():
    # QA probe: battle_shot with zero enemy rows. Detection says "scout" (only
    # one column present) but the hint is compatible â€” read it as a partial
    # battle instead of hard-failing.
    r = extract_panel([_shot_battle(right_rows=set())], side_hint="you", panel_hint="battle")
    assert r["panel_type"] == "battle" and r["status"] == "partial"
    assert len(r["stats_left"]) == 12 and r["stats_right"] == {}
    assert r["stats_you"] == r["stats_left"] and r["stats_enemy"] == {}
    for cls in CLASSES:
        for st in STATS:
            assert f"stats_right.{cls}|{st}" in r["unreadable_fields"]
            assert f"stats_left.{cls}|{st}" not in r["unreadable_fields"]
    assert any("only one column was readable" in w for w in r["warnings"])

def test_qa_defect_021_agreeing_hints_stay_silent():
    for hint, shot in (("scout", _shot_scout()), ("battle", _shot_battle()),
                       ("citystats", _shot_citystats())):
        r = extract_panel([shot], side_hint="you", panel_hint=hint)
        assert r["panel_type"] == hint
        assert r["warnings"] == [], hint

def test_qa_defect_021_hint_under_unknown_detection_warns_but_proceeds():
    shot = [_tok("Infantry Attack", 0.05, 0.10, 0.40, 0.13),
            _tok("+4491.6%", 0.70, 0.10, 0.95, 0.13)]
    r = extract_panel([shot], side_hint="you", panel_hint="scout")
    assert r["panel_type"] == "scout" and r["status"] == "partial"
    assert any("could not be detected" in w for w in r["warnings"])

def test_qa_defect_026_repeated_warnings_are_deduped_across_shots():
    r = extract_panel([_drift_shot(), _drift_shot(), _drift_shot()],
                      side_hint=None, panel_hint=None)
    assert r["warnings"] == ["orphan value near y=0.130"]


# ---------------------------------------------------------------------------
# QA D-029: specials are side-aware end to end
# ---------------------------------------------------------------------------

SPECIAL_LABEL = "Attack Bonus (Pet Skill)"

def _shot_battle_with_specials(left="+10.0%", right="+8.0%",
                               left_conf=0.99, right_conf=0.99):
    toks = _shot_battle()
    y = 0.10 + 12 * 0.05
    toks.append(_tok(SPECIAL_LABEL, 0.38, y, 0.58, y + 0.03))
    if left is not None:
        toks.append(_tok(left, 0.03, y, 0.23, y + 0.03, conf=left_conf, color="green"))
    if right is not None:
        toks.append(_tok(right, 0.70, y, 0.90, y + 0.03, conf=right_conf, color="red"))
    return toks

def test_qa_defect_029_dual_column_specials_are_not_summed():
    r = extract_panel([_shot_battle_with_specials()], side_hint="you", panel_hint=None)
    assert r["panel_type"] == "battle"
    assert r["specials"] == [
        {"label": SPECIAL_LABEL, "value": 10.0, "side": "left"},
        {"label": SPECIAL_LABEL, "value": 8.0, "side": "right"},
    ]
    assert r["specials_you"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": "left"}]
    assert r["specials_enemy"] == [{"label": SPECIAL_LABEL, "value": 8.0, "side": "right"}]

def test_qa_defect_029_side_lists_fold_per_side_not_summed():
    from shell.app.ocr.panel.convert import fold_sets
    r = extract_panel([_shot_battle_with_specials()], side_hint="you", panel_hint=None)
    S_scout, S_battle, P_enemy = fold_sets(r["specials_you"], r["specials_enemy"],
                                           observed="read")
    assert abs(S_scout["Attack"] - 0.10) < 1e-9      # NOT 0.18
    assert abs(S_battle["Attack"] - 0.10) < 1e-9
    assert P_enemy["Attack"] == 0.0

def test_qa_defect_029_side_orientation_follows_the_requested_side():
    r = extract_panel([_shot_battle_with_specials()], side_hint="enemy", panel_hint=None)
    assert r["specials_you"] == [{"label": SPECIAL_LABEL, "value": 8.0, "side": "right"}]
    assert r["specials_enemy"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": "left"}]

def test_qa_defect_029_unreadable_specials_are_keyed_per_side():
    r = extract_panel([_shot_battle_with_specials(right_conf=0.20)],
                      side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": "left"}]
    assert f"specials_right.{SPECIAL_LABEL}" in r["unreadable_fields"]
    assert f"specials_left.{SPECIAL_LABEL}" not in r["unreadable_fields"]
    assert r["specials_observed"] == "partial"

def test_qa_defect_029_single_column_specials_keep_the_flat_key_and_null_side():
    shot = _shot_scout()
    shot.append(_tok(SPECIAL_LABEL, 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": None}]
    assert "specials_you" not in r and "specials_enemy" not in r

def test_qa_defect_029_single_column_unreadable_special_keeps_the_flat_key():
    shot = _shot_scout()
    shot.append(_tok(SPECIAL_LABEL, 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83, conf=0.20))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert f"specials.{SPECIAL_LABEL}" in r["unreadable_fields"]


# ---------------------------------------------------------------------------
# QA D-034: side-awareness is derived from the ROWS, not the panel type
# ---------------------------------------------------------------------------

def _shot_specials_only(right_conf=0.99):
    """A standalone two-column specials screenshot: no class rows at all, so
    detect_panel_type() says "unknown"."""
    toks, y = [], 0.10
    for label in (SPECIAL_LABEL, "Defense Bonus (Pet Skill)"):
        toks.append(_tok(label, 0.38, y, 0.58, y + 0.03))
        toks.append(_tok("+10.0%", 0.03, y, 0.23, y + 0.03, color="green"))
        toks.append(_tok("+8.0%", 0.70, y, 0.90, y + 0.03, conf=right_conf, color="red"))
        y += 0.05
    return toks

def _fold_attack(specials_side):
    from shell.app.ocr.panel.convert import fold_sets
    S_scout, _, _ = fold_sets(specials_side, [], observed="read")
    return S_scout["Attack"]

def _left(specials):
    return [s for s in specials if s["side"] == "left"]

def test_qa_defect_034_standalone_specials_image_is_side_aware_without_a_hint():
    r = extract_panel([_shot_specials_only()], side_hint="you", panel_hint=None)
    assert r["panel_type"] == "unknown"          # no class rows to detect on
    assert r["specials"][:2] == [
        {"label": SPECIAL_LABEL, "value": 10.0, "side": "left"},
        {"label": SPECIAL_LABEL, "value": 8.0, "side": "right"},
    ]
    assert abs(_fold_attack(_left(r["specials"])) - 0.10) < 1e-9      # not 0.18

def test_qa_defect_034_scout_hint_does_not_flatten_two_column_specials():
    r = extract_panel([_shot_specials_only()], side_hint="you", panel_hint="scout")
    assert r["panel_type"] == "scout"
    assert abs(_fold_attack(_left(r["specials"])) - 0.10) < 1e-9
    assert {s["side"] for s in r["specials"]} == {"left", "right"}

def test_qa_defect_034_battle_hint_is_unchanged():
    r = extract_panel([_shot_specials_only()], side_hint="you", panel_hint="battle")
    assert r["panel_type"] == "battle"
    assert abs(_fold_attack(_left(r["specials"])) - 0.10) < 1e-9

def test_qa_defect_034_unreadable_side_keys_survive_an_unknown_panel_type():
    r = extract_panel([_shot_specials_only(right_conf=0.20)], side_hint="you", panel_hint=None)
    assert f"specials_right.{SPECIAL_LABEL}" in r["unreadable_fields"]
    assert r["specials"] == [
        {"label": SPECIAL_LABEL, "value": 10.0, "side": "left"},
        {"label": "Defense Bonus (Pet Skill)", "value": 10.0, "side": "left"},
    ]

def test_qa_defect_034_single_column_contract_is_untouched():
    shot = _shot_scout()
    shot.append(_tok(SPECIAL_LABEL, 0.05, 0.80, 0.40, 0.83))
    shot.append(_tok("+10.0%", 0.70, 0.80, 0.95, 0.83))
    r = extract_panel([shot], side_hint="you", panel_hint=None)
    assert r["specials"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": None}]
    assert abs(_fold_attack(r["specials"]) - 0.10) < 1e-9
    assert "specials_you" not in r

def test_qa_defect_034_one_sided_special_on_a_battle_panel_stays_flat():
    # No counterpart in the other column => nothing can be summed, so the flat
    # single-column contract applies (the ruling's "otherwise" branch).
    toks = _shot_battle()
    y = 0.10 + 12 * 0.05
    toks.append(_tok(SPECIAL_LABEL, 0.38, y, 0.58, y + 0.03))
    toks.append(_tok("+10.0%", 0.03, y, 0.23, y + 0.03, color="green"))
    r = extract_panel([toks], side_hint="you", panel_hint=None)
    assert r["panel_type"] == "battle"
    assert r["specials"] == [{"label": SPECIAL_LABEL, "value": 10.0, "side": None}]
