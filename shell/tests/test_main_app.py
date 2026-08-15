"""Tests for shell/app/main.py (Agent A) — keyless.

App assembly: health, /shell/me shape, and the critical end-to-end path —
an authenticated (DEV_BYPASS) request reaching the mounted, untouched
wos_sim predictor app with a real scenario payload.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app import db as _db_module
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


def test_me_shape_and_dev_default_pro_quotas(client):
    # Localhost dev defaults to PRO (owner decision 2026-08-15,
    # settings.dev_default_plan — ENV-gated to dev only).
    body = client.get("/shell/me").json()
    assert body["user"] == {"user_id": "dev_user", "email": None, "plan": "pro"}
    assert body["entitlements"]["daily_sim_quota"] == 100  # PRO_SIMS_PER_DAY
    assert body["entitlements"]["daily_ocr_quota"] == 30   # PRO_OCR_PER_DAY
    assert body["remaining"]["sims"] == 100
    assert body["sign_in_url"]


def test_me_free_quota_shape_via_dev_plan_header(client):
    # The free tier's /shell/me shape stays covered — reached explicitly
    # with the bypass-only header (how free-path QA works in dev now).
    body = client.get("/shell/me", headers={"X-Dev-Plan": "free"}).json()
    assert body["user"]["plan"] == "free"
    assert body["entitlements"]["daily_sim_quota"] == 5   # FREE_SIMS_PER_DAY
    assert body["entitlements"]["daily_ocr_quota"] == 0   # free tier: no OCR
    assert body["remaining"]["sims"] == 5


def test_me_pro_quota_via_dev_plan_header(client):
    body = client.get("/shell/me", headers={"X-Dev-Plan": "pro"}).json()
    assert body["entitlements"]["daily_sim_quota"] == 100  # PRO_SIMS_PER_DAY
    assert body["entitlements"]["daily_ocr_quota"] == 30   # PRO_OCR_PER_DAY


# --- regression: M1 (EVAL_ROUND_2.md, round 1's F13) ------------------------
# "remaining" used to always report the full daily quota — main.py:396-398
# carried a literal "TODO(Agent B): subtract today's usage_events" comment —
# so the overlay chip told a signed-in user "Sims left today: 5" right up to
# the moment the 6th request actually 429'd. db.get_usage_today has existed
# since before round 1 and is used by limits.py's own quota check; it just
# was never wired into this endpoint's response.

def test_me_remaining_drops_by_recorded_usage_for_both_kinds():
    """Record N=3 sim uses and N=2 ocr uses directly against the real db
    store (the same primitive limits.check_and_record itself calls after an
    Allowed verdict), then assert /shell/me's remaining reflects EXACTLY
    that drop for each kind independently — never a shared/miscounted total."""
    _db_module.reset_db()
    try:
        app = create_app(Settings(_env_file=None, DEV_BYPASS=True))
        c = TestClient(app)
        headers = {"X-Dev-Plan": "pro", "X-Dev-User": "m1_user"}

        before = c.get("/shell/me", headers=headers).json()
        assert before["remaining"] == {"sims": 100, "ocr": 30}   # untouched baseline

        for _ in range(3):
            asyncio.run(_db_module.record_usage(
                "m1_user", endpoint="/api/predict", kind="sim"))
        for _ in range(2):
            asyncio.run(_db_module.record_usage(
                "m1_user", endpoint="/shell/ocr", kind="ocr"))

        after = c.get("/shell/me", headers=headers).json()
        assert after["remaining"]["sims"] == 100 - 3
        assert after["remaining"]["ocr"] == 30 - 2
    finally:
        _db_module.reset_db()


def test_me_remaining_drops_after_real_predict_calls(client, scenario):
    """Stronger end-to-end version of the above for the sim kind: real
    POST /api/predict calls through the full app (auth -> limits -> engine),
    not a direct db.record_usage call — proves the observable chain the user
    actually experiences, not just the read side."""
    headers = {"X-Dev-Plan": "pro", "X-Dev-User": "m1_e2e_user"}
    _db_module.reset_db()
    try:
        before = client.get("/shell/me", headers=headers).json()
        assert before["remaining"]["sims"] == 100

        for _ in range(3):
            resp = client.post("/api/predict", json={**scenario, "n": 5, "seed": 1},
                               headers=headers)
            assert resp.status_code == 200

        after = client.get("/shell/me", headers=headers).json()
        assert after["remaining"]["sims"] == 100 - 3
        assert after["remaining"]["ocr"] == 30   # sim usage must not touch ocr
    finally:
        _db_module.reset_db()


def test_me_remaining_never_goes_negative_past_quota():
    """max(0, quota - used): a user who somehow exceeds quota (e.g. via the
    per-IP cap path, or a race) must see 0, never a negative number."""
    _db_module.reset_db()
    try:
        app = create_app(Settings(_env_file=None, DEV_BYPASS=True))
        c = TestClient(app)
        headers = {"X-Dev-Plan": "free", "X-Dev-User": "m1_over_user"}
        for _ in range(9):   # well past FREE_SIMS_PER_DAY=5
            asyncio.run(_db_module.record_usage(
                "m1_over_user", endpoint="/api/predict", kind="sim"))
        body = c.get("/shell/me", headers=headers).json()
        assert body["remaining"]["sims"] == 0
    finally:
        _db_module.reset_db()


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


# --- regression: M4 (EVAL_ROUND_1.md F19 / EVAL_ROUND_2.md M4) --------------
# sweep_scan (limits.py) was solid, well-tested work that NOTHING called —
# no cron, no docker-compose sidecar, no in-app task. create_app() now wires
# limits.run_sweep_scheduler as a background task via a FastAPI lifespan.
# TestClient only runs lifespan startup/shutdown when used as a context
# manager (`with TestClient(app) as c:`) — none of the OTHER tests in this
# suite do that (they use the bare module-scoped `client` fixture above), so
# this is the first place the scheduler ever actually starts in the test
# suite; every other test in the whole 480-test suite is unaffected by it.

def test_sweep_scheduler_is_scheduled_at_app_startup(monkeypatch):
    """Proves create_app() genuinely starts the scheduler at startup — not
    just that the scheduler function exists somewhere and could be called."""
    from shell.app import limits as _limits_module

    calls = []

    async def fast_stub(*, interval_s=None, stop_event=None):
        calls.append(1)
        # returns immediately instead of looping — this test only needs to
        # prove create_app() STARTS the scheduler, not exercise the loop
        # itself (run_sweep_scheduler's own loop/backoff/fail-safe behavior
        # is covered directly in shell/tests/test_limits_sweep.py).

    monkeypatch.setattr(_limits_module, "run_sweep_scheduler", fast_stub)
    app = create_app(Settings(_env_file=None, DEV_BYPASS=True))
    with TestClient(app) as c:
        assert c.get("/shell/health").status_code == 200
        assert calls == [1], "run_sweep_scheduler must be started at app startup"
        assert app.state.sweep_task is not None


def test_sweep_scheduler_task_is_cancelled_at_app_shutdown():
    """A real (non-stub) scheduler task, still running (interval not yet
    elapsed) when the app shuts down, must be cancelled — not leaked as a
    dangling background task."""
    app = create_app(Settings(_env_file=None, DEV_BYPASS=True))
    with TestClient(app) as c:
        c.get("/shell/health")
        task = app.state.sweep_task
        assert task is not None and not task.done()
    assert task.cancelled() or task.done()


def test_sweep_scheduler_absent_when_limits_module_missing(monkeypatch):
    """Fail-open posture (same as every other _limits usage in main.py):
    if shell.app.limits isn't importable, app startup must not crash — it
    just doesn't schedule anything."""
    from shell.app import main as main_module

    monkeypatch.setattr(main_module, "_limits", None)
    app = create_app(Settings(_env_file=None, DEV_BYPASS=True))
    with TestClient(app) as c:
        assert c.get("/shell/health").status_code == 200
        assert app.state.sweep_task is None
