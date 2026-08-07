"""Tests for shell/app/limits.py check_and_record + LimitsMiddleware (Agent B).

Keyless (InMemoryDB). Covers the contract denials exactly:
    400 below_min_troops · 402 payment_required · 429 quota_exhausted / burst
plus per-IP daily caps and safe body restore in the middleware.
"""

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from shell.app import db, limits
from shell.app.billing._contracts import UserCtx

run = asyncio.run

ENV_KEYS = [
    "DATABASE_URL", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "DEV_BYPASS",
    "ENV", "MIN_TROOPS_PER_SIDE", "FREE_SIMS_PER_DAY", "PRO_SIMS_PER_DAY",
    "PRO_OCR_PER_DAY", "BURST_PER_MIN", "SWEEP_MIN_EVENTS", "IP_HASH_SALT",
    "BASE_URL", "GLOBAL_CONCURRENCY", "STRIPE_PRICE_ID_PRO",
    "CLERK_SECRET_KEY", "CLERK_PUBLISHABLE_KEY", "CLERK_JWKS_URL",
]


@pytest.fixture(autouse=True)
def keyless_env(monkeypatch):
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)
    db.reset_db()
    yield
    db.reset_db()


FREE = UserCtx(user_id="free_user", email=None, plan="free")
PRO = UserCtx(user_id="pro_user", email=None, plan="pro")


def sim_body(own=50000, enemy=60000):
    return {"own": {"troops_total": own}, "enemy": {"troops_total": enemy}}


# ---------------------------------------------------------------------------
# MIN_TROOPS (D1): 4999 -> 400, 5000 -> pass
# ---------------------------------------------------------------------------

def test_min_troops_4999_denied_400():
    verdict = run(
        limits.check_and_record(FREE, "/api/predict", sim_body(own=4999), "ip1")
    )
    assert isinstance(verdict, limits.Denied)
    assert verdict.status == 400 and verdict.code == "below_min_troops"


def test_min_troops_enemy_side_also_enforced():
    verdict = run(
        limits.check_and_record(FREE, "/api/battle", sim_body(enemy=4999), "ip1")
    )
    assert isinstance(verdict, limits.Denied) and verdict.status == 400


def test_min_troops_5000_passes():
    verdict = run(
        limits.check_and_record(FREE, "/api/predict", sim_body(own=5000, enemy=5000), "ip1")
    )
    assert isinstance(verdict, limits.Allowed)


def test_missing_or_malformed_troops_denied_400_not_500():
    for body in [None, {}, {"own": {}}, {"own": {"troops_total": "lots"}},
                 {"own": {"troops_total": True}, "enemy": {"troops_total": 9000}}]:
        verdict = run(limits.check_and_record(FREE, "/api/predict", body, "ip1"))
        assert isinstance(verdict, limits.Denied), body
        assert verdict.status == 400 and verdict.code == "below_min_troops"


def test_denied_requests_consume_no_quota():
    for _ in range(10):
        run(limits.check_and_record(FREE, "/api/predict", sim_body(own=1), "ip1"))
    assert run(db.get_usage_today(FREE.user_id, "sim")) == 0


# ---------------------------------------------------------------------------
# Daily quota (D2): free plan exhausts at the 6th sim
# ---------------------------------------------------------------------------

def test_free_quota_exhausts_at_sixth_sim():
    for i in range(5):
        verdict = run(
            limits.check_and_record(FREE, "/api/predict", sim_body(own=50000 + i * 10000), "ip1")
        )
        assert isinstance(verdict, limits.Allowed), f"sim {i + 1} should be allowed"
    sixth = run(limits.check_and_record(FREE, "/api/predict", sim_body(), "ip1"))
    assert isinstance(sixth, limits.Denied)
    assert sixth.status == 429 and sixth.code == "quota_exhausted"


def test_pro_quota_is_100_not_5():
    # 6th sim fine on pro (spread over time to stay under burst)
    backend = db.get_db()
    for i in range(5):
        run(db.record_usage(PRO.user_id, endpoint="/api/predict", kind="sim",
                            ts=db._utcnow() - db.timedelta(minutes=10 + i)))
    verdict = run(limits.check_and_record(PRO, "/api/predict", sim_body(), "ip9"))
    assert isinstance(verdict, limits.Allowed)
    assert len(backend.usage_events) == 6


# ---------------------------------------------------------------------------
# OCR paywall (402 payment_required on free; metered on pro)
# ---------------------------------------------------------------------------

def test_ocr_denied_402_on_free_plan():
    verdict = run(limits.check_and_record(FREE, "/shell/ocr", None, "ip1"))
    assert isinstance(verdict, limits.Denied)
    assert verdict.status == 402 and verdict.code == "payment_required"


def test_ocr_allowed_on_pro_until_daily_quota(monkeypatch):
    # Freeze the DB clock mid-day: the backdated rows below must land on the
    # SAME UTC day as the quota check. With the real clock this test fails
    # whenever it runs within ~34 minutes after UTC midnight (the backdated
    # timestamps cross into yesterday) — time-of-day flake found 2026-08-07.
    from datetime import datetime as _dt, timezone as _tz
    monkeypatch.setattr(db, "_utcnow", lambda: _dt(2026, 8, 7, 12, 0, 0, tzinfo=_tz.utc))
    verdict = run(limits.check_and_record(PRO, "/shell/ocr", None, "ip1"))
    assert isinstance(verdict, limits.Allowed)
    # exhaust the remaining 29 (backdated to dodge the burst window)
    for i in range(29):
        run(db.record_usage(PRO.user_id, endpoint="/shell/ocr", kind="ocr",
                            ts=db._utcnow() - db.timedelta(minutes=5 + i)))
    verdict = run(limits.check_and_record(PRO, "/shell/ocr", None, "ip1"))
    assert isinstance(verdict, limits.Denied)
    assert verdict.status == 429 and verdict.code == "quota_exhausted"


# ---------------------------------------------------------------------------
# Burst (<= BURST_PER_MIN sliding 60s window) -> 429 burst
# ---------------------------------------------------------------------------

def test_burst_sixth_rapid_request_denied():
    for i in range(5):
        verdict = run(limits.check_and_record(PRO, "/api/predict", sim_body(own=50000 + i * 10000), "ip1"))
        assert isinstance(verdict, limits.Allowed)
    sixth = run(limits.check_and_record(PRO, "/api/predict", sim_body(), "ip1"))
    assert isinstance(sixth, limits.Denied)
    assert sixth.status == 429 and sixth.code == "burst"


def test_burst_window_slides():
    # 5 events well in the past: window empty again
    for i in range(5):
        run(db.record_usage(PRO.user_id, endpoint="/api/predict", kind="sim",
                            ts=db._utcnow() - db.timedelta(seconds=90 + i)))
    verdict = run(limits.check_and_record(PRO, "/api/predict", sim_body(), "ip1"))
    assert isinstance(verdict, limits.Allowed)


# ---------------------------------------------------------------------------
# Per-IP daily cap = 3x account cap (C5: burner accounts)
# ---------------------------------------------------------------------------

def test_ip_daily_cap_three_times_account_cap():
    shared_ip = "ip_shared"
    for n in range(3):  # three free burner accounts fill 3 x 5 = 15
        user = UserCtx(user_id=f"burner_{n}", email=None, plan="free")
        for i in range(5):
            verdict = run(
                limits.check_and_record(
                    user, "/api/predict", sim_body(own=50000 + i * 10000), shared_ip
                )
            )
            assert isinstance(verdict, limits.Allowed)
    fresh = UserCtx(user_id="burner_3", email=None, plan="free")
    verdict = run(limits.check_and_record(fresh, "/api/predict", sim_body(), shared_ip))
    assert isinstance(verdict, limits.Denied)
    assert verdict.status == 429 and verdict.code == "quota_exhausted"
    # same fresh account from a different IP is fine (account quota untouched)
    verdict = run(limits.check_and_record(fresh, "/api/predict", sim_body(), "ip_other"))
    assert isinstance(verdict, limits.Allowed)


# ---------------------------------------------------------------------------
# Unmetered endpoints pass through without recording
# ---------------------------------------------------------------------------

def test_unmetered_endpoint_allowed_and_unrecorded():
    verdict = run(limits.check_and_record(FREE, "/shell/billing/checkout", {}, "ip1"))
    assert isinstance(verdict, limits.Allowed)
    assert db.get_db().usage_events == []


# ---------------------------------------------------------------------------
# LimitsMiddleware: body restored downstream; denials returned as JSON
# ---------------------------------------------------------------------------

def make_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DEV_BYPASS", "1")
    app = FastAPI()

    @app.post("/api/predict")
    async def predict(request: Request):  # pragma: no cover - exercised via client
        data = await request.json()
        return {"echo_own": data["own"]["troops_total"]}

    return TestClient(limits.LimitsMiddleware(app))


def test_middleware_restores_body_for_downstream(monkeypatch):
    client = make_client(monkeypatch)
    resp = client.post("/api/predict", json=sim_body(own=7000, enemy=8000))
    assert resp.status_code == 200
    assert resp.json() == {"echo_own": 7000}


def test_middleware_denies_min_troops_with_json_error(monkeypatch):
    client = make_client(monkeypatch)
    resp = client.post("/api/predict", json=sim_body(own=4999))
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"] == "below_min_troops" and "5,000" in payload["message"]


def test_middleware_quota_and_plan_headers(monkeypatch):
    client = make_client(monkeypatch)
    headers = {"X-Dev-User": "mw_free"}
    for i in range(5):
        resp = client.post(
            "/api/predict", json=sim_body(own=50000 + i * 10000), headers=headers
        )
        assert resp.status_code == 200
    resp = client.post("/api/predict", json=sim_body(), headers=headers)
    assert resp.status_code == 429
    assert resp.json()["error"] == "quota_exhausted"


def test_middleware_ignores_non_metered_paths(monkeypatch):
    monkeypatch.setenv("DEV_BYPASS", "1")
    app = FastAPI()

    @app.get("/api/health")
    async def health():  # pragma: no cover - exercised via client
        return {"ok": True}

    client = TestClient(limits.LimitsMiddleware(app))
    assert client.get("/api/health").status_code == 200
    assert db.get_db().usage_events == []
