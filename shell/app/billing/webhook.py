"""shell/app/billing/webhook.py — Stripe webhook + checkout routes (Agent B).

Implements PRODUCTION_PLAN.md §2 ("Stripe billing + idempotent webhook") and
PRODUCTION_CRITERIA.md §C3: webhooks signature-verified; entitlement changes
ONLY via verified webhook or admin action.

Router (Agent A includes this in main.py):
    POST /shell/billing/webhook   — Stripe events (idempotent via audit_log)
    POST /shell/billing/checkout  — start hosted checkout for the Pro plan

Signature policy:
    * STRIPE_WEBHOOK_SECRET set        -> stripe.Webhook.construct_event, bad
                                          signature => 400.
    * secret absent AND ENV == "dev"   -> unsigned JSON accepted (keyless dev).
    * secret absent AND ENV != "dev"   -> 503; NEVER process unsigned events
                                          outside dev.

Idempotency: each Stripe event id is recorded in audit_log with a UNIQUE
dedup_key ("stripe_evt:<id>"); a replayed event is acknowledged with 200 but
performs no state change (webhook-loss recovery per PRODUCTION_PLAN §5 —
Stripe retries and replays are safe).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from shell.app import db
from shell.app.billing._contracts import UserCtx, get_settings
from shell.app.billing.stripe_client import create_checkout_session

router = APIRouter()

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def _epoch_to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


async def _verify_and_parse(request: Request) -> dict:
    payload = await request.body()
    settings = get_settings()
    secret = settings.stripe_webhook_secret

    if secret:
        signature = request.headers.get("stripe-signature")
        if not signature:
            raise HTTPException(status_code=400, detail="missing signature")
        try:
            import stripe

            event = stripe.Webhook.construct_event(payload, signature, secret)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid signature")
        return event.to_dict() if hasattr(event, "to_dict") else dict(event)

    if settings.env != "dev":
        # Never process unsigned webhooks outside dev (C3).
        raise HTTPException(status_code=503, detail="webhook secret not configured")
    try:
        parsed = json.loads(payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid payload")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    return parsed


async def _resolve_user_id(obj: dict) -> Optional[str]:
    metadata = obj.get("metadata") or {}
    user_id = obj.get("client_reference_id") or metadata.get("clerk_user_id")
    if user_id:
        return str(user_id)
    customer = obj.get("customer")
    if customer:
        return await db.get_user_by_customer(str(customer))
    return None


async def _handle_event(event: dict) -> str:
    """Apply one (already-deduplicated) Stripe event. Returns a disposition."""
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type not in HANDLED_EVENTS:
        return "ignored"

    user_id = await _resolve_user_id(obj)
    if not user_id:
        await db.audit(
            "stripe_webhook_orphan",
            actor="stripe",
            subject=str(obj.get("customer") or "unknown"),
            detail={"type": event_type, "object_id": obj.get("id")},
        )
        return "orphaned"

    await db.upsert_user(user_id, obj.get("customer_email"))

    if event_type == "checkout.session.completed":
        await db.apply_subscription_update(
            user_id,
            plan="pro",
            status="active",
            stripe_customer_id=str(obj["customer"]) if obj.get("customer") else None,
            stripe_subscription_id=(
                str(obj["subscription"]) if obj.get("subscription") else None
            ),
            current_period_end=None,  # authoritative value arrives with
            # customer.subscription.updated
        )
        return "applied"

    if event_type == "customer.subscription.updated":
        await db.apply_subscription_update(
            user_id,
            plan="pro",
            status=str(obj.get("status") or "active"),
            stripe_customer_id=str(obj["customer"]) if obj.get("customer") else None,
            stripe_subscription_id=str(obj["id"]) if obj.get("id") else None,
            current_period_end=_epoch_to_dt(obj.get("current_period_end")),
        )
        return "applied"

    # customer.subscription.deleted
    await db.apply_subscription_update(
        user_id,
        plan="pro",  # historical plan retained; status makes it resolve to free
        status="canceled",
        stripe_customer_id=str(obj["customer"]) if obj.get("customer") else None,
        stripe_subscription_id=str(obj["id"]) if obj.get("id") else None,
        current_period_end=_epoch_to_dt(obj.get("current_period_end")),
    )
    return "applied"


@router.post("/shell/billing/webhook")
@router.post("/shell/webhook/stripe")  # alias: the path Agent A's auth.py
# exempts from authentication (EXEMPT_PATHS) — Stripe posts unauthenticated,
# so this alias is what gets configured in the Stripe dashboard in real-auth
# deployments. Same handler, same idempotency ledger.
async def stripe_webhook(request: Request) -> dict:
    event = await _verify_and_parse(request)
    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event id missing")

    # Idempotency ledger: first writer wins; replays are acknowledged no-ops.
    fresh = await db.audit(
        "stripe_webhook",
        actor="stripe",
        subject=str(event_id),
        detail={"type": event.get("type")},
        dedup_key=f"stripe_evt:{event_id}",
    )
    if not fresh:
        return {"received": True, "duplicate": True, "disposition": "deduplicated"}

    disposition = await _handle_event(event)
    return {"received": True, "duplicate": False, "disposition": disposition}


@router.post("/shell/billing/checkout")
async def start_checkout(request: Request):
    settings = get_settings()
    user: Optional[UserCtx] = getattr(request.state, "user", None)
    if user is None:
        if settings.dev_bypass:
            user = UserCtx(
                user_id=request.headers.get("x-dev-user", "dev_user"),
                email=None,
                plan=request.headers.get("x-dev-plan", "free"),
            )
        else:
            return JSONResponse(
                status_code=401,
                content={"error": "auth_required", "sign_in_url": settings.base_url},
            )

    await db.upsert_user(user.user_id, user.email)
    session = await create_checkout_session(user)
    return {"url": session["url"], "session_id": session["id"], "mock": session.get("mock", False)}
