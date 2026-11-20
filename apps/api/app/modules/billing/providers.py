"""Payment provider adapters. NO real money moves in this codebase by default.

- `simulated`: clearly-labelled fake provider; marks the invoice paid with `simulated=True`. Disabled in production.
- `stripe` / `razorpay`: report `not_configured` unless credentials are present in the environment
  (STRIPE_SECRET_KEY; RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET). When configured they create a hosted checkout
  (Stripe Checkout Session / Razorpay Payment Link) and return its URL with status `pending`. The invoice is marked
  paid only when a signature-verified webhook arrives (see webhooks.py).
"""
import os
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings


@dataclass
class ChargeResult:
    status: str  # succeeded | pending | failed
    reference: str | None
    simulated: bool
    error: str | None = None
    checkout_url: str | None = None


def _return_url(path: str) -> str:
    base = (os.getenv("WEB_APP_URL") or "http://localhost:3010").rstrip("/")
    return f"{base}{path}"


class SimulatedProvider:
    name = "simulated"

    def status(self) -> str:
        return "disabled" if get_settings().is_production else "simulated"

    def charge(self, amount: Decimal, currency: str, invoice_number: str) -> ChargeResult:
        return ChargeResult("succeeded", f"sim_{invoice_number}", simulated=True)


class StripeProvider:
    name = "stripe"

    def status(self) -> str:
        return "configured" if os.getenv("STRIPE_SECRET_KEY") else "not_configured"

    def charge(self, amount: Decimal, currency: str, invoice_number: str) -> ChargeResult:
        try:
            r = httpx.post("https://api.stripe.com/v1/checkout/sessions", timeout=15,
                           auth=(os.environ["STRIPE_SECRET_KEY"], ""),
                           data={"mode": "payment",
                                 "line_items[0][quantity]": 1,
                                 "line_items[0][price_data][currency]": currency.lower(),
                                 "line_items[0][price_data][unit_amount]": int(amount * 100),
                                 "line_items[0][price_data][product_data][name]": f"Leadex invoice {invoice_number}",
                                 "metadata[invoice]": invoice_number,
                                 "success_url": _return_url("/billing?payment=success"),
                                 "cancel_url": _return_url("/billing?payment=cancelled")})
        except httpx.HTTPError as e:
            return ChargeResult("failed", None, False, f"stripe unreachable: {e.__class__.__name__}")
        if r.status_code >= 400:
            return ChargeResult("failed", None, False, f"stripe error {r.status_code}")
        body = r.json()
        return ChargeResult("pending", body.get("id"), False, checkout_url=body.get("url"))


class RazorpayProvider:
    name = "razorpay"

    def status(self) -> str:
        return "configured" if os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET") else "not_configured"

    def charge(self, amount: Decimal, currency: str, invoice_number: str) -> ChargeResult:
        try:
            r = httpx.post("https://api.razorpay.com/v1/payment_links", timeout=15,
                           auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]),
                           json={"amount": int(amount * 100), "currency": currency, "reference_id": invoice_number,
                                 "description": f"Leadex invoice {invoice_number}",
                                 "callback_url": _return_url("/billing?payment=success"),
                                 "callback_method": "get"})
        except httpx.HTTPError as e:
            return ChargeResult("failed", None, False, f"razorpay unreachable: {e.__class__.__name__}")
        if r.status_code >= 400:
            return ChargeResult("failed", None, False, f"razorpay error {r.status_code}")
        body = r.json()
        return ChargeResult("pending", body.get("id"), False, checkout_url=body.get("short_url"))


PROVIDERS = {p.name: p for p in (SimulatedProvider(), StripeProvider(), RazorpayProvider())}
