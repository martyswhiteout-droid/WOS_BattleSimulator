import json, pathlib
from shell.app.ocr.panel.values import parse_value
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))

def test_value_grammar_all_fixture_cases():
    for case in FIX["value_grammar_cases"]:
        got = parse_value(case["raw"])
        if case["value"] is None:
            assert got is None, f"{case['raw']!r} must not parse"
        else:
            assert got is not None and abs(got.value - case["value"]) < 1e-9, f"{case['raw']!r}"

def test_no_locale_ambiguity_rejected():
    assert parse_value("1.234,5%") is None   # EU decimal style: reject in v1, don't guess
    assert parse_value("12 345") is None
