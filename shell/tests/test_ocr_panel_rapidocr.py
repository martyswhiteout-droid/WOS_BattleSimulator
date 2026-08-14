"""Unit tests for the RapidOCR adapter's fast paths (QA D-047).

QA2 found ``engine_rapidocr.py`` had zero dedicated unit tests — its error
paths, bytes-like contract, and output shape were exercised only by the
``-m benchmark``-gated real-image run and one identity-pin in the ladder
suite, so a regression in any of them would ship undetected by the default
suite. These tests stay fast and keyless: everything under test happens
BEFORE the real ONNX engine would load (validation), or against a stubbed
engine seam (contract shape). Real inference stays where it belongs, in the
gated benchmark.
"""
import pytest

from shell.app.ocr.panel import engine_rapidocr
from shell.app.ocr.panel.engine_rapidocr import recognize_image


class _StubResult:
    def __init__(self, boxes=None, txts=None, scores=None):
        self.boxes = boxes
        self.txts = txts
        self.scores = scores


def _stub_engine(monkeypatch, result):
    # The lazy singleton is the seam: replacing it keeps the real ONNX
    # models unloaded (fast, keyless) while the whole normalization path
    # after it runs for real.
    monkeypatch.setattr(engine_rapidocr, "_ENGINE", lambda raw: result)


def _png_bytes(width=40, height=40):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (width, height), (10, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


def test_non_bytes_input_raises_typeerror_before_any_engine_work():
    for bad in ("a string", 7, None, ["bytes"], {"img": b""}):
        with pytest.raises(TypeError):
            recognize_image(bad)


def test_corrupt_bytes_raise_valueerror_not_a_silent_result():
    with pytest.raises(ValueError, match="unsupported or malformed OCR image"):
        recognize_image(b"definitely not an image")


def test_truncated_png_raises_valueerror():
    with pytest.raises(ValueError, match="unsupported or malformed OCR image"):
        recognize_image(_png_bytes()[:60])   # header survives, body does not


def test_bytearray_and_memoryview_are_accepted(monkeypatch):
    _stub_engine(monkeypatch, _StubResult())
    png = _png_bytes()
    assert recognize_image(bytearray(png)) == []
    assert recognize_image(memoryview(png)) == []


def test_none_result_fields_yield_no_tokens(monkeypatch):
    # RapidOCR returns None-filled results for a blank image: never fabricate
    # tokens from nothing to read.
    _stub_engine(monkeypatch, _StubResult(boxes=None, txts=None, scores=None))
    assert recognize_image(_png_bytes()) == []


def test_output_contract_shape_via_stubbed_engine(monkeypatch):
    # One recognized line -> one normalized Task-1 token dict with coords in
    # [0,1], conf clamped, and color None on a single-column layout.
    box = ((4.0, 8.0), (36.0, 8.0), (36.0, 16.0), (4.0, 16.0))
    _stub_engine(monkeypatch, _StubResult(boxes=[box], txts=["Infantry Attack"], scores=[1.7]))
    tokens = recognize_image(_png_bytes(width=40, height=40))
    assert len(tokens) == 1
    token = tokens[0]
    assert set(token) == {"text", "x0", "y0", "x1", "y1", "conf", "color"}
    assert token["text"] == "Infantry Attack"
    assert 0.0 <= token["x0"] < token["x1"] <= 1.0
    assert 0.0 <= token["y0"] < token["y1"] <= 1.0
    assert token["conf"] == 1.0   # clamped from the stub's out-of-range 1.7
    assert token["color"] is None


def test_glued_value_label_line_is_split_into_two_tokens(monkeypatch):
    # RapidOCR sometimes reads "+7.50% Defender Troops' Attack" as ONE line;
    # the adapter splits it into a value token and a label token.
    box = ((0.0, 8.0), (40.0, 8.0), (40.0, 16.0), (0.0, 16.0))
    _stub_engine(monkeypatch, _StubResult(
        boxes=[box], txts=["+7.50% Defender Troops' Attack"], scores=[0.98]))
    tokens = recognize_image(_png_bytes(width=40, height=40))
    assert [token["text"] for token in tokens] == ["+7.50%", "Defender Troops' Attack"]
    value, label = tokens
    assert value["x1"] <= label["x0"] + 1e-9   # value sits left of its label


@pytest.mark.asyncio
async def test_ladder_wraps_rapidocr_load_failure_as_engine_unavailable(monkeypatch):
    # QA D-047: ladder.py's two-line try/except (import failure ->
    # EngineUnavailable -> router 503) was untested; the equivalent Gemini
    # path has test_gemini_engine_import_failure_degrades_gracefully.
    from shell.app.ocr.panel import ladder

    def _boom():
        raise ImportError("rapidocr wheel is not installed")

    monkeypatch.setattr(ladder, "_load_rapidocr", _boom)
    with pytest.raises(ladder.EngineUnavailable, match="rapidocr engine unavailable"):
        await ladder.extract_panel_production(
            [b"unused"], "you", None, settings=object())
