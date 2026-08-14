"""Tests for shell/app/billing/entitlements.py (Agent B) — keyless.

Covers the resolve_plan() contract required by shell/ARCHITECTURE.md +
MORNING_BRIEF.md §Resume (Agent B): exported, awaitable, CACHED, and NEVER
raising — any backend failure must degrade to "free", never propagate and
never silently grant "pro" (PRODUCTION_CRITERIA C2). Agent A's auth.py wires
this in on every authenticated request (F3, EVAL_ROUND_1.md), so an
uncached/raising resolve_plan would either hammer the DB per-request or take
the shell down on a transient DB blip.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from shell.app import db
from shell.app.billing import entitlements as ent_mod

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


# ---------------------------------------------------------------------------
# Exported
# ---------------------------------------------------------------------------

def test_resolve_plan_exported_from_billing_package():
    """Agent A imports this from the package root, not the submodule."""
    from shell.app.billing import resolve_plan as pkg_resolve_plan

    assert pkg_resolve_plan is ent_mod.resolve_plan


def test_resolve_plan_is_awaitable():
    import inspect

    assert inspect.iscoroutinefunction(ent_mod.resolve_plan)


# ---------------------------------------------------------------------------
# Cached
# ---------------------------------------------------------------------------

def test_resolve_plan_caches_and_does_not_refetch(monkeypatch):
    calls = {"n": 0}
    real_get_subscription = db.get_subscription

    async def counting_get_subscription(user_id):
        calls["n"] += 1
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", counting_get_subscription)

    assert run(ent_mod.resolve_plan("cache_user")) == "free"
    assert run(ent_mod.resolve_plan("cache_user")) == "free"
    assert run(ent_mod.resolve_plan("cache_user")) == "free"
    assert calls["n"] == 1, "resolve_plan must serve repeat calls from cache"


def test_resolve_plan_cache_is_per_user(monkeypatch):
    calls = {"n": 0}
    real_get_subscription = db.get_subscription

    async def counting_get_subscription(user_id):
        calls["n"] += 1
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", counting_get_subscription)

    run(ent_mod.resolve_plan("user_1"))
    run(ent_mod.resolve_plan("user_2"))
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# Never-raising
# ---------------------------------------------------------------------------

def test_resolve_plan_never_raises_degrades_to_free(monkeypatch):
    async def boom(user_id):
        raise RuntimeError("subscriptions table unreachable")

    monkeypatch.setattr(db, "get_subscription", boom)

    # Must NOT raise — a paying-customer-lookout that crashes the request
    # path is worse than one that fails closed to "free" (PRODUCTION_CRITERIA
    # C2: never grant "pro" on a backend failure).
    assert run(ent_mod.resolve_plan("doomed_user")) == "free"


def test_resolve_plan_failure_is_not_cached(monkeypatch):
    """A transient DB blip must not lock a user out of pro for the whole TTL:
    only successful resolutions are cached."""
    state = {"fail": True}
    real_get_subscription = db.get_subscription

    async def flaky(user_id):
        if state["fail"]:
            raise RuntimeError("transient")
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", flaky)

    assert run(ent_mod.resolve_plan("flaky_user")) == "free"  # degrades, uncached

    state["fail"] = False
    run(
        db.apply_subscription_update(
            "flaky_user", plan="pro", status="active"
        )
    )
    ent_mod.invalidate_plan_cache("flaky_user")  # DB write path invalidates too
    assert run(ent_mod.resolve_plan("flaky_user")) == "pro"


# ---------------------------------------------------------------------------
# Cache invalidation (webhook-driven — see test_billing_webhook.py for the
# end-to-end route-level version)
# ---------------------------------------------------------------------------

def test_invalidate_plan_cache_forces_a_fresh_read(monkeypatch):
    calls = {"n": 0}
    real_get_subscription = db.get_subscription

    async def counting_get_subscription(user_id):
        calls["n"] += 1
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", counting_get_subscription)

    run(ent_mod.resolve_plan("u"))
    run(ent_mod.resolve_plan("u"))
    assert calls["n"] == 1

    ent_mod.invalidate_plan_cache("u")
    run(ent_mod.resolve_plan("u"))
    assert calls["n"] == 2


def test_invalidate_plan_cache_with_no_args_clears_everything(monkeypatch):
    calls = {"n": 0}
    real_get_subscription = db.get_subscription

    async def counting_get_subscription(user_id):
        calls["n"] += 1
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", counting_get_subscription)

    run(ent_mod.resolve_plan("a"))
    run(ent_mod.resolve_plan("b"))
    assert calls["n"] == 2

    ent_mod.invalidate_plan_cache()
    run(ent_mod.resolve_plan("a"))
    run(ent_mod.resolve_plan("b"))
    assert calls["n"] == 4


def test_db_reset_db_also_clears_the_plan_cache(monkeypatch):
    """Test isolation: db.reset_db() is the standard per-test hygiene call
    used across every shell test file. If it left a stale plan cached, a
    user_id reused across two tests (e.g. "user_A" in test_billing_webhook.py)
    could leak a plan resolution from one test into the next."""
    calls = {"n": 0}
    real_get_subscription = db.get_subscription

    async def counting_get_subscription(user_id):
        calls["n"] += 1
        return await real_get_subscription(user_id)

    monkeypatch.setattr(db, "get_subscription", counting_get_subscription)

    run(ent_mod.resolve_plan("reset_user"))
    assert calls["n"] == 1

    db.reset_db()
    run(ent_mod.resolve_plan("reset_user"))
    assert calls["n"] == 2, "reset_db() must drop cached plan resolutions too"
