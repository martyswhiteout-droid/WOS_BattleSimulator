"""Tests for shell/app/billing/* (Agent B) — keyless.

Covers: mock checkout session URLs, webhook signature policy, IDEMPOTENT
event handling (same event twice = exactly one state change), subscription
lifecycle -> resolve_plan, and the checkout route.
"""

import asyncio
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shell.app import db
from shell.app.billing import entitlements as ent_mod
from shell.app.billing._contracts import UserCtx
from shell.app.billing.stripe_client import create_checkout_session
from shell.app.billing.webhook import router

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


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def checkout_completed_event(event_id="evt_1", user_id="user_A"):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "customer": "cus_1",
                "subscription": "sub_1",
                "client_reference_id": user_id,
                "customer_email": "a@example.com",
                "metadata": {},
            }
        },
    }


# ---------------------------------------------------------------------------
# Mock checkout (keyless)
# ---------------------------------------------------------------------------

def test_mock_checkout_session_when_no_stripe_key():
    user = UserCtx(user_id="u1", email="u1@example.com", plan="free")
    session = run(create_checkout_session(user))
    assert session["mock"] is True
    assert session["id"].startswith("cs_mock_")
    assert session["url"].startswith("http://localhost:8200/shell/billing/mock-checkout")
    assert "session_id=" in session["url"]


def test_checkout_route_dev_bypass_returns_mock_url(monkeypatch):
    monkeypatch.setenv("DEV_BYPASS", "1")
    client = make_client()
    resp = client.post("/shell/billing/checkout", headers={"X-Dev-User": "u42"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mock"] is True and "mock-checkout" in body["url"]
    assert run(db.get_db().upsert_user("u42"))  # user row was created


def test_checkout_route_requires_auth_outside_dev_bypass(monkeypatch):
    # Agent A's config auto-enables DEV_BYPASS when no Clerk key is set,
    # so pin it OFF to exercise the real-auth branch.
    monkeypatch.setenv("DEV_BYPASS", "0")
    client = make_client()
    resp = client.post("/shell/billing/checkout")
    assert resp.status_code == 401
    assert resp.json()["error"] == "auth_required"


# ---------------------------------------------------------------------------
# Webhook: signature policy
# ---------------------------------------------------------------------------

def test_unsigned_webhook_accepted_only_in_dev():
    client = make_client()  # ENV defaults to dev; no secret configured
    resp = client.post("/shell/billing/webhook", json=checkout_completed_event())
    assert resp.status_code == 200


def test_unsigned_webhook_rejected_outside_dev(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    client = make_client()
    resp = client.post("/shell/billing/webhook", json=checkout_completed_event())
    assert resp.status_code == 503


def test_bad_signature_rejected_when_secret_configured(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    client = make_client()
    # no signature header
    resp = client.post("/shell/billing/webhook", json=checkout_completed_event())
    assert resp.status_code == 400
    # bogus signature header
    resp = client.post(
        "/shell/billing/webhook",
        json=checkout_completed_event(),
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Webhook: idempotency (same event twice = ONE update)
# ---------------------------------------------------------------------------

def test_webhook_idempotent_replay_is_noop():
    client = make_client()
    event = checkout_completed_event()

    first = client.post("/shell/billing/webhook", json=event)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    sub = run(db.get_subscription("user_A"))
    assert sub["plan"] == "pro" and sub["status"] == "active"

    # Tamper with state between deliveries: a true replay must NOT re-apply.
    run(db.apply_subscription_update("user_A", plan="pro", status="canceled"))

    second = client.post("/shell/billing/webhook", json=event)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    sub = run(db.get_subscription("user_A"))
    assert sub["status"] == "canceled", "replayed event must not update state again"

    ledger = run(db.get_audit_entries("stripe_webhook", "evt_1"))
    assert len(ledger) == 1


# ---------------------------------------------------------------------------
# Webhook: subscription lifecycle -> resolve_plan
# ---------------------------------------------------------------------------

def test_checkout_completed_grants_pro():
    client = make_client()
    client.post("/shell/billing/webhook", json=checkout_completed_event())
    assert run(ent_mod.resolve_plan("user_A")) == "pro"


def test_subscription_updated_sets_period_end_and_status():
    client = make_client()
    client.post("/shell/billing/webhook", json=checkout_completed_event())
    future = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    updated = {
        "id": "evt_2",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",  # resolved via stripe_customer_id mapping
                "status": "active",
                "current_period_end": future,
                "metadata": {},
            }
        },
    }
    resp = client.post("/shell/billing/webhook", json=updated)
    assert resp.status_code == 200 and resp.json()["disposition"] == "applied"
    sub = run(db.get_subscription("user_A"))
    assert sub["current_period_end"] is not None
    assert run(ent_mod.resolve_plan("user_A")) == "pro"


def test_subscription_deleted_downgrades_to_free():
    client = make_client()
    client.post("/shell/billing/webhook", json=checkout_completed_event())
    assert run(ent_mod.resolve_plan("user_A")) == "pro"
    deleted = {
        "id": "evt_3",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "canceled",
                "metadata": {},
            }
        },
    }
    client.post("/shell/billing/webhook", json=deleted)
    assert run(ent_mod.resolve_plan("user_A")) == "free"


def test_expired_period_end_resolves_free():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    run(
        db.apply_subscription_update(
            "user_B", plan="pro", status="active", current_period_end=past
        )
    )
    assert run(ent_mod.resolve_plan("user_B")) == "free"


def test_unknown_user_never_subscribed_is_free():
    assert run(ent_mod.resolve_plan("ghost")) == "free"


def test_orphan_event_acknowledged_but_audited():
    client = make_client()
    orphan = {
        "id": "evt_orphan",
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_x", "customer": "cus_unknown",
                            "status": "active", "metadata": {}}},
    }
    resp = client.post("/shell/billing/webhook", json=orphan)
    assert resp.status_code == 200
    assert resp.json()["disposition"] == "orphaned"
    assert run(db.get_audit_entries("stripe_webhook_orphan"))


def test_unhandled_event_type_ignored():
    client = make_client()
    resp = client.post(
        "/shell/billing/webhook",
        json={"id": "evt_9", "type": "invoice.paid", "data": {"object": {}}},
    )
    assert resp.status_code == 200 and resp.json()["disposition"] == "ignored"


def test_event_without_id_rejected_400():
    client = make_client()
    resp = client.post(
        "/shell/billing/webhook", json={"type": "checkout.session.completed"}
    )
    assert resp.status_code == 400
