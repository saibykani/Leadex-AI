"""Payment provider webhooks (public, signature-verified, idempotent).

* Stripe:   POST /api/v1/billing/webhooks/stripe    header `Stripe-Signature`, secret STRIPE_WEBHOOK_SECRET.
            Handles checkout.session.completed (paid) and checkout.session.expired / async_payment_failed.
* Razorpay: POST /api/v1/billing/webhooks/razorpay  header `X-Razorpay-Signature`, secret RAZORPAY_WEBHOOK_SECRET.
            Handles payment_link.paid and payment_link.cancelled / expired.

Without the secret the endpoint answers 503 and changes nothing. Each provider event id is recorded once
(billing_webhook_events), so replays are no-ops. The tenant is resolved from the payment's provider reference via
the narrow SECURITY DEFINER function billing_payment_org(); RLS then applies as normal.
"""
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.tenancy import audit
from app.modules.billing import service as svc
from app.modules.billing.models import BillingWebhookEvent, Invoice, Payment

router = APIRouter(prefix="/billing/webhooks", tags=["billing-webhooks"])
STRIPE_TOLERANCE_S = 300


def _secret(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise AppError(503, "webhook_not_configured", f"{name} is not set")
    return v


def verify_stripe(payload: bytes, header: str, secret: str, now: float | None = None) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    sigs = [p.split("=", 1)[1] for p in header.split(",") if p.startswith("v1=")]
    try:
        ts = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > STRIPE_TOLERANCE_S:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


def verify_razorpay(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _payment_org(db: Session, provider: str, reference: str):
    if db.bind.dialect.name == "postgresql":
        return db.scalar(text("SELECT billing_payment_org(:p, :r)"), {"p": provider, "r": reference})
    return db.scalar(select(Payment.organization_id).where(Payment.provider == provider,
                                                           Payment.provider_reference == reference))


def _apply(db: Session, request: Request, provider: str, event_id: str, event_type: str, reference: str | None,
           outcome: str | None) -> dict:
    try:
        db.add(BillingWebhookEvent(provider=provider, event_id=event_id, event_type=event_type))
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    if not reference or outcome is None:
        db.commit()
        return {"status": "ignored"}
    org = _payment_org(db, provider, reference)
    if org is None:
        db.commit()
        return {"status": "unknown_reference"}
    set_tenant(db, org)
    pay = db.scalar(select(Payment).where(Payment.organization_id == org, Payment.provider == provider,
                                          Payment.provider_reference == reference))
    inv = db.get(Invoice, pay.invoice_id)
    if outcome == "succeeded" and pay.status != "succeeded":
        pay.status = "succeeded"
        if inv.status == "open":
            inv.status, inv.paid_at = "paid", utcnow()
            sub = svc.get_subscription(db, org)
            if sub.status == "past_due":
                sub.status = "active"
    elif outcome == "failed" and pay.status == "pending":
        pay.status, pay.error = "failed", event_type
    audit(db, "billing.webhook", org_id=org, user_id=None, entity_type="payment", entity_id=pay.id,
          data={"provider": provider, "event": event_type, "outcome": outcome}, request=request)
    db.commit()
    return {"status": "processed", "outcome": outcome}


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    secret = _secret("STRIPE_WEBHOOK_SECRET")
    payload = await request.body()
    if not verify_stripe(payload, request.headers.get("stripe-signature", ""), secret):
        raise AppError(400, "invalid_signature", "Webhook signature verification failed")
    ev = json.loads(payload)
    obj = (ev.get("data") or {}).get("object") or {}
    kind = ev.get("type", "")
    outcome = {"checkout.session.completed": "succeeded" if obj.get("payment_status") == "paid" else None,
               "checkout.session.async_payment_succeeded": "succeeded",
               "checkout.session.async_payment_failed": "failed",
               "checkout.session.expired": "failed"}.get(kind)
    return _apply(db, request, "stripe", ev.get("id", ""), kind, obj.get("id"), outcome)


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    secret = _secret("RAZORPAY_WEBHOOK_SECRET")
    payload = await request.body()
    if not verify_razorpay(payload, request.headers.get("x-razorpay-signature", ""), secret):
        raise AppError(400, "invalid_signature", "Webhook signature verification failed")
    ev = json.loads(payload)
    kind = ev.get("event", "")
    link = ((ev.get("payload") or {}).get("payment_link") or {}).get("entity") or {}
    outcome = {"payment_link.paid": "succeeded", "payment_link.cancelled": "failed",
               "payment_link.expired": "failed"}.get(kind)
    event_id = request.headers.get("x-razorpay-event-id") or f"{kind}:{link.get('id')}"
    return _apply(db, request, "razorpay", event_id, kind, link.get("id"), outcome)
