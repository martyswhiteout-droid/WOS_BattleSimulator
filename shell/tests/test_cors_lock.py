"""Tests for shell/app/main.py's CorsLockMiddleware (Agent A) — keyless.

F14 (EVAL_ROUND_1.md): wos_sim/predictor/server.py (a READ-ONLY import,
shell/ARCHITECTURE.md boundary rule 1 — cannot be edited here) wires
``CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])``
for its own dev convenience. Verified: an anonymous ``OPTIONS /api/predict``
from ``Origin: https://evil.example`` got back
``access-control-allow-origin: *``. This middleware wraps the WHOLE app
(outermost) so it can rewrite whatever CORS headers any inner layer set,
locking them to the configured production origin (BASE_URL) outside dev.
"""
from __future__ import annotations

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


def _client(env, base_url="https://wostests.com"):
    # IP_HASH_SALT: F11's fail-fast refuses to boot staging/prod without it;
    # this value is test-only, not a secret.
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True,
                                           ENV=env, BASE_URL=base_url,
                                           IP_HASH_SALT="test-only-salt")))


def test_untrusted_origin_gets_no_cors_grant_in_staging():
    client = _client("staging")
    resp = client.options("/api/predict",
                          headers={"Origin": "https://evil.example",
                                   "Access-Control-Request-Method": "POST"})
    acao = resp.headers.get("access-control-allow-origin")
    assert acao != "*"
    assert acao != "https://evil.example"


def test_configured_origin_gets_a_locked_cors_grant_in_staging():
    client = _client("staging", base_url="https://wostests.com")
    resp = client.options("/api/predict",
                          headers={"Origin": "https://wostests.com",
                                   "Access-Control-Request-Method": "POST"})
    assert resp.headers.get("access-control-allow-origin") == "https://wostests.com"


def test_wildcard_never_leaks_through_in_prod():
    client = _client("prod")
    resp = client.options("/api/predict",
                          headers={"Origin": "https://evil.example",
                                   "Access-Control-Request-Method": "POST"})
    assert resp.headers.get("access-control-allow-origin") != "*"


def test_dev_env_is_unaffected_wildcard_still_open():
    """Dev convenience preserved: local tooling / the prototype's own
    cross-origin dev workflows keep working."""
    client = _client("dev")
    resp = client.options("/api/predict",
                          headers={"Origin": "https://evil.example",
                                   "Access-Control-Request-Method": "POST"})
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_regular_get_request_also_locked_not_just_preflight():
    client = _client("staging")
    resp = client.get("/shell/health", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("access-control-allow-origin") != "*"
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example"
