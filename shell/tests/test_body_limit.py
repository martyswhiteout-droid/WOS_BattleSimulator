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


def test_limit_applies_to_shell_ocr_path_too(client):
    huge = b"x" * 5000
    resp = client.post("/shell/ocr", content=huge,
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
