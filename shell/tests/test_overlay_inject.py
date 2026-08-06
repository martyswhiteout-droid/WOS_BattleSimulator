"""Tests for shell/app/overlay/ (Agent A) — keyless.

The overlay script is injected into the SERVED index.html response, the file
on disk is never modified (boundary rule 1), and the overlay assets are served
auth-exempt with the design-system palette + reduced-motion kill-switch.
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
from shell.app.overlay import SCRIPT_TAG, inject

TAG = SCRIPT_TAG.decode()


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    """Reset Agent B's process-global in-memory quota/burst store per test."""
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True)))


# ------------------------------------------------------------------- units

def test_inject_before_last_body_tag_case_insensitive():
    assert inject(b"<html><body>x</body></html>") == \
        b"<html><body>x" + SCRIPT_TAG + b"</body></html>"
    assert inject(b"<HTML><BODY>x</BODY></HTML>").endswith(
        SCRIPT_TAG + b"</BODY></HTML>")


def test_inject_without_body_tag_appends():
    assert inject(b"<p>fragment</p>") == b"<p>fragment</p>" + SCRIPT_TAG


# -------------------------------------------------------------- end to end

def test_served_index_has_overlay_script(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert TAG in resp.text
    # injected before </body>, not blindly appended
    assert resp.text.lower().rfind("</body>") > resp.text.find(TAG) > -1


def test_prototype_file_on_disk_untouched():
    """Boundary rule 1: the injection is response-time only."""
    html = (_REPO_ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert "/shell/overlay.js" not in html


def test_overlay_js_served_self_contained(client):
    resp = client.get("/shell/overlay.js")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/javascript")
    assert "wos-shell" in resp.text
    assert "/shell/me" in resp.text                 # chip fetches quota/plan
    assert "/shell/billing/checkout" in resp.text   # upgrade flow (guarded)
    for cdn in ("http://", "https://cdn", "googleapis", "unpkg", "jsdelivr"):
        assert cdn not in resp.text                 # self-contained, no CDNs


def test_overlay_css_palette_and_reduced_motion(client):
    resp = client.get("/shell/overlay.css")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")
    assert "#0B273D" in resp.text                   # navy panel token
    assert "prefers-reduced-motion" in resp.text    # kill-switch present
    assert "@import" not in resp.text


def test_non_index_responses_not_injected(client):
    """JSON from the API must never grow a script tag."""
    resp = client.get("/shell/health")
    assert TAG not in resp.text
