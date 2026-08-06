import json, pathlib
FIX = pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json"

def _load():
    return json.loads(FIX.read_text(encoding="utf-8"))

def test_fixture_has_two_accounts_with_full_panels():
    g = _load()
    for acct in ("A", "B"):
        a = g["accounts"][acct]
        for k in ("bo_troops", "bo_class", "scout", "battle_left", "S_scout", "S_battle", "P_enemy", "U"):
            assert k in a, f"{acct} missing {k}"
        assert set(a["bo_class"]) == {"Infantry", "Lancer", "Marksman"}
        for cls in a["scout"]:
            assert set(a["scout"][cls]) == {"Attack", "Defense", "Lethality", "Health"}

def test_law_reproduces_battle_from_scout_both_accounts():
    # THE ground truth: Battle+1 = (Scout+1)*(1+S_battle)/((1+S_scout)*(1+P_enemy))
    g = _load()
    for acct in ("A", "B"):
        a = g["accounts"][acct]
        for cls, stats in a["scout"].items():
            for st, sv in stats.items():
                r = (1 + a["S_battle"][st]) / ((1 + a["S_scout"][st]) * (1 + a["P_enemy"][st]))
                pred = ((1 + sv / 100) * r - 1) * 100
                obs = a["battle_left"][cls][st]
                assert abs(pred - obs) <= 0.11, f"{acct}/{cls}/{st}: {pred} vs {obs}"
