import pathlib
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from shell.app.auth import UserCtx
from shell.app.ocr.panel_router import MAX_BODY_BYTES, MAX_REQUEST_BYTES, router as panel_router

PNG_BYTES = b"\x89PNG\r\n\x1a\nminimal-test-image"

def _client(monkeypatch, plan):
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    app = FastAPI()

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.state.user = UserCtx(user_id=f"{plan}_user", email=None, plan=plan)
        return await call_next(request)

    app.include_router(panel_router)
    return TestClient(app)

@pytest.fixture
def client_free(monkeypatch):
    return _client(monkeypatch, "free")

@pytest.fixture
def client_paid(monkeypatch):
    return _client(monkeypatch, "pro")

def _no_primary_engine(monkeypatch):
    """Make the primary engine unloadable.

    These tests assert the 503 that "the mock is refused" produced when the
    router had no engine at all. Since the production ladder landed, refusing
    the mock means falling through to the real engines, so the no-engine
    premise is now stated explicitly — the property under test is unchanged:
    if the mock gate regressed, the response would be 200 with source "mock".
    """
    def unloadable():
        raise ImportError("no module named rapidocr")

    monkeypatch.setattr("shell.app.ocr.panel.ladder._load_rapidocr", unloadable)


def test_oversize_body_413(client_paid):
    blob = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_BODY_BYTES + 1)
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", blob, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 413

def test_non_image_sniffed_415(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", b"MZ\x90\x00notpng", "image/png")}, data={"side": "enemy"})
    assert r.status_code == 415

def test_qa_defect_016_mock_roundtrip_never_spools_a_small_upload_to_disk(client_paid, monkeypatch):
    # Replaces the old "no files left" test, which only asserted that pytest's
    # own empty tmp_path was empty. Starlette spools uploads over 1 MiB to the
    # OS temp dir; a small upload must never trigger a rollover.
    rollovers = []
    original = tempfile.SpooledTemporaryFile.rollover

    def spy(self):
        rollovers.append(self)
        return original(self)

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", spy)
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 200 and r.json()["status"] in ("ok", "partial")
    assert rollovers == []

def test_qa_defect_016_unauthenticated_gets_401(monkeypatch):
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    app = FastAPI()
    app.include_router(panel_router)      # no auth middleware => no request.state.user
    client = TestClient(app)
    r = client.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 401 and r.json()["error"] == "auth_required"

def test_qa_defect_016_more_than_three_files_422(client_paid):
    # 2026-08-29: cap raised 3 -> 6 (the four-row battle UI legitimately sends
    # heroes + stats + 2 buffs [+ troop power]; the owner's first real phone
    # read was rejected by the old cap). Both sides of the new boundary:
    files_ok = [("file", (f"{i}.png", PNG_BYTES, "image/png")) for i in range(6)]
    r_ok = client_paid.post("/shell/ocr/panel", files=files_ok, data={"side": "enemy"})
    assert r_ok.status_code == 200
    files = [("file", (f"{i}.png", PNG_BYTES, "image/png")) for i in range(7)]
    r = client_paid.post("/shell/ocr/panel", files=files, data={"side": "enemy"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_file_count"

def test_qa_defect_016_zero_byte_file_422(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", b"", "image/png")}, data={"side": "enemy"})
    assert r.status_code == 422 and r.json()["error"] == "empty_file"

def test_qa_defect_016_invalid_panel_422(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy", "panel": "bogus"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_panel"

def test_qa_defect_016_mock_off_is_503(client_paid, monkeypatch):
    monkeypatch.delenv("OCR_PANEL_MOCK", raising=False)
    _no_primary_engine(monkeypatch)
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"

def test_qa_defect_007_oversize_content_length_rejected_before_form_parsing(client_paid, monkeypatch):
    sentinel = []

    def spy(*args, **kwargs):
        sentinel.append(1)
        return {}

    monkeypatch.setattr("shell.app.ocr.panel_router.extract_panel", spy)
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"},
                         headers={"content-length": str(MAX_REQUEST_BYTES + 1)})
    assert r.status_code == 413 and r.json()["error"] == "body_too_large"
    assert sentinel == []                 # the handler never ran, so no spooling

def test_qa_defect_014_aggregate_upload_size_413(client_paid):
    from shell.app.ocr.panel_router import MAX_BODY_BYTES as _CAP
    # Each file under the per-file cap; the SUM exceeds the aggregate cap
    # (D-014's intent), sized from the constant (2026-08-29: 8 -> 16 MB).
    blob = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"0" * (_CAP // 2)
    files = [("file", (f"{i}.png", blob, "image/png")) for i in range(3)]
    r = client_paid.post("/shell/ocr/panel", files=files, data={"side": "enemy"})
    assert r.status_code == 413 and r.json()["error"] == "body_too_large"

def test_qa_defect_010_mock_response_is_marked_as_mock(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 200 and r.json()["source"] == "mock"

def test_qa_defect_010_mock_refused_outside_dev_env(client_paid, monkeypatch):
    _no_primary_engine(monkeypatch)
    _stub_env(monkeypatch, "prod")
    r = _post(client_paid)
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"

    _stub_env(monkeypatch, "dev")
    assert _post(client_paid).status_code == 200

def test_qa_defect_019_malformed_tokens_are_422_not_500(client_paid, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("malformed token: coord out of range: 1.7")

    monkeypatch.setattr("shell.app.ocr.panel_router.extract_panel", boom)
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 422 and r.json()["error"] == "unreadable_tokens"


def _post(client, **kwargs):
    return client.post("/shell/ocr/panel",
                       files={"file": ("a.png", PNG_BYTES, "image/png")},
                       data={"side": "enemy"}, **kwargs)

def _stub_env(monkeypatch, value, present=True):
    class _Settings:
        pass

    settings = _Settings()
    if present:
        settings.ENV = value
    monkeypatch.setattr("shell.app.ocr.panel_router.get_settings", lambda: settings)

def test_qa_defect_023_mock_gate_reads_settings_env_not_the_process_env(client_paid, monkeypatch):
    # QA probe: the process env says dev, the real config says prod. Settings win.
    _no_primary_engine(monkeypatch)
    monkeypatch.setenv("ENV", "dev")
    _stub_env(monkeypatch, "prod")
    r = _post(client_paid)
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"

def test_qa_defect_023_blank_or_missing_env_fails_closed(client_paid, monkeypatch):
    _no_primary_engine(monkeypatch)
    for value in ("", "   ", "	", "prod", "staging", "development", None, 7):
        _stub_env(monkeypatch, value)
        assert _post(client_paid).status_code == 503, repr(value)
    _stub_env(monkeypatch, None, present=False)      # settings object without ENV
    assert _post(client_paid).status_code == 503

def test_qa_defect_023_dev_env_enables_the_mock(client_paid, monkeypatch):
    for value in ("dev", "  DEV  ", "Dev"):
        _stub_env(monkeypatch, value)
        r = _post(client_paid)
        assert r.status_code == 200 and r.json()["source"] == "mock", repr(value)

def test_qa_defect_024_oversize_declared_length_never_reaches_the_parser(client_paid, monkeypatch):
    from starlette.formparsers import MultiPartParser

    parsed = []
    original = MultiPartParser.parse

    async def spy(self, *args, **kwargs):
        parsed.append(1)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(MultiPartParser, "parse", spy)
    r = _post(client_paid, headers={"content-length": str(__import__('shell.app.ocr.panel_router', fromlist=['x']).MAX_REQUEST_BYTES + 1)})
    assert r.status_code == 413 and r.json()["error"] == "body_too_large"
    assert parsed == []
    # the ceiling is MAX_BODY_BYTES + 64 KiB, not 3x it
    assert MAX_REQUEST_BYTES == MAX_BODY_BYTES + 65536

def test_qa_defect_024_chunked_upload_is_411(client_paid):
    for value in ("chunked", "Chunked", "CHUNKED"):
        r = _post(client_paid, headers={"transfer-encoding": value})
        assert r.status_code == 411, value
        assert r.json()["error"] == "length_required", value

def test_qa_defect_024_streamed_chunked_body_is_411(client_paid):
    r = client_paid.post("/shell/ocr/panel", content=iter([b"not-a-multipart-body"]))
    assert r.status_code == 411 and r.json()["error"] == "length_required"


# ---------------------------------------------------------------------------
# Production path: the engine ladder (RapidOCR primary, Gemini gap filler)
# ---------------------------------------------------------------------------

def _fake_ladder(monkeypatch, result=None, raises=None, captured=None):
    async def ladder(images, side, panel_hint, *, settings):
        if captured is not None:
            captured.update(images=list(images), side=side, panel_hint=panel_hint,
                            settings=settings)
        if raises is not None:
            raise raises
        return dict(result or {"status": "ok", "stats": {}, "unreadable_fields": [],
                               "warnings": [], "engines_used": ["rapidocr"],
                               "field_engine": {}})

    monkeypatch.setattr("shell.app.ocr.panel_router.extract_panel_production", ladder)


def test_production_path_runs_the_ladder_and_passes_provenance(client_paid, monkeypatch):
    monkeypatch.delenv("OCR_PANEL_MOCK", raising=False)
    captured = {}
    _fake_ladder(monkeypatch, captured=captured, result={
        "status": "ok", "stats": {"Infantry|Attack": 4491.6}, "unreadable_fields": [],
        "warnings": [], "engines_used": ["rapidocr", "gemini"],
        "field_engine": {"stats.Infantry|Attack": "gemini"}})

    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy", "panel": "scout"})

    assert r.status_code == 200
    body = r.json()
    assert body["engines_used"] == ["rapidocr", "gemini"]
    assert body["field_engine"] == {"stats.Infantry|Attack": "gemini"}
    assert body["source"] == "engine"
    assert captured["images"] == [PNG_BYTES]
    assert captured["side"] == "enemy" and captured["panel_hint"] == "scout"
    assert captured["settings"] is not None


def test_production_path_engine_unavailable_is_503(client_paid, monkeypatch):
    from shell.app.ocr.panel.ladder import EngineUnavailable

    monkeypatch.delenv("OCR_PANEL_MOCK", raising=False)
    _fake_ladder(monkeypatch, raises=EngineUnavailable("no rapidocr"))
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"


def test_production_path_malformed_image_is_422_not_500(client_paid, monkeypatch):
    monkeypatch.delenv("OCR_PANEL_MOCK", raising=False)
    _fake_ladder(monkeypatch, raises=ValueError("unsupported or malformed OCR image"))
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 422 and r.json()["error"] == "unreadable_tokens"


def test_mock_path_never_reaches_the_ladder(client_paid, monkeypatch):
    _fake_ladder(monkeypatch, raises=AssertionError("ladder must not run under the mock"))
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mock" and "engines_used" not in body


def test_qa_defect_030_runtime_error_from_the_ladder_is_503_not_500(client_paid, monkeypatch):
    monkeypatch.delenv("OCR_PANEL_MOCK", raising=False)
    _fake_ladder(monkeypatch, raises=RuntimeError("Event loop is closed"))
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"


# ---------------------------------------------------------------------------
# QA D-031: the free-tier signal is the middleware's 402, for BOTH endpoints
# ---------------------------------------------------------------------------

def test_qa_defect_031_free_tier_is_402_from_the_middleware(monkeypatch):
    from shell.app import db, limits

    db.reset_db()
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    app = FastAPI()
    app.include_router(panel_router)
    app.add_middleware(limits.LimitsMiddleware)
    client = TestClient(app)
    try:
        r = client.post("/shell/ocr/panel",
                        files={"file": ("a.png", PNG_BYTES, "image/png")},
                        data={"side": "enemy"}, headers={"x-dev-plan": "free"})
        assert r.status_code == 402 and r.json()["error"] == "payment_required"

        # a paid plan clears the meter and reaches the route (which then applies
        # its own auth contract) — proof the 402 came from the plan, not the path
        paid = client.post("/shell/ocr/panel",
                           files={"file": ("a.png", PNG_BYTES, "image/png")},
                           data={"side": "enemy"}, headers={"x-dev-plan": "pro"})
        assert paid.status_code != 402
    finally:
        db.reset_db()


def test_qa_defect_031_router_has_no_plan_branch_left():
    import shell.app.ocr.panel_router as module

    assert not hasattr(module, "resolve_plan")
    source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
    assert "ocr_not_available_on_free" not in source


# --- 2026-09-10: minimum-resolution guard (owner report: ~230px forwarded
# screenshots read nothing and burned ~90s each in the Gemini tier) ---------

def _png_of_width(width: int, height: int = 40) -> bytes:
    from PIL import Image
    import io as _io
    buf = _io.BytesIO()
    Image.new("RGB", (width, height), (10, 40, 60)).save(buf, format="PNG")
    return buf.getvalue()


def test_unreadably_small_screenshot_is_rejected_instantly_with_its_width(client_paid):
    resp = client_paid.post("/shell/ocr/panel",
                            files=[("file", ("shot.png", _png_of_width(100), "image/png"))],
                            data={"side": "you", "panel": "battle"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "image_too_small"
    assert body["width"] == 100
    assert body["min_width"] == 120


def test_small_but_readable_screenshot_is_upscaled_not_rejected(client_paid, monkeypatch):
    # 2026-09-11 (owner: "not from phone"): a 230px chat-forwarded copy must
    # reach the engine — upscaled to the working width, never refused.
    seen = {}
    async def fake_ladder(images, side, panel, *, settings=None):
        from PIL import Image
        import io as _io
        seen["widths"] = [Image.open(_io.BytesIO(i)).size[0] for i in images]
        return {"status": "ok", "panel_type": "battle", "requested_side": side, "stats": {},
                "specials": [], "specials_observed": "none", "unreadable_fields": [],
                "warnings": [], "field_engine": {}, "engines_used": ["rapidocr"]}
    import shell.app.ocr.panel_router as pr
    monkeypatch.setattr(pr, "extract_panel_production", fake_ladder)
    monkeypatch.setattr(pr, "_mock_enabled", lambda: False)
    resp = client_paid.post("/shell/ocr/panel",
                            files=[("file", ("shot.png", _png_of_width(230, 60), "image/png"))],
                            data={"side": "you", "panel": "battle"})
    assert resp.status_code == 200, resp.text
    assert seen["widths"] == [1000]


def test_upscale_helper_keeps_aspect_and_never_downscales():
    from PIL import Image
    import io as _io
    from shell.app.ocr.panel_router import _upscale_to_width
    small = _png_of_width(230, 100)
    big = Image.open(_io.BytesIO(_upscale_to_width(small, 1000)))
    assert big.size == (1000, 435)
    wide = _png_of_width(1206, 50)
    assert _upscale_to_width(wide, 1000) == wide      # untouched bytes
    assert _upscale_to_width(b"not an image", 1000) == b"not an image"
