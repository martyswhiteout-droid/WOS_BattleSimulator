"""shell.app.billing — Stripe billing + entitlements (Agent B).

Implements PRODUCTION_PLAN.md §2.2 (subscriptions/entitlements) and
PRODUCTION_CRITERIA.md §C3 (hosted checkout, signature-verified webhooks,
entitlement changes only via verified webhook or admin).

Exports ``router`` (checkout + webhook routes) because Agent A's main.py
auto-includes ``shell.app.billing.router`` when present.
"""

from shell.app.billing.webhook import router

__all__ = ["router"]
