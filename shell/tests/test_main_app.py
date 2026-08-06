"""Tests for shell/app/main.py (Agent A) — keyless.

App assembly: health, /shell/me shape, and the critical end-to-end path —
an authenticated (DEV_BYPASS) request reaching the mounted, untouched
wos_sim predictor app with a real scenario payload.
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


@pytest.fixture(scope="module")
def scenario():
    """Real profile shape from the canonical saved scenario (BRD §9 dicts)."""
    data = json.loads((_REPO_ROOT / "Scenarios" / "Scenario_1.json")
                      .read_text(encoding="utf-8"))
    return {"own": data["own"], "enemy": data["enemy"]}


def test_health_open_and_sim_mounted(client):
    body = client.get("/shell/health").json()
    assert body["status"] == "ok"
    assert body["sim_mounted"] is True
    assert body["env"] == "dev"


def test_me_shape_and_free_quota_defaults(client):
    body = client.get("/shell/me").json()
    assert body["user"] == {"user_id": "dev_user", "email": None, "plan": "free"}
    assert body["entitlements"]["daily_sim_quota"] == 5   # FREE_SIMS_PER_DAY
    assert body["entitlements"]["daily_ocr_quota"] == 0   # free tier: no OCR
    assert body["remaining"]["sims"] == 5
    assert body["sign_in_url"]


def test_me_pro_quota_via_dev_plan_header(client):
    body = client.get("/shell/me", headers={"X-Dev-Plan": "pro"}).json()
    assert body["entitlements"]["daily_sim_quota"] == 100  # PRO_SIMS_PER_DAY
    assert body["entitlements"]["daily_ocr_quota"] == 30   # PRO_OCR_PER_DAY


def test_authed_predict_reaches_sim(client, scenario):
    resp = client.post("/api/predict", json={**scenario, "n": 20, "seed": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["verdict"]["win"]["p"] <= 1.0
    assert body["engine"]["confidence"] in ("coin_flip", "directional")
    assert body["n"] == 20
    assert "army_losses" in body and "own" in body["army_losses"]


def test_authed_battle_reaches_sim(client, scenario):
    resp = client.post("/api/battle", json={**scenario, "seed": 1, "index": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["turns"] and body["own_survivors"]
    assert "kill_matrix" in body        # dev: full telemetry available


def test_sim_validation_errors_stay_clean_400(client, scenario):
    resp = client.post("/api/predict", json={**scenario, "n": 0, "seed": 1})
    assert resp.status_code == 400      # InvalidInput -> clean JSON, not a 500
    assert "problems" in resp.json()


def test_prototype_static_ui_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
