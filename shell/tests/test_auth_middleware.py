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


def test_dev_user_header_switches_identity_in_bypass_mode():
    """F22 (EVAL_ROUND_1.md, minor): X-Dev-User was honored by limits.py and
    sent by the probe suite, but auth.py always set user_id="dev_user"
    regardless — the probes' "free user" and "pro user" were secretly the
    SAME account, which was part of why the burst window bled across
    probes (F12). Bypass mode only (hostile-client rule)."""
    client = TestClient(make_app(DEV_BYPASS=True))
    body = client.get("/shell/me", headers={"X-Dev-User": "probe_free"}).json()
    assert body["user"]["user_id"] == "probe_free"

    body2 = client.get("/shell/me", headers={"X-Dev-User": "probe_pro",
                                             "X-Dev-Plan": "pro"}).json()
    assert body2["user"]["user_id"] == "probe_pro"
    assert body2["user"]["plan"] == "pro"


def test_dev_user_header_ignored_outside_bypass_mode(jwt_client, rsa_pair):
    """The hostile-client rule (COMPASS invariant 6): X-Dev-User must never
    let a real, verified session's identity be spoofed."""
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_clerk_123", "exp": int(time.time()) + 300})
    jwt_client.cookies.set("__session", token)
    resp = jwt_client.get("/shell/me", headers={"X-Dev-User": "someone_else"})
    assert resp.json()["user"]["user_id"] == "user_clerk_123"


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
    assert client.get("/shell/signout", follow_redirects=False).status_code != 401
    assert client.get("/legal/tos").status_code == 200
    assert client.get("/legal/privacy").status_code == 200


def test_ocr_client_assets_prefix_open_without_auth():
    """F9 fix carve-out: the OCR overlay's static JS/CSS/WASM loader assets
    must stay pre-auth-reachable (main.py injects their tags into every
    served page unconditionally, auth state or not) even though the F9 fix
    now denies-by-default for every other unauthenticated page/asset path."""
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.get("/shell/ocr/client/ocr_flow.js")
    assert resp.status_code == 200


# ------------------------------------------------------------------ F9 fix

def test_unauthed_root_redirects_307_even_without_an_accept_header():
    """F9 (EVAL_ROUND_1.md): previously the 307-to-sign-in only fired when
    the client SENT an Accept: text/html header; a plain request (curl
    default, a script) fell through and got served the full 266KB app
    shell unauthenticated. Now the redirect fires regardless."""
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.get("/", follow_redirects=False)   # no Accept header at all
    assert resp.status_code == 307
    assert "sign-in" in resp.headers["location"]


def test_unauthed_index_html_redirects_regardless_of_accept():
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.get("/index.html", headers={"Accept": "*/*"}, follow_redirects=False)
    assert resp.status_code == 307


def test_unauthed_non_get_non_exempt_path_denied_closed():
    """The residual case the old code silently passed through (a non-GET/
    HEAD request to a path that is neither /api/ nor /shell/) is now denied
    rather than forwarded unauthenticated."""
    client = TestClient(make_app(DEV_BYPASS=False))
    resp = client.post("/some-random-path")
    assert resp.status_code == 401


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


# ------------------------------------------------------- F3: resolve_plan

def test_verified_session_resolves_real_plan_from_subscription(rsa_pair, jwt_client):
    """F3 (EVAL_ROUND_1.md): a verified session must reflect the REAL
    subscription plan (Agent B's resolve_plan, wired in post-verify), not a
    hardcoded "free" — otherwise a paying Pro subscriber is served the free
    tier forever."""
    from shell.app import db as _db
    _db.reset_db()
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_pro_1", "exp": int(time.time()) + 300})
    import asyncio
    asyncio.run(_db.apply_subscription_update("user_pro_1", plan="pro", status="active"))

    jwt_client.cookies.set("__session", token)
    resp = jwt_client.get("/shell/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["plan"] == "pro"


def test_verified_session_without_subscription_stays_free(rsa_pair, jwt_client):
    from shell.app import db as _db
    _db.reset_db()
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_no_sub", "exp": int(time.time()) + 300})
    jwt_client.cookies.set("__session", token)
    resp = jwt_client.get("/shell/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["plan"] == "free"


def test_resolve_plan_failure_degrades_to_free_never_invents_pro(rsa_pair, jwt_client,
                                                                  monkeypatch):
    """A broken/raising resolve_plan must degrade to "free" — the mirror
    failure mode of F3 (a broken resolver must never grant "pro" for free
    either)."""
    import shell.app.billing.entitlements as ent_mod

    async def boom(user_id):
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(ent_mod, "resolve_plan", boom)
    key, _ = rsa_pair
    token = _token(key, {"sub": "user_x", "exp": int(time.time()) + 300})
    jwt_client.cookies.set("__session", token)
    resp = jwt_client.get("/shell/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["plan"] == "free"


def test_dev_bypass_plan_still_from_header_not_resolve_plan(monkeypatch):
    """DEV_BYPASS mode must stay exactly as documented in docs/OCR_QA_PLAN.md
    §8 (the sanctioned X-Dev-Plan technique): resolve_plan is never
    consulted there, only the header."""
    import shell.app.billing.entitlements as ent_mod

    async def unexpected(user_id):
        raise AssertionError("resolve_plan must not be called in DEV_BYPASS mode")

    monkeypatch.setattr(ent_mod, "resolve_plan", unexpected)
    client = TestClient(make_app(DEV_BYPASS=True))
    resp = client.get("/shell/me", headers={"X-Dev-Plan": "pro"})
    assert resp.json()["user"]["plan"] == "pro"


def test_userctx_contract_fields():
    """Shared contract (shell/ARCHITECTURE.md): exactly these fields."""
    ctx = auth.UserCtx(user_id="u", email=None, plan="free")
    assert set(ctx.__dataclass_fields__) == {"user_id", "email", "plan"}
