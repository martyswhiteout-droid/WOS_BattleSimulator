"""shell/app/billing/stripe_client.py — Stripe checkout client (Agent B).

Implements PRODUCTION_PLAN.md §2 "Stripe billing" and PRODUCTION_CRITERIA.md
§C3: payments via Stripe HOSTED checkout only — we never touch card data.

Mock-first (ARCHITECTURE.md rule 2): when STRIPE_SECRET_KEY is absent,
MockStripe returns deterministic fake session URLs so the full checkout flow
is testable keyless. Real keys switch to the stripe library transparently.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Optional

from shell.app.billing._contracts import UserCtx, get_settings


class MockStripe:
    """Keyless stand-in for Stripe hosted checkout (dev/staging without keys)."""

    def create_checkout_session(
        self,
        user: UserCtx,
        price_id: Optional[str],
        success_url: str,
        cancel_url: str,
    ) -> dict:
        seed = f"{user.user_id}:{price_id}:{time.time_ns()}"
        session_id = "cs_mock_" + hashlib.sha256(seed.encode()).hexdigest()[:24]
        base = get_settings().base_url.rstrip("/")
        return {
            "id": session_id,
            "url": f"{base}/shell/billing/mock-checkout?session_id={session_id}",
            "mock": True,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }


async def create_checkout_session(
    user: UserCtx,
    price_id: Optional[str] = None,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> dict:
    """Create a Stripe (or mock) hosted-checkout session for the Pro plan.

    Returns {"id", "url", "mock"} — the caller redirects the browser to
    `url`. client_reference_id + metadata carry the clerk_user_id so the
    webhook can attribute the completed checkout (C3: entitlement changes
    happen ONLY in the verified webhook, never here).
    """
    settings = get_settings()
    price = price_id or settings.stripe_price_id_pro
    base = settings.base_url.rstrip("/")
    success = success_url or f"{base}/?checkout=success"
    cancel = cancel_url or f"{base}/?checkout=cancel"

    if not settings.stripe_secret_key:
        return MockStripe().create_checkout_session(user, price, success, cancel)

    import stripe  # deferred import: keyless environments never need it

    stripe.api_key = settings.stripe_secret_key

    def _create():
        return stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price, "quantity": 1}],
            client_reference_id=user.user_id,
            customer_email=user.email,
            success_url=success,
            cancel_url=cancel,
            metadata={"clerk_user_id": user.user_id},
            subscription_data={"metadata": {"clerk_user_id": user.user_id}},
        )

    session = await asyncio.to_thread(_create)
    return {"id": session["id"], "url": session["url"], "mock": False}
