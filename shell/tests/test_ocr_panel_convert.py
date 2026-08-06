import json, pathlib, pytest
from shell.app.ocr.panel.convert import fold_sets, battle_to_scoutnet, calibrate_U, citystats_to_scoutnet, CalibrationError
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))
STATS = ("Attack", "Defense", "Lethality", "Health")

@pytest.mark.parametrize("acct", ["A", "B"])
def test_fold_sets_reproduce_documented_sets(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"])
    for st in STATS:
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9, (acct, st)
        assert abs(S_battle[st] - a["S_battle"][st]) < 1e-9, (acct, st)
        assert abs(P_enemy[st] - a["P_enemy"][st]) < 1e-9, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_battle_to_scoutnet_recovers_scout_panel(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"])
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
