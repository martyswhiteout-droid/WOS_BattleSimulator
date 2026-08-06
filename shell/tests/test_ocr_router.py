"""Agent C — endpoint tests for POST /shell/ocr (keyless, mock vision).

Covers the ARCHITECTURE.md response contract: ok / partial / failed statuses,
unreadable_fields surfacing, image-hash cache hits (no second vision call),
400s for oversized / wrong-type uploads, and 401 when unauthenticated.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

# Make `shell.app.ocr` importable regardless of pytest invocation directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from shell.app.ocr._shims import UserCtx  # noqa: E402
from shell.app.ocr.cache import InMemoryOcrJobs  # noqa: E402
from shell.app.ocr.extract import MAX_IMAGE_BYTES, OcrService  # noqa: E402
from shell.app.ocr.router import router as ocr_router  # noqa: E402
from shell.app.ocr.vision import MockVision  # noqa: E402


def make_png(color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def build_client(fixture: str) -> tuple[TestClient, MockVision]:
    """Test app: fake auth middleware (Agent A's contract) + injected OCR service."""
    vision = MockVision(fixture=fixture)
    service = OcrService(vision=vision, jobs=InMemoryOcrJobs())
    app = FastAPI()

    @app.middleware("http")
    async def fake_auth(request, call_next):  # stands in for Agent A's AuthMiddleware
        if request.headers.get("x-test-anon") != "1":
            request.state.user = UserCtx(
                user_id="test_user", email="t@example.invalid", plan="pro"
            )
        return await call_next(request)

    app.include_router(ocr_router)
    app.state.ocr_service = service
    return TestClient(app), vision


def post_image(client: TestClient, data: bytes, filename="shot.png",
               content_type="image/png", headers=None, extra=None):
    return client.post(
        "/shell/ocr",
        files={"file": (filename, data, content_type)},
        data=extra or {},
        headers=headers or {},
    )


# --- happy / partial / failed paths ----------------------------------------

def test_upload_ok_path_with_valid_mock():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["unreadable_fields"] == []
    assert body["job_id"]
    assert body["cached"] is False
    assert body["profile"]["troops_total"] == 1000
    assert body["profile"]["schema_version"] == 1
    assert body["profile"]["stats"]["Infantry|Attack"] == 150.0
    assert vision.calls == 1


def test_partial_path_surfaces_unreadable_fields():
    client, _ = build_client("synthetic_partial_nulls.json")
    resp = post_image(client, make_png(), extra={"side": "defender"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "partial"
    assert body["profile"] is not None
    assert body["unreadable_fields"], "partial results must name the unreadable fields"
    assert "stats" in body["unreadable_fields"]
    assert "per_class.Infantry.tier" in body["unreadable_fields"]


def test_invalid_mock_yields_failed_with_reason():
    client, _ = build_client("synthetic_invalid.json")
    resp = post_image(client, make_png())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["profile"] is None
    assert body["reason"].startswith("validator_rejected")
    assert "casualty identity" in body["reason"]
    assert body["job_id"]  # failures are recorded jobs too


# --- caching ---------------------------------------------------------------

def test_cache_hit_skips_second_vision_call():
    client, vision = build_client("synthetic_valid_type1.json")
    png = make_png()
    first = post_image(client, png).json()
    second = post_image(client, png).json()
    assert vision.calls == 1, "identical image must be served from the hash cache"
    assert second["cached"] is True
    assert first["cached"] is False
    assert second["job_id"] == first["job_id"]
    assert second["status"] == first["status"] == "ok"
    # a DIFFERENT image is a real second job
    third = post_image(client, make_png(color=(99, 0, 0))).json()
    assert vision.calls == 2
    assert third["cached"] is False


# --- rejects ---------------------------------------------------------------

def test_oversized_upload_400():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, b"\x00" * (MAX_IMAGE_BYTES + 1))
    assert resp.status_code == 400
    assert resp.json()["error"] == "image_too_large"
    assert vision.calls == 0, "no vision spend on rejected uploads"


def test_wrong_type_upload_400():
    client, vision = build_client("synthetic_valid_type1.json")
    buf = io.BytesIO()
    Image.new("P", (16, 16)).save(buf, format="GIF")
    resp = post_image(client, buf.getvalue(), filename="anim.gif", content_type="image/gif")
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_image_type"
    assert vision.calls == 0


def test_garbage_upload_400():
    client, _ = build_client("synthetic_valid_type1.json")
    resp = post_image(client, b"not an image at all")
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_image"


def test_invalid_side_400():
    client, _ = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png(), extra={"side": "spectator"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_side"


def test_unauthenticated_401():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png(), headers={"x-test-anon": "1"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "auth_required"
    assert "sign_in_url" in body
    assert vision.calls == 0
