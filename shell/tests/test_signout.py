"""Tests for POST /shell/signout (shell/app/main.py, Agent A) — keyless.

F6 (EVAL_ROUND_1.md): the overlay's sign-out button only ran
``document.cookie = "__session=...; Max-Age=0"`` client-side. Clerk's
``__session`` cookie is HttpOnly, so JavaScript cannot read OR delete it —
the user was redirected to the sign-in page while remaining fully
authenticated (shared-device account takeover). This route clears the
cookie via a ``Set-Cookie`` response header, which HttpOnly does not block
(it only blocks script access, not server-set headers), and best-effort
revokes the session at Clerk when a secret key is configured -- a failure
there must never block the (already-effective) local cookie clear.
"""
from __future__ import annotations

import sys
import time
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


def test_signout_clears_session_cookie_server_side():
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=False)))
    client.cookies.set("__session", "whatever-token-value")
    resp = client.post("/shell/signout")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "__session=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie


def test_signout_works_without_any_existing_cookie():
    """Idempotent: calling it while already signed out still 200s cleanly."""
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=False)))
    resp = client.post("/shell/signout")
    assert resp.status_code == 200


def test_signout_is_exempt_from_the_auth_requirement():
    """A stale/garbage/expired cookie must still be clearable -- signout
    itself must not require being currently authenticated."""
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=False)))
    resp = client.post("/shell/signout")
    assert resp.status_code != 401


def test_signout_never_calls_clerk_when_no_secret_key_configured(monkeypatch):
    """Keyless/mock-first: no CLERK_SECRET_KEY -> the Clerk revoke helper is
    never even attempted."""
    import shell.app.main as main_mod

    called = []
    orig = main_mod._revoke_clerk_session

    async def spy(*a, **kw):
        called.append(True)
        return await orig(*a, **kw)

    monkeypatch.setattr(main_mod, "_revoke_clerk_session", spy)
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True,
                                             CLERK_SECRET_KEY=None)))
    client.cookies.set("__session", "sometoken")
    resp = client.post("/shell/signout")
    assert resp.status_code == 200
    assert called == []


def test_signout_survives_a_raising_clerk_revoke_attempt(monkeypatch):
    """A Clerk-side failure (outage, bad endpoint, whatever) must never
    prevent the local cookie clear -- that is the part that actually ends
    the session for THIS browser."""
    import shell.app.main as main_mod

    async def boom(*a, **kw):
        raise RuntimeError("simulated Clerk outage")

    monkeypatch.setattr(main_mod, "_revoke_clerk_session", boom)
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=False,
                                             CLERK_SECRET_KEY="sk_test_x")))
    client.cookies.set("__session", "sometoken")
    resp = client.post("/shell/signout")
    assert resp.status_code == 200
    assert "Max-Age=0" in resp.headers.get("set-cookie", "")


def test_overlay_js_calls_the_signout_route_not_the_broken_document_cookie():
    client = TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True)))
    text = client.get("/shell/overlay.js").text
    assert "/shell/signout" in text
    assert 'document.cookie = "__session=' not in text
