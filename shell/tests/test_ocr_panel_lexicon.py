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
