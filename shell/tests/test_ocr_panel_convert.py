import json, pathlib, pytest
from shell.app.ocr.panel.convert import (fold_sets, battle_to_scoutnet, calibrate_U,
                                         citystats_to_scoutnet, CalibrationError,
                                         MissingSpecialsError)
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))
STATS = ("Attack", "Defense", "Lethality", "Health")

@pytest.mark.parametrize("acct", ["A", "B"])
def test_fold_sets_reproduce_documented_sets(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed="read")
    for st in STATS:
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9, (acct, st)
        assert abs(S_battle[st] - a["S_battle"][st]) < 1e-9, (acct, st)
        assert abs(P_enemy[st] - a["P_enemy"][st]) < 1e-9, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_battle_to_scoutnet_recovers_scout_panel(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed="read")
    got = battle_to_scoutnet(a["battle_left"], S_scout, S_battle, P_enemy)
    for cls, stats in a["scout"].items():
        for st, v in stats.items():
            assert abs(got[cls][st] - v) <= 0.11, (acct, cls, st, got[cls][st], v)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_calibrate_U_matches_documented_block(acct):
    a = FIX["accounts"][acct]
    U = calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], a["S_scout"])
    for st in STATS:
        assert abs(U[st] - a["U"][st]) <= 0.10, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_citystats_roundtrip_reproduces_scout(acct):
    a = FIX["accounts"][acct]
    U = calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], a["S_scout"])
    got = citystats_to_scoutnet(a["bo_troops"], a["bo_class"], U, a["S_scout"])
    for cls, stats in a["scout"].items():
        for st, v in stats.items():
            assert abs(got[cls][st] - v) <= 0.11, (acct, cls, st)

def test_calibration_error_on_inconsistent_panels():
    a = FIX["accounts"]["A"]
    bad_scout = {c: dict(s) for c, s in a["scout"].items()}
    bad_scout["Infantry"]["Attack"] += 50.0
    with pytest.raises(CalibrationError):
        calibrate_U(a["bo_troops"], a["bo_class"], bad_scout, a["S_scout"])

def test_qa_defect_005_unobserved_empty_specials_refuses_identity_fold():
    # No specials panel captured + nothing read => the fold is NOT "all zero".
    with pytest.raises(MissingSpecialsError):
        fold_sets([], [], observed="none")

def test_qa_defect_005_observed_flag_is_required():
    with pytest.raises(TypeError):
        fold_sets([], [])

def test_qa_defect_005_observed_panel_with_no_enemy_specials_stays_legal():
    # Account B: the panel WAS observed, the enemy genuinely has no specials.
    a = FIX["accounts"]["B"]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed="read")
    for st in STATS:
        assert P_enemy[st] == 0.0
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9

def test_qa_defect_005_observed_empty_own_specials_is_legal():
    S_scout, S_battle, P_enemy = fold_sets([], [], observed="read")
    assert all(S_scout[st] == 0.0 and S_battle[st] == 0.0 and P_enemy[st] == 0.0 for st in STATS)

def test_qa_defect_013_reduction_rows_fold_into_the_enemy_penalty_set():
    # "Enemy Attack/Defense Reduction" are lexicon-known penalties; the old
    # substring test on "Penalty" skipped them entirely.
    _, _, P_enemy = fold_sets([], [{"label": "Enemy Attack Reduction", "value": -12.0},
                                   {"label": "Enemy Defense Reduction", "value": 8.0}],
                              observed="read")
    assert abs(P_enemy["Attack"] - 0.12) < 1e-9
    assert abs(P_enemy["Defense"] - 0.08) < 1e-9   # abs(): a lost sign must not drop the row

def test_qa_defect_013_own_positive_penalty_row_is_excluded_with_a_warning():
    # OCR dropping the minus turned an outgoing penalty into a self-buff.
    warns = []
    S_scout, S_battle, _ = fold_sets(
        [{"label": "Enemy Defense Penalty (Pet Skill)", "value": 10.0}], [],
        observed="read", warnings=warns)
    assert S_scout["Defense"] == 0.0 and S_battle["Defense"] == 0.0
    assert len(warns) == 1 and "Enemy Defense Penalty (Pet Skill)" in warns[0]

def test_qa_defect_013_own_negative_penalty_row_is_silently_unfolded():
    warns = []
    S_scout, _, P_enemy = fold_sets(
        [{"label": "Enemy Defense Penalty (Pet Skill)", "value": -10.0}], [],
        observed="read", warnings=warns)
    assert S_scout["Defense"] == 0.0 and P_enemy["Defense"] == 0.0 and warns == []

def test_qa_defect_013_own_non_penalty_bonus_still_folds():
    S_scout, _, _ = fold_sets([{"label": "Defense Bonus (Pet Skill)", "value": 10.0}], [],
                              observed="read")
    assert abs(S_scout["Defense"] - 0.10) < 1e-9

def test_qa_defect_015_calibration_requires_all_three_classes():
    a = FIX["accounts"]["A"]
    with pytest.raises(CalibrationError):
        calibrate_U(a["bo_troops"], a["bo_class"],
                    {"Infantry": a["scout"]["Infantry"]}, a["S_scout"])
    with pytest.raises(CalibrationError):
        calibrate_U(a["bo_troops"], {"Infantry": a["bo_class"]["Infantry"]},
                    a["scout"], a["S_scout"])

def test_qa_defect_019_calibrate_U_raises_typed_errors_on_bad_input():
    a = FIX["accounts"]["A"]
    with pytest.raises(CalibrationError):        # was a bare ValueError from max([])
        calibrate_U(a["bo_troops"], a["bo_class"], {}, a["S_scout"])
    with pytest.raises(CalibrationError):        # was ZeroDivisionError
        calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], {st: -1.0 for st in STATS})
    with pytest.raises(CalibrationError):        # was KeyError
        holes = {c: {st: v for st, v in s.items() if st != "Health"}
                 for c, s in a["scout"].items()}
        calibrate_U(a["bo_troops"], a["bo_class"], holes, a["S_scout"])
    with pytest.raises(CalibrationError):        # was TypeError
        calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], None)

def test_qa_defect_019_battle_to_scoutnet_guards_the_division():
    a = FIX["accounts"]["A"]
    with pytest.raises(CalibrationError):
        battle_to_scoutnet(a["battle_left"], a["S_scout"],
                           {st: -1.0 for st in STATS}, a["P_enemy"])

def test_qa_defect_022_fold_requires_the_read_state_not_merely_seen():
    own = [{"label": "Attack Bonus (Pet Skill)", "value": 10.0}]
    for state in ("none", "partial"):
        with pytest.raises(MissingSpecialsError):
            fold_sets([], [], observed=state)
        with pytest.raises(MissingSpecialsError):
            fold_sets(own, [], observed=state)      # rows seen but not all readable

def test_qa_defect_022_read_state_with_no_specials_is_a_legal_identity():
    S_scout, S_battle, P_enemy = fold_sets([], [], observed="read")
    for st in STATS:
        assert S_scout[st] == 0.0 and S_battle[st] == 0.0 and P_enemy[st] == 0.0

def test_qa_defect_022_only_the_three_states_are_accepted():
    for bad in (True, False, None, 1, "yes", "READ"):
        with pytest.raises(ValueError) as exc:
            fold_sets([], [], observed=bad)
        assert not isinstance(exc.value, MissingSpecialsError), bad
