import json, pathlib, pytest
from shell.app.ocr.panel.convert import (fold_sets, battle_to_scoutnet, calibrate_U,
                                         citystats_to_scoutnet, CalibrationError,
                                         MissingSpecialsError)
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))
STATS = ("Attack", "Defense", "Lethality", "Health")

@pytest.mark.parametrize("acct", ["A", "B"])
def test_fold_sets_reproduce_documented_sets(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed=True)
    for st in STATS:
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9, (acct, st)
        assert abs(S_battle[st] - a["S_battle"][st]) < 1e-9, (acct, st)
        assert abs(P_enemy[st] - a["P_enemy"][st]) < 1e-9, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_battle_to_scoutnet_recovers_scout_panel(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed=True)
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
        fold_sets([], [], observed=False)

def test_qa_defect_005_observed_flag_is_required():
    with pytest.raises(TypeError):
        fold_sets([], [])

def test_qa_defect_005_observed_panel_with_no_enemy_specials_stays_legal():
    # Account B: the panel WAS observed, the enemy genuinely has no specials.
    a = FIX["accounts"]["B"]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"], observed=True)
    for st in STATS:
        assert P_enemy[st] == 0.0
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9

def test_qa_defect_005_observed_empty_own_specials_is_legal():
    S_scout, S_battle, P_enemy = fold_sets([], [], observed=True)
    assert all(S_scout[st] == 0.0 and S_battle[st] == 0.0 and P_enemy[st] == 0.0 for st in STATS)
