"""Tests for shell/app/main.py's BodyLimitMiddleware (Agent A) — keyless.

F4 (EVAL_ROUND_1.md), body-size portion: a 12 MB JSON body sailed through as
a 200 in 9.55s because nothing capped request-body size before the app fully
buffered and parsed it. This middleware is the OUTERMOST layer (wraps auth,
limits, everything) so an oversized body is rejected before any downstream
buffering happens, regardless of which limits implementation (Agent B's own
LimitsMiddleware, or this module's fallback adapter) is active. It applies
in every ENV (not just staging/prod) — a huge body is wasteful in dev too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app.config import Settings
from shell.app.main import create_app


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


@pytest.fixture()
def client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True,
                                           MAX_BODY_BYTES=1024)))


def test_oversized_body_with_content_length_rejected_413_without_reaching_app(client):
    huge = json.dumps({"pad": "x" * 5000}).encode()
    resp = client.post("/api/predict", content=huge,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 413
    assert resp.json()["error"] == "payload_too_large"


def test_body_within_limit_passes_through(client):
    small = json.dumps({"own": {}, "enemy": {}}).encode()
    resp = client.post("/api/predict", content=small,
                       headers={"content-type": "application/json"})
    # not 413 -- whatever downstream validation says (400/200), but the
    # body-limit layer itself must not be what rejects a small payload.
    assert resp.status_code != 413


def test_ocr_paths_get_the_larger_ocr_limit_not_the_default(client):
    """A real screenshot upload (hundreds of KB — see the corpus fixtures
    under shell/tests/fixtures/panel_ocr/images/, 67KB-1.6MB) must NOT be
    rejected by this generic guard before it ever reaches Agent C's own
    OCR-specific validation (ocr/panel_router.py's own ~8MB cap, already
    tested by QA D-014/D-024). The `client` fixture sets the DEFAULT limit
    to 1024 bytes but leaves MAX_OCR_BODY_BYTES at its real (much larger)
    default, so a 5000-byte body must sail through THIS layer for the OCR
    paths specifically, even though the same size 413s on /api/predict."""
    body = b"x" * 5000
    for path in ("/shell/ocr", "/shell/ocr/panel"):
        resp = client.post(path, content=body,
                           headers={"content-type": "application/octet-stream"})
        assert resp.status_code != 413, f"{path} should not be capped by the default limit"


def test_ocr_paths_still_have_a_ceiling(client):
    """Not unlimited: something far larger than any legitimate screenshot
    (or Agent C's own ~8MB cap) still gets rejected by this outer guard."""
    client_tight_ocr = TestClient(create_app(
        Settings(_env_file=None, DEV_BYPASS=True, MAX_OCR_BODY_BYTES=1024)))
    resp = client_tight_ocr.post("/shell/ocr/panel", content=b"x" * 5000,
                                 headers={"content-type": "application/octet-stream"})
    assert resp.status_code == 413


def test_get_requests_are_never_body_limited(client):
    resp = client.get("/shell/health")
    assert resp.status_code == 200


def test_default_max_body_bytes_matches_caddyfile_cap():
    """Sanity: the app-level default should agree with the edge-level cap
    documented in shell/Caddyfile, so behavior is consistent whether the app
    is reached directly (dev, tests) or through Caddy."""
    assert Settings(_env_file=None).MAX_BODY_BYTES == 256 * 1024


def test_max_ocr_body_bytes_covers_the_ocr_modules_own_cap():
    """Sanity: this outer guard's OCR allowance must be >= Agent C's own
    ocr/panel_router.MAX_REQUEST_BYTES, or a legitimate upload that
    endpoint would accept could still 413 here first."""
    from shell.app.ocr import panel_router
    assert Settings(_env_file=None).MAX_OCR_BODY_BYTES >= panel_router.MAX_REQUEST_BYTES


def test_oversized_body_without_content_length_header_still_rejected(client):
    """Chunked/streamed bodies (no Content-Length) must still be bounded —
    the guard accumulates and rejects once the running total crosses the
    limit, rather than trusting a client-supplied header alone."""
    def body_stream():
        for _ in range(20):
            yield b"x" * 500   # 10000 bytes total, over the 1024 limit

    resp = client.post("/api/predict", content=body_stream(),
                       headers={"content-type": "application/json"})
    assert resp.status_code == 413
