import pytest
from shell.app.ocr.panel.tokens import OcrToken, tokens_from_json

def test_token_roundtrip_and_validation():
    ts = tokens_from_json([{"text": "Infantry Attack", "x0": 0.05, "y0": 0.10, "x1": 0.40, "y1": 0.13, "conf": 0.98}])
    assert ts[0].text == "Infantry Attack" and ts[0].color is None

def test_token_rejects_bad_coords_and_conf():
    with pytest.raises(ValueError):
        tokens_from_json([{"text": "x", "x0": -0.1, "y0": 0, "x1": 0.5, "y1": 0.1, "conf": 0.9}])
    with pytest.raises(ValueError):
        tokens_from_json([{"text": "x", "x0": 0.1, "y0": 0, "x1": 0.5, "y1": 0.1, "conf": 1.7}])

def test_qa_defect_019_malformed_tokens_raise_value_error_not_key_or_type_error():
    bad_inputs = [
        "not a list",
        ["not an object"],
        [{"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2, "conf": 0.9}],          # no text
        [{"text": "x", "y0": 0.1, "x1": 0.2, "y1": 0.2, "conf": 0.9}],        # no x0
        [{"text": "x", "x0": "a", "y0": 0.1, "x1": 0.2, "y1": 0.2, "conf": 0.9}],
        [{"text": "x", "x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2, "conf": None}],
    ]
    for bad in bad_inputs:
        with pytest.raises(ValueError):
            tokens_from_json(bad)
