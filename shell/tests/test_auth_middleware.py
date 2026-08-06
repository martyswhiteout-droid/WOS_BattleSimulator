"""Tests for shell/app/auth.py (Agent A) — keyless.

DEV_BYPASS identity injection, 401/redirect behavior for unauthenticated
requests, exempt paths, and real RS256 JWT verification against a locally
generated JWKS (Clerk itself is never contacted).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json

import jwt
import pytest
from fastapi.testclient import TestClient

from shell.app import auth
from shell.app.config import Settings
from shell.app.main import create_app


def make_app(**kw):
    return create_app(Settings(_env_file=None, **kw))


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    """Agent B's in-memory quota/burst store is process-global; reset it per
    test so suites don't consume each other's dev_user daily quota."""
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


# ---------------------------------------------------------------- DEV_BYPASS

def test_dev_bypass_injects_dev_user():
    client = TestClient(make_app(DEV_BYPASS=True))
    resp = client.get("/shell/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["user_id"] == "dev_user"
    assert body["user"]["plan"] == "free"


def test_dev_bypass_defaults_on_without_clerk_secret():
    settings = Settings(_env_file=None)
    assert settings.CLERK_SECRET_KEY is None
    assert settings.dev_bypass is True
    settings = Settings(_env_file=None, CLERK_SECRET_KEY="sk_test_x")
    assert settings.dev_bypass is False


def test_dev_plan_header_switches_plan():
    client = TestClient(make_app(DEV_BYPASS=True))
    body = client.get("/shell/me", headers={"X-Dev-Plan": "pro"}).json()
    assert body["user"]["plan"] == "pro"
    # nonsense plans fall back to free (no invented tiers)
    body = client.get("/shell/me", headers={"X-Dev-Plan": "emperor"}).json()
    assert body["user"]["plan"] == "free"


# ------------------------------------------------------- unauthed behavior

def test_unauthed_api_gets_401_json():
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.post("/api/predict", json={})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "auth_required"
    assert body["sign_in_url"]


def test_unauthed_shell_route_gets_401():
    client = TestClient(make_app(DEV_BYPASS=False))
    assert client.get("/shell/me").status_code == 401


def test_unauthed_html_page_redirects_307():
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
    assert resp.status_code == 307
    assert "sign-in" in resp.headers["location"]
    assert "redirect_url=" in resp.headers["location"]


def test_exempt_paths_open_without_auth():
    client = TestClient(make_app(DEV_BYPASS=False))
    assert client.get("/shell/health").status_code == 200
    assert client.get("/shell/overlay.js").status_code == 200
    assert client.get("/shell/overlay.css").status_code == 200


# ------------------------------------------------------------ real JWT mode

KID = "test-key-1"
JWKS_URL = "https://clerk.test/.well-known/jwks.json"


@pytest.fixture(scope="module")
def rsa_pair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())  # str on PyJWT<2.7
    if isinstance(jwk, str):
        jwk = json.loads(jwk)
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return key, jwk


@pytest.fixture()
def jwt_client(rsa_pair, monkeypatch):
    _, jwk = rsa_pair

    async def fake_fetch(url):
        assert url == JWKS_URL
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
    return TestClient(make_app(DEV_BYPASS=False, CLERK_JWKS_URL=JWKS_URL))


def _token(key, claims, kid=KID):
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def test_valid_session_jwt_authenticates(rsa_pair, jwt_client):
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_clerk_123", "exp": int(time.time()) + 300})
    jwt_client.cookies.set("__session", token)
    resp = jwt_client.get("/shell/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["user_id"] == "user_clerk_123"


def test_expired_jwt_rejected(rsa_pair, jwt_client):
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_clerk_123", "exp": int(time.time()) - 3600})
    jwt_client.cookies.set("__session", token)
    assert jwt_client.get("/shell/me").status_code == 401


def test_garbage_token_rejected(jwt_client):
    jwt_client.cookies.set("__session", "not.a.jwt")
    assert jwt_client.get("/shell/me").status_code == 401


def test_unknown_kid_rejected(rsa_pair, jwt_client):
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_clerk_123", "exp": int(time.time()) + 300},
                   kid="rogue-key")
    jwt_client.cookies.set("__session", token)
    assert jwt_client.get("/shell/me").status_code == 401


def test_userctx_contract_fields():
    """Shared contract (shell/ARCHITECTURE.md): exactly these fields."""
    ctx = auth.UserCtx(user_id="u", email=None, plan="free")
    assert set(ctx.__dataclass_fields__) == {"user_id", "email", "plan"}
