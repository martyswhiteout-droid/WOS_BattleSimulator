"""shell/app/billing/entitlements.py — plan resolution (Agent B).

Implements PRODUCTION_PLAN.md §2.2 (entitlements as single source of truth)
and PRODUCTION_CRITERIA.md §C2: SERVER-SIDE entitlement enforcement — the
client is never the thing deciding what a user may run.

resolve_plan(user_id) derives the effective plan from the subscriptions
table, which is updated ONLY by the verified Stripe webhook (§C3).

Contract (MORNING_BRIEF.md §Resume, Agent B; consumed by Agent A's auth.py
on every authenticated request, F3 in EVAL_ROUND_1.md):
    * exported     — re-exported from shell.app.billing (package root).
    * awaitable    — `async def`.
    * cached       — an in-process TTL cache avoids a DB round trip per
                      request; the Stripe webhook calls invalidate_plan_cache
                      after every subscription write so upgrades/downgrades
                      are visible on the NEXT request, not after the TTL.
    * never-raising — ANY backend failure (DB down, malformed row, ...)
                      degrades to "free" and is never cached, so a transient
                      blip self-heals on the next call instead of parking a
                      user on "free" for a whole TTL. Granting "pro" on a
                      failure is the one outcome this must never produce
                      (PRODUCTION_CRITERIA C2 — we do not charge for a
                      product we silently fail to deliver, and we do not
                      hand out the paid product on an error either).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from shell.app import db

log = logging.getLogger("wos.shell.entitlements")

#: Stripe subscription statuses that grant paid access.
ACTIVE_STATUSES = {"active", "trialing"}

#: How long a resolved plan is trusted before resolve_plan() re-checks the
#: subscriptions table. Short enough that a cache-only staleness window is
#: never the reason a paying user sees "free"; invalidate_plan_cache() (called
#: by the webhook on every write) covers the common case of an actual change.
_PLAN_CACHE_TTL_S = 30.0

#: user_id -> (plan, cached_at_monotonic). Process-local; fine for a
#: single-VPS deployment (ARCHITECTURE.md's target shape). Never holds a
#: failure result — see _resolve_plan_uncached's caller.
_plan_cache: dict[str, tuple[str, float]] = {}


def invalidate_plan_cache(user_id: Optional[str] = None) -> None:
    """Drop a cached plan (or, with no argument, every cached plan).

    Called by the Stripe webhook (billing/webhook.py) right after it writes
    a subscription change, and by db.reset_db() for test isolation — a
    user_id reused across tests must never see another test's cached plan.
    """
    if user_id is None:
        _plan_cache.clear()
    else:
        _plan_cache.pop(user_id, None)


async def resolve_plan(user_id: str) -> str:
    """Return "pro" or "free" for a user. See module docstring for the
    cached / never-raising contract."""
    cached = _plan_cache.get(user_id)
    if cached is not None:
        plan, cached_at = cached
        if (time.monotonic() - cached_at) < _PLAN_CACHE_TTL_S:
            return plan

    try:
        plan = await _resolve_plan_uncached(user_id)
    except Exception:
        # Never raise out of resolve_plan: a broken subscriptions lookup
        # must degrade the paywall, not the whole authenticated path.
        # Not cached — a transient failure must not outlive its cause.
        log.exception("resolve_plan(%r) failed; degrading to free", user_id)
        return "free"

    _plan_cache[user_id] = (plan, time.monotonic())
    return plan


async def _resolve_plan_uncached(user_id: str) -> str:
    sub = await db.get_subscription(user_id)
    if not sub:
        return "free"
    if sub.get("plan") != "pro":
        return "free"
    if (sub.get("status") or "").lower() not in ACTIVE_STATUSES:
        return "free"
    period_end = sub.get("current_period_end")
    if period_end is not None:
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        if period_end < datetime.now(timezone.utc):
            return "free"
    return "pro"


async def get_effective_entitlements(user_id: str) -> db.Entitlements:
    """Convenience for /shell/me-style endpoints: plan -> quota row."""
    return await db.get_entitlements(await resolve_plan(user_id))
