"""shell/app/billing/entitlements.py — plan resolution (Agent B).

Implements PRODUCTION_PLAN.md §2.2 (entitlements as single source of truth)
and PRODUCTION_CRITERIA.md §C2: SERVER-SIDE entitlement enforcement — the
client is never the thing deciding what a user may run.

resolve_plan(user_id) derives the effective plan from the subscriptions
table, which is updated ONLY by the verified Stripe webhook (§C3).
"""

from __future__ import annotations

from datetime import datetime, timezone

from shell.app import db

#: Stripe subscription statuses that grant paid access.
ACTIVE_STATUSES = {"active", "trialing"}


async def resolve_plan(user_id: str) -> str:
    """Return "pro" or "free" for a user, from subscription state alone."""
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
