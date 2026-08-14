"""shell.app.billing — Stripe billing + entitlements (Agent B).

Implements PRODUCTION_PLAN.md §2.2 (subscriptions/entitlements) and
PRODUCTION_CRITERIA.md §C3 (hosted checkout, signature-verified webhooks,
entitlement changes only via verified webhook or admin).

Exports ``router`` (checkout + webhook routes) because Agent A's main.py
auto-includes ``shell.app.billing.router`` when present.

Also exports ``resolve_plan``/``invalidate_plan_cache`` (entitlements.py) at
the package root so Agent A's auth.py has one stable import point:
``from shell.app.billing import resolve_plan``.
"""

from shell.app.billing.entitlements import invalidate_plan_cache, resolve_plan
from shell.app.billing.webhook import router

__all__ = ["router", "resolve_plan", "invalidate_plan_cache"]
