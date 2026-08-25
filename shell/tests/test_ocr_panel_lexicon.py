import json, pathlib
from shell.app.ocr.panel.lexicon import match_label
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))

def test_label_cases_from_fixture():
    for case in FIX["label_cases"]:
        assert match_label(case["raw"]) == case["canonical"], case["raw"]

def test_all_24_class_stat_labels_and_specials_resolve():
    for cls in ("Infantry", "Lancer", "Marksman"):
        for st in ("Attack", "Defense", "Lethality", "Health"):
            assert match_label(f"{cls} {st}") == f"{cls}|{st}"
    for sp in ("Attack Bonus (Pet Skill)", "Territory Defender Defense", "Enemy Lethality Penalty (Expert Skill)"):
        assert match_label(sp) == f"special:{sp}"

def test_numbers_never_match_labels():
    assert match_label("4491.6%") is None


def test_owner_20260825_appoint_based_labels_match_and_fold_as_plain_buffs():
    # Owner instruction 2026-08-25: appointment buffs are additional plain
    # A/D/L/H buffs. Skeletons are alpha-only, so the apostrophe/hyphen/case
    # variants the game may render all resolve to the same canonical label.
    from shell.app.ocr.panel.convert import fold_sets
    from shell.app.ocr.panel.lexicon import match_label
    for stat in ("Attack", "Defense", "Lethality", "Health"):
        canon = f"special:Appoint-based Troop's {stat}"
        assert match_label(f"Appoint-based Troop's {stat}") == canon
        assert match_label(f"Appoint-Based Troops' {stat}") == canon   # variant spelling
    S_scout, S_battle, P = fold_sets(
        [{"label": "Appoint-based Troop's Attack", "value": 5.0, "side": None}],
        [], observed="read")
    assert S_scout["Attack"] == 0.05 and S_battle["Attack"] == 0.05
    assert P["Attack"] == 0.0
