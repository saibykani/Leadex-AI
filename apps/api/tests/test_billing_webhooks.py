import hashlib
import hmac
import json
import time

import httpx

from app.modules.billing import providers
from tests.conftest import register, tenant_headers

B = "/api/v1/billing"


class _Resp:
    def __init__(self, body):
        self.status_code, self._b = 200, body

    def json(self):
        return self._b


def _open_invoice(client, monkeypatch, provider, ref, url):
    a = register(client, f"Hook {provider}")
    h = tenant_headers(a)
    inv = client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"}).json()["invoice"]
    monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: _Resp({"id": ref, "url": url, "short_url": url}))
    p = client.post(f"{B}/invoices/{inv['id']}/pay", headers=h, json={"provider": provider})
    assert p.status_code == 200, p.text
    assert p.json()["status"] == "pending" and p.json()["checkout_url"] == url
    return h, inv


def _post(client, path, body, hdr):
    return client.post(f"{B}/webhooks/{path}", content=body, headers=hdr)


def _stripe_sig(body: bytes, secret: str, ts=None):
    ts = ts or int(time.time())
    return f"t={ts},v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def test_stripe_checkout_webhook_marks_paid_once(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    h, inv = _open_invoice(client, monkeypatch, "stripe", "cs_test_123", "https://checkout.stripe.test/cs_test_123")
    body = json.dumps({"id": "evt_1", "type": "checkout.session.completed",
                       "data": {"object": {"id": "cs_test_123", "payment_status": "paid"}}}).encode()
    # bad signature / stale timestamp rejected
    assert _post(client, "stripe", body, {"Stripe-Signature": "t=1,v1=bad"}).status_code == 400
    stale = _stripe_sig(body, "whsec_test", ts=int(time.time()) - 3600)
    assert _post(client, "stripe", body, {"Stripe-Signature": stale}).status_code == 400
    r = _post(client, "stripe", body, {"Stripe-Signature": _stripe_sig(body, "whsec_test")})
    assert r.status_code == 200 and r.json()["status"] == "processed", r.text
    again = _post(client, "stripe", body, {"Stripe-Signature": _stripe_sig(body, "whsec_test")})
    assert again.json()["status"] == "duplicate"
    invs = {i["id"]: i for i in client.get(f"{B}/invoices", headers=h).json()["items"]}
    assert invs[inv["id"]]["status"] == "paid"


def test_razorpay_link_webhook(client, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "rzp_hook")
    h, inv = _open_invoice(client, monkeypatch, "razorpay", "plink_1", "https://rzp.io/i/abc")
    body = json.dumps({"event": "payment_link.paid",
                       "payload": {"payment_link": {"entity": {"id": "plink_1"}}}}).encode()
    sig = hmac.new(b"rzp_hook", body, hashlib.sha256).hexdigest()
    assert _post(client, "razorpay", body, {"X-Razorpay-Signature": "0" * 64}).status_code == 400
    r = client.post(f"{B}/webhooks/razorpay", content=body,
                    headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_r1"})
    assert r.json()["status"] == "processed"
    invs = {i["id"]: i for i in client.get(f"{B}/invoices", headers=h).json()["items"]}
    assert invs[inv["id"]]["status"] == "paid"


def test_webhook_without_secret_is_refused(client, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    assert _post(client, "stripe", b"{}", {"Stripe-Signature": "t=1,v1=x"}).status_code == 503


def test_unknown_reference_is_ignored(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    body = json.dumps({"id": "evt_x", "type": "checkout.session.completed",
                       "data": {"object": {"id": "cs_nope", "payment_status": "paid"}}}).encode()
    r = _post(client, "stripe", body, {"Stripe-Signature": _stripe_sig(body, "whsec_test")})
    assert r.json()["status"] == "unknown_reference"


assert httpx  # imported so monkeypatch target exists
