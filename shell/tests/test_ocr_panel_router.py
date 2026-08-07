import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from shell.app.auth import UserCtx
from shell.app.ocr.panel_router import MAX_BODY_BYTES, router as panel_router

PNG_BYTES = b"\x89PNG\r\n\x1a\nminimal-test-image"

def _client(monkeypatch, plan):
    async def fake_resolve_plan(user_id):
        return plan

    monkeypatch.setattr("shell.app.ocr.panel_router.resolve_plan", fake_resolve_plan)
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

def test_free_tier_gets_403(client_free):
    r = client_free.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 403 and r.json()["error"] == "ocr_not_available_on_free"

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
    async def fake_resolve_plan(user_id):
        return "pro"

    monkeypatch.setattr("shell.app.ocr.panel_router.resolve_plan", fake_resolve_plan)
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    app = FastAPI()
    app.include_router(panel_router)      # no auth middleware => no request.state.user
    client = TestClient(app)
    r = client.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 401 and r.json()["error"] == "auth_required"

def test_qa_defect_016_more_than_three_files_422(client_paid):
    files = [("file", (f"{i}.png", PNG_BYTES, "image/png")) for i in range(4)]
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
                         headers={"content-length": str(MAX_BODY_BYTES * 3 + 16384 + 1)})
    assert r.status_code == 413 and r.json()["error"] == "body_too_large"
    assert sentinel == []                 # the handler never ran, so no spooling

def test_qa_defect_014_aggregate_upload_size_413(client_paid):
    blob = b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024)   # 3 MiB each, 9 MiB total
    files = [("file", (f"{i}.png", blob, "image/png")) for i in range(3)]
    r = client_paid.post("/shell/ocr/panel", files=files, data={"side": "enemy"})
    assert r.status_code == 413 and r.json()["error"] == "body_too_large"

def test_qa_defect_010_mock_response_is_marked_as_mock(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 200 and r.json()["source"] == "mock"

def test_qa_defect_010_mock_refused_outside_dev_env(client_paid, monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 503 and r.json()["error"] == "ocr_engine_unavailable"

    monkeypatch.setenv("ENV", "dev")
    ok = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert ok.status_code == 200

    monkeypatch.delenv("ENV", raising=False)
    unset = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert unset.status_code == 200

def test_qa_defect_019_malformed_tokens_are_422_not_500(client_paid, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("malformed token: coord out of range: 1.7")

    monkeypatch.setattr("shell.app.ocr.panel_router.extract_panel", boom)
    r = client_paid.post("/shell/ocr/panel",
                         files={"file": ("a.png", PNG_BYTES, "image/png")},
                         data={"side": "enemy"})
    assert r.status_code == 422 and r.json()["error"] == "unreadable_tokens"
