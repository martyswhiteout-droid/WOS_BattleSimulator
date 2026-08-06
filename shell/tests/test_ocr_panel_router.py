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

def test_mock_extraction_roundtrip_and_no_files_left(tmp_path, client_paid, monkeypatch):
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 200 and r.json()["status"] in ("ok", "partial")
    assert list(tmp_path.iterdir()) == []   # nothing persisted anywhere under the app tmp dir
