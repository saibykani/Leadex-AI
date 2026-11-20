import hashlib
import hmac
import json
import uuid

import httpx
import pytest

from app.core.config import Settings
from app.core.db import tenant_session
from app.modules.communication import service as comm
from tests.conftest import register, tenant_headers

C = "/api/v1/campaigns"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SMTP_HOST", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MS_CLIENT_ID", "MS_CLIENT_SECRET",
              "WA_ACCESS_TOKEN", "WA_APP_SECRET", "WA_VERIFY_TOKEN", "EMAIL_WEBHOOK_SECRET", "OLLAMA_URL"):
        monkeypatch.delenv(k, raising=False)
    yield
    comm.set_transport(None)


def _lead(client, h, approved=True, **kw):
    body = {"business_name": "Sunrise Dental", "country": "IN", "email": f"o-{uuid.uuid4().hex[:6]}@shop.example",
            "phone": f"+91 98{uuid.uuid4().int % 10**8:08d}", **kw}
    r = client.post("/api/v1/leads", headers=h, json=body)
    assert r.status_code == 201, r.text
    lead = r.json()
    if approved:
        r = client.post(f"/api/v1/leads/{lead['id']}/status", headers=h, json={"status": "verified"})
        assert r.status_code == 200
        r = client.post(f"/api/v1/leads/{lead['id']}/status", headers=h,
                        json={"status": "approved_for_outreach", "consent_reference": "form-1"})
        assert r.status_code == 200, r.text
        for ch in ("email", "whatsapp"):
            r = client.post("/api/v1/compliance/consents", headers=h, json={
                "lead_id": lead["id"], "channel": ch, "basis": "express_consent", "evidence_text": "web form"})
            assert r.status_code == 201, r.text
    lead = client.get(f"/api/v1/leads/{lead['id']}", headers=h).json()
    lead["email_normalized"] = lead["email"].lower()
    lead["phone_normalized"] = "".join(ch for ch in lead["phone"] if ch.isdigit())
    return lead


def _template(client, h, **kw):
    r = client.post("/api/v1/email/templates", headers=h, json={
        "name": "Intro", "subject": "Hi {{business_name}}",
        "html": "<p>Hello {{business_name}}</p><script>alert(1)</script><a href='x' onclick='y()'>a</a>",
        "text": "Hello {{business_name}} see {{website_preview_url}}", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _email_campaign(client, h, leads, steps=None):
    t = _template(client, h)
    r = client.post(C, headers=h, json={"name": "Spring", "channel": "email", "email": {
        "steps": steps or [{"template_id": t["id"], "delay_hours": 0}, {"template_id": t["id"], "delay_hours": 48}],
        "physical_address": "1 Market St, Pune", "website_preview_base_url": "https://p.example/{lead_id}"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = client.post(f"{C}/{cid}/recipients", headers=h, json={"lead_ids": [x["id"] for x in leads]})
    assert r.status_code == 200, r.text
    return cid


def _approve(client, h, cid):
    assert client.post(f"{C}/{cid}/submit", headers=h).status_code == 200
    r = client.post(f"{C}/{cid}/approval", headers=h, json={"decision": "approved"})
    assert r.status_code == 200, r.text  # single-member org may self-approve


def test_template_sanitized_and_preview(client):
    a = register(client, "Comm Tpl")
    h = tenant_headers(a)
    t = _template(client, h)
    assert "<script" not in t["html"] and "onclick" not in t["html"]
    assert t["variables"] == ["business_name", "website_preview_url"]
    r = client.post("/api/v1/email/templates/preview", headers=h, json={
        "subject": "Hi {{business_name}}", "html": "<p>{{business_name}} {{owner}}</p>",
        "sample": {"business_name": "<b>Evil</b>"}})
    p = r.json()
    assert "&lt;b&gt;Evil" in p["html"] and "Unsubscribe" in p["html"]
    assert "[Physical mailing address required]" in p["html"] and p["missing_variables"] == ["owner"]


def test_cross_tenant_404_and_rbac(client):
    a, b = register(client, "Comm A"), register(client, "Comm B")
    ha = tenant_headers(a)
    cid = _email_campaign(client, ha, [_lead(client, ha)])
    hb = tenant_headers(b)
    assert client.get(f"{C}/{cid}", headers=hb).status_code == 404
    assert client.post(f"{C}/{cid}/submit", headers=hb).status_code == 404
    tid = client.get("/api/v1/email/templates", headers=ha).json()[0]["id"]
    assert client.get(f"/api/v1/email/templates/{tid}", headers=hb).status_code == 404
    # Sales Rep: no campaigns:write / campaigns:approve
    rep = register(client, "Comm Rep Home")
    r = client.post(f"/api/v1/organizations/{a['org_id']}/members", headers=a["headers"],
                    json={"email": rep["email"], "role": "Sales Rep"})
    assert r.status_code == 201, r.text
    hr = tenant_headers(rep, a["org_id"])
    assert client.get(f"{C}/{cid}", headers=hr).status_code == 200
    assert client.post(C, headers=hr, json={"name": "x", "channel": "email"}).status_code == 403
    assert client.post(f"{C}/{cid}/submit", headers=hr).status_code == 403
    assert client.post(f"{C}/{cid}/approval", headers=hr, json={"decision": "approved"}).status_code == 403
    # Now 2 members: the creator can no longer self-approve (four-eyes)
    assert client.post(f"{C}/{cid}/submit", headers=ha).status_code == 200
    r = client.post(f"{C}/{cid}/approval", headers=ha, json={"decision": "approved"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "four_eyes_required"


def test_cannot_start_before_approval_and_idempotency(client):
    a = register(client, "Comm Start")
    h = tenant_headers(a)
    good, unapproved = _lead(client, h), _lead(client, h, approved=False, business_name="Moon Cafe")
    cid = _email_campaign(client, h, [good, unapproved])
    k = {**h, "Idempotency-Key": "start-1"}
    assert client.post(f"{C}/{cid}/start", headers=k).status_code == 409  # draft
    assert client.post(f"{C}/{cid}/submit", headers=h).status_code == 200
    assert client.post(f"{C}/{cid}/start", headers={**h, "Idempotency-Key": "s-0"}).status_code == 409
    assert client.post(f"{C}/{cid}/approval", headers=h, json={"decision": "approved"}).status_code == 200
    assert client.post(f"{C}/{cid}/start", headers=h).status_code == 400  # header required
    r1 = client.post(f"{C}/{cid}/start", headers=k)
    assert r1.status_code == 200, r1.text
    assert r1.json()["dispatched"] == {"simulated": 1, "blocked": 1} and r1.json()["replayed"] is False
    r2 = client.post(f"{C}/{cid}/start", headers=k)
    assert r2.status_code == 200 and r2.json()["replayed"] is True
    msgs = client.get("/api/v1/email/messages", headers=h, params={"campaign_id": cid}).json()
    assert msgs["total"] == 2  # replay did not send again
    by = {m["status"]: m for m in msgs["items"]}
    assert "lead_status_not_eligible:discovered" in by["blocked"]["gate_reasons"]
    assert by["simulated"]["gate_reasons"] == ["outbound_simulated_environment"]
    recips = {r["lead_id"]: r for r in client.get(f"{C}/{cid}/recipients", headers=h).json()["items"]}
    assert recips[unapproved["id"]]["status"] == "blocked" and recips[good["id"]]["next_due_at"]
    an = client.get("/api/v1/email/analytics", headers=h, params={"campaign_id": cid}).json()
    assert an["sent"] == 0 and an["delivered"] == 0 and an["simulated"] == 1 and an["blocked"] == 1
    other = client.post(f"/api/v1/campaigns/{uuid.uuid4()}/start", headers=k)
    assert other.status_code == 409  # same key, different request
    events = [e["type"] for e in client.get(f"{C}/{cid}/events", headers=h).json()["items"]]
    assert "campaign.approved" in events and "campaign.started" in events


def test_unsubscribe_suppresses_and_stops_sequence(client):
    from app.modules.communication.models import UnsubscribeToken

    a = register(client, "Comm Unsub")
    h = tenant_headers(a)
    lead = _lead(client, h)
    cid = _email_campaign(client, h, [lead])
    _approve(client, h, cid)
    assert client.post(f"{C}/{cid}/start", headers={**h, "Idempotency-Key": "u1"}).status_code == 200
    # Recover a valid token: create one through the service (raw tokens are never stored)
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        token = comm.new_unsubscribe_token(db, uuid.UUID(a["org_id"]), lead["email_normalized"], uuid.UUID(lead["id"]))
        db.commit()
        assert db.query(UnsubscribeToken).count() >= 2
    assert client.get("/api/v1/public/unsubscribe/not-a-token").status_code == 404
    assert client.get(f"/api/v1/public/unsubscribe/{uuid.uuid4().hex}.forged").status_code == 404
    r = client.get(f"/api/v1/public/unsubscribe/{token}")
    assert r.status_code == 200 and "unsubscribed" in r.text
    sup = client.get("/api/v1/communication/suppressions", headers=h).json()["items"]
    assert sup[0]["value"] == lead["email_normalized"] and sup[0]["reason"] == "unsubscribe"
    rec = client.get(f"{C}/{cid}/recipients", headers=h).json()["items"][0]
    assert rec["status"] == "unsubscribed" and rec["next_due_at"] is None
    # A new campaign to the same lead is blocked by the gate
    cid2 = _email_campaign(client, h, [lead])
    rec2 = client.get(f"{C}/{cid2}/recipients", headers=h).json()["items"][0]
    assert "suppressed:unsubscribe" in rec2["gate_reasons"]


def test_followup_tick_and_inbound_reply(client, monkeypatch):
    a = register(client, "Comm Tick")
    h = tenant_headers(a)
    lead = _lead(client, h)
    t = _template(client, h)
    r = client.post(C, headers=h, json={"name": "Seq", "channel": "email", "email": {
        "steps": [{"template_id": t["id"], "delay_hours": 0}, {"template_id": t["id"], "delay_hours": 0}],
        "physical_address": "1 Market St"}})
    cid = r.json()["id"]
    client.post(f"{C}/{cid}/recipients", headers=h, json={"lead_ids": [lead["id"]]})
    _approve(client, h, cid)
    assert client.post(f"{C}/{cid}/start", headers={**h, "Idempotency-Key": "t1"}).json()["status"] == "running"
    r = client.post(f"{C}/{cid}/tick", headers=h)
    assert r.json()["dispatched"] == {"simulated": 1} and r.json()["status"] == "completed"
    msgs = client.get("/api/v1/email/messages", headers=h, params={"campaign_id": cid}).json()["items"]
    assert sorted(m["step_index"] for m in msgs) == [0, 1]
    # inbound webhook requires configured secret
    payload = {"to": "sales@acme.example", "from": lead["email"], "subject": "Re: hi", "text": "STOP"}
    assert client.post("/api/v1/webhooks/email/inbound", json=payload).status_code == 503
    monkeypatch.setenv("EMAIL_WEBHOOK_SECRET", "s3cret")
    assert client.post("/api/v1/webhooks/email/inbound", json=payload,
                       headers={"X-Leadex-Webhook-Secret": "nope"}).status_code == 401
    assert client.post("/api/v1/email/accounts", headers=h, json={"address": "sales@acme.example"}).status_code == 201
    r = client.post("/api/v1/webhooks/email/inbound", json=payload, headers={"X-Leadex-Webhook-Secret": "s3cret"})
    assert r.status_code == 202 and r.json()["opt_out"] is True
    sup = client.get("/api/v1/communication/suppressions", headers=h).json()["items"]
    assert any(s["reason"] == "unsubscribe" for s in sup)


def _wa_setup(client, h, monkeypatch):
    monkeypatch.setenv("WA_APP_SECRET", "appsecret")
    pid = str(uuid.uuid4().int % 10**12)
    r = client.post("/api/v1/whatsapp/accounts", headers=h, json={"phone_number_id": pid})
    assert r.status_code == 201, r.text
    return pid


def _signed(body: dict, secret="appsecret"):  # noqa: S107 (test fixture)
    raw = json.dumps(body).encode()
    return raw, {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(),
                 "Content-Type": "application/json"}


def _wa_payload(pid, sender, text, mid=None):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": pid},
        "contacts": [{"wa_id": sender, "profile": {"name": "Ravi"}}],
        "messages": [{"from": sender, "id": mid or f"wamid.{uuid.uuid4().hex}", "type": "text",
                      "text": {"body": text}}]}}]}]}


def test_whatsapp_webhook_signature_and_opt_out(client, monkeypatch):
    a = register(client, "Comm WA")
    h = tenant_headers(a)
    lead = _lead(client, h)
    pid = _wa_setup(client, h, monkeypatch)
    raw, hdr = _signed(_wa_payload(pid, lead["phone_normalized"], "Hi, interested"))
    assert client.post("/api/v1/webhooks/whatsapp", content=raw,
                       headers={**hdr, "X-Hub-Signature-256": "sha256=deadbeef"}).status_code == 401
    assert client.post("/api/v1/webhooks/whatsapp", content=raw,
                       headers={"Content-Type": "application/json"}).status_code == 401
    r = client.post("/api/v1/webhooks/whatsapp", content=raw, headers=hdr)
    assert r.status_code == 200 and r.json()["messages"] == 1
    assert client.post("/api/v1/webhooks/whatsapp", content=raw, headers=hdr).json()["messages"] == 0  # retry
    convs = client.get("/api/v1/whatsapp/conversations", headers=h).json()["items"]
    assert len(convs) == 1 and convs[0]["lead_id"] == lead["id"] and convs[0]["handoff_to_human"] is True
    conv = convs[0]["id"]
    # inside 24h window: free-form reply allowed by policy -> simulated (non-production)
    r = client.post(f"/api/v1/whatsapp/conversations/{conv}/messages", headers=h, json={"text": "Thanks!"})
    assert r.status_code == 201 and r.json()["status"] == "simulated"
    raw, hdr = _signed(_wa_payload(pid, lead["phone_normalized"], "STOP"))
    assert client.post("/api/v1/webhooks/whatsapp", content=raw, headers=hdr).json()["opt_outs"] == 1
    r = client.post(f"/api/v1/whatsapp/conversations/{conv}/messages", headers=h, json={"text": "One more"})
    assert r.json()["status"] == "blocked"
    assert "contact_opted_out" in r.json()["gate_reasons"]
    assert any("suppressed:" in x for x in r.json()["gate_reasons"])
    # other tenant cannot see the conversation
    b = register(client, "Comm WA other")
    assert client.get(f"/api/v1/whatsapp/conversations/{conv}/messages", headers=tenant_headers(b)).status_code == 404


def test_whatsapp_verify_and_template_rules(client, monkeypatch):
    assert client.get("/api/v1/webhooks/whatsapp", params={"hub.mode": "subscribe"}).status_code == 503
    monkeypatch.setenv("WA_VERIFY_TOKEN", "vt")
    q = {"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"}
    r = client.get("/api/v1/webhooks/whatsapp", params=q)
    assert r.status_code == 200 and r.text == "42"
    assert client.get("/api/v1/webhooks/whatsapp", params={**q, "hub.verify_token": "x"}).status_code == 403
    a = register(client, "Comm WA tpl")
    h = tenant_headers(a)
    t = client.post("/api/v1/whatsapp/templates", headers=h,
                    json={"name": "intro_offer", "body": "Hi {{1}}, we built you a site."}).json()
    lead = _lead(client, h)
    c = client.post(C, headers=h, json={"name": "WA", "channel": "whatsapp", "whatsapp_template_id": t["id"]}).json()
    client.post(f"{C}/{c['id']}/recipients", headers=h, json={"lead_ids": [lead["id"]]})
    r = client.post(f"{C}/{c['id']}/submit", headers=h)
    assert r.status_code == 422 and "approved_whatsapp_template_required" in r.json()["error"]["details"]
    client.post(f"/api/v1/whatsapp/templates/{t['id']}/status", headers=h, json={"status": "approved"})
    assert client.post(f"{C}/{c['id']}/submit", headers=h).status_code == 200
    assert client.post(f"{C}/{c['id']}/approval", headers=h, json={"decision": "approved"}).status_code == 200
    r = client.post(f"{C}/{c['id']}/start", headers={**h, "Idempotency-Key": "wa1"})
    assert r.json()["dispatched"] == {"simulated": 1}


def test_live_whatsapp_send_uses_cloud_api(client, monkeypatch):
    """With the environment live and provider configured, the adapter calls the Graph API (mocked)."""
    a = register(client, "Comm WA live")
    h = tenant_headers(a)
    lead = _lead(client, h)
    pid = _wa_setup(client, h, monkeypatch)
    raw, hdr = _signed(_wa_payload(pid, lead["phone_normalized"], "hello"))
    client.post("/api/v1/webhooks/whatsapp", content=raw, headers=hdr)
    conv = client.get("/api/v1/whatsapp/conversations", headers=h).json()["items"][0]["id"]
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.LIVE1"}]})

    comm.set_transport(httpx.MockTransport(handler))
    monkeypatch.setenv("WA_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(Settings, "outbound_simulated", property(lambda self: False))
    r = client.post(f"/api/v1/whatsapp/conversations/{conv}/messages", headers=h, json={"text": "Real reply"})
    assert r.json()["status"] == "sent" and r.json()["provider_message_id"] == "wamid.LIVE1"
    assert seen["url"] == f"https://graph.facebook.com/v21.0/{pid}/messages" and seen["auth"] == "Bearer tok"
    assert seen["body"]["text"]["body"] == "Real reply"
    # status webhook advances to delivered, never backwards
    st = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": pid},
                                            "statuses": [{"id": "wamid.LIVE1", "status": "delivered"}]}}]}]}
    raw, hdr = _signed(st)
    assert client.post("/api/v1/webhooks/whatsapp", content=raw, headers=hdr).json()["statuses"] == 1
    msgs = client.get(f"/api/v1/whatsapp/conversations/{conv}/messages", headers=h).json()
    assert msgs[-1]["status"] == "delivered"


def test_oauth_authorize_and_callback(client, monkeypatch):
    a = register(client, "Comm OAuth")
    h = tenant_headers(a)
    assert client.get("/api/v1/email/oauth/gmail/authorize", headers=h).status_code == 503
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
    url = client.get("/api/v1/email/oauth/gmail/authorize", headers=h).json()["authorization_url"]
    assert url.startswith("https://accounts.google.com/") and "gmail.send" in url
    state = httpx.URL(url).params["state"]

    def handler(req: httpx.Request):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
        return httpx.Response(200, json={"emailAddress": "Owner@Acme.example"})

    comm.set_transport(httpx.MockTransport(handler))
    assert client.get("/api/v1/oauth/email/gmail/callback", params={"code": "c", "state": "bad"},
                      follow_redirects=False).status_code == 400
    r = client.get("/api/v1/oauth/email/gmail/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and "connected=gmail" in r.headers["location"]
    accs = client.get("/api/v1/email/accounts", headers=h).json()
    assert accs[0]["address"] == "owner@acme.example" and accs[0]["status"] == "connected"
    assert "credentials_enc" not in accs[0]
