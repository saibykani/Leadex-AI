import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.core.db import tenant_session
from app.modules.agents import config as ai_config
from app.modules.compliance import checks as compliance_checks
from app.modules.voice import telephony
from tests.conftest import register, tenant_headers

A = "/api/v1/agents"
C = "/api/v1/calls"
BASE = "https://tunnel.example.test"
PHONE, E164 = "098765 43210", "+919876543210"
ENV_TOKEN = "env-auth-token"
DISCLOSURE = "This is an automated AI assistant calling on behalf of Acme."


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "TWILIO_ESCALATION_NUMBER",
              "PUBLIC_WEBHOOK_BASE_URL", "TEST_CALL_ALLOWLIST", "OLLAMA_BASE_URL", "QDRANT_URL"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("ALLOW_TEST_CALLS", "false")
    monkeypatch.setenv("VOICE_KILL_SWITCH", "false")
    monkeypatch.setattr(ai_config, "http_transport", None)
    monkeypatch.setattr(telephony, "http_transport", None)
    monkeypatch.setattr(compliance_checks, "now", lambda: datetime(2026, 11, 4, 6, 30, tzinfo=UTC))


class Twilio:
    def __init__(self, status=201, body=None):
        self.requests: list[httpx.Request] = []
        self.status, self.body = status, body or {"sid": "CA" + "1" * 32, "status": "queued"}

    def __call__(self, request: httpx.Request):
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


def _configure(monkeypatch, *, public=True, allow=True, twilio: Twilio | None = None):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACenv")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", ENV_TOKEN)
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15005550006")
    if public:
        monkeypatch.setenv("PUBLIC_WEBHOOK_BASE_URL", BASE + "/")
    if allow:
        monkeypatch.setenv("ALLOW_TEST_CALLS", "true")
        monkeypatch.setenv("TEST_CALL_ALLOWLIST", f"+15551234567, {E164}")
    t = twilio or Twilio()
    monkeypatch.setattr(telephony, "http_transport", httpx.MockTransport(t))
    return t


def _setup(client, org="Tel Org", phone=PHONE):
    acct = register(client, org)
    h = tenant_headers(acct)
    r = client.post(A, headers=h, json={"name": "Sales Bot", "compliance_disclosure": DISCLOSURE,
                                        "greeting": "Hello there!", "business_info": "We build websites."})
    assert r.status_code == 201, r.text
    ag = r.json()
    assert client.post(f"{A}/{ag['id']}/publish", headers=h).status_code == 201
    r = client.post("/api/v1/leads", headers=h, json={"business_name": "Dental Co", "country": "IN", "phone": phone,
                                                      "email": f"{uuid.uuid4().hex[:6]}@d.example"})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert client.post(f"/api/v1/leads/{lid}/status", headers=h, json={"status": "verified"}).status_code == 200
    assert client.post(f"/api/v1/leads/{lid}/status", headers=h, json={
        "status": "approved_for_outreach", "consent_reference": "form-123"}).status_code == 200
    assert client.post("/api/v1/compliance/consents", headers=h, json={
        "lead_id": lid, "channel": "voice", "basis": "express_consent", "evidence_text": "Web form"}).status_code == 201
    return {"acct": acct, "h": h, "agent": ag["id"], "lead": lid, "org": uuid.UUID(acct["org_id"])}


def _call(client, s, key=None):
    return client.post(C, headers={**s["h"], "Idempotency-Key": key or uuid.uuid4().hex},
                       json={"lead_id": s["lead"], "agent_id": s["agent"]})


def _hook(client, kind, call_id, params: dict, token=ENV_TOKEN, sig=None):
    path = f"/api/v1/telephony/twilio/{kind}/{call_id}"
    signature = sig if sig is not None else telephony.twilio_signature(token, BASE + path, list(params.items()))
    return client.post(path, data=params, headers={"X-Twilio-Signature": signature})


def _dialed(client, monkeypatch, org="Tel Org"):
    t = _configure(monkeypatch)
    s = _setup(client, org)
    r = _call(client, s)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "initiated"
    return s, r.json()["id"], t


# ---------------------------------------------------------------- adapter status / placement
def test_not_configured(client):
    s = _setup(client, "Tel NC")
    st = client.get("/api/v1/telephony/status", headers=s["h"]).json()
    assert st["status"] == "not_configured" and st["mode"] == "not_configured"


def test_not_configured_blocks_real_dial_when_allowlisted(client, monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_CALLS", "true")
    monkeypatch.setenv("TEST_CALL_ALLOWLIST", E164)
    s = _setup(client, "Tel NC2")
    r = _call(client, s)
    assert r.status_code == 201 and r.json()["status"] == "not_configured"
    assert r.json()["gate_reasons"] == ["telephony_not_configured"] and r.json()["simulated"] is False


def test_needs_public_url(client, monkeypatch):
    t = _configure(monkeypatch, public=False)
    monkeypatch.setenv("PUBLIC_WEBHOOK_BASE_URL", "http://insecure.example")  # must be https
    s = _setup(client, "Tel NP")
    st = client.get("/api/v1/telephony/status", headers=s["h"]).json()
    assert st["status"] == "needs_public_url" and st["credential_source"] == "env"
    r = _call(client, s)
    assert r.json()["status"] == "not_configured" and r.json()["gate_reasons"] == ["telephony_needs_public_url"]
    assert t.requests == []


def test_simulated_when_not_allowlisted(client, monkeypatch):
    t = _configure(monkeypatch)
    monkeypatch.setenv("TEST_CALL_ALLOWLIST", "+15551234567")
    s = _setup(client, "Tel Sim")
    assert client.get("/api/v1/telephony/status", headers=s["h"]).json()["mode"] == "test_allowlist"
    r = _call(client, s)
    assert r.json()["status"] == "simulated_completed" and r.json()["simulated"] is True
    assert t.requests == []
    monkeypatch.setenv("ALLOW_TEST_CALLS", "false")
    monkeypatch.setenv("TEST_CALL_ALLOWLIST", E164)
    assert _call(client, s).json()["status"] == "simulated_completed" and t.requests == []


def test_real_dial_request_params_and_idempotency(client, monkeypatch):
    t = _configure(monkeypatch)
    s = _setup(client, "Tel Dial")
    key = uuid.uuid4().hex
    r = _call(client, s, key)
    assert r.status_code == 201, r.text
    call = r.json()
    assert call["status"] == "initiated" and call["provider"] == "twilio" and call["simulated"] is False
    assert call["to_number"] == E164 and call["provider_call_id"] == "CA" + "1" * 32
    assert len(t.requests) == 1
    req = t.requests[0]
    assert req.url.path == "/2010-04-01/Accounts/ACenv/Calls.json" and req.method == "POST"
    assert req.headers["Authorization"].startswith("Basic ")
    form = dict(httpx.QueryParams(req.content.decode()).multi_items())
    assert form["To"] == E164 and form["From"] == "+15005550006"
    assert form["Url"] == f"{BASE}/api/v1/telephony/twilio/voice/{call['id']}"
    assert form["StatusCallback"] == f"{BASE}/api/v1/telephony/twilio/status/{call['id']}"
    assert "Record" not in form  # no recording consent
    # idempotent replay: no second dial
    r2 = _call(client, s, key)
    assert r2.headers.get("Idempotent-Replay") == "true" and r2.json()["id"] == call["id"]
    assert len(t.requests) == 1


def test_twilio_error_surfaced_verbatim(client, monkeypatch):
    msg = "The number +919876543210 is unverified. Trial accounts cannot call unverified numbers."
    _configure(monkeypatch, twilio=Twilio(400, {"code": 21219, "message": msg, "status": 400}))
    s = _setup(client, "Tel Err")
    call = _call(client, s).json()
    assert call["status"] == "failed" and msg in call["error_message"] and "21219" in call["error_message"]


# ---------------------------------------------------------------- webhooks
def test_signature_rejection(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel Sig")
    assert _hook(client, "voice", cid, {"CallSid": "CA1"}, sig="bogus").status_code == 403
    assert _hook(client, "voice", cid, {"CallSid": "CA1"}, token="wrong-token").status_code == 403
    path = f"/api/v1/telephony/twilio/voice/{cid}"
    assert client.post(path, data={"CallSid": "CA1"}).status_code == 403
    # params tampered after signing
    sig = telephony.twilio_signature(ENV_TOKEN, BASE + path, [("CallSid", "CA1")])
    assert client.post(path, data={"CallSid": "CA2"}, headers={"X-Twilio-Signature": sig}).status_code == 403
    assert _hook(client, "voice", uuid.uuid4(), {"CallSid": "CA1"}).status_code == 404
    assert _hook(client, "voice", cid, {"CallSid": "CA1"}).status_code == 200


def test_first_twiml_has_ai_disclosure(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Bright Smiles Marketing")
    r = _hook(client, "voice", cid, {"CallSid": "CA1", "CallStatus": "in-progress"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    x = r.text
    assert "AI assistant calling on behalf of Bright Smiles Marketing" in x and "Hello there!" in x
    assert '<Gather input="speech" speechTimeout="auto"' in x and 'language="en-IN"' in x
    assert f'action="{BASE}/api/v1/telephony/twilio/turn/{cid}"' in x
    d = client.get(f"{C}/{cid}", headers=s["h"]).json()
    assert d["status"] == "in_progress" and d["transcript"][0]["speaker"] == "agent"


def _ollama(monkeypatch, handler):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setattr(ai_config, "http_transport", httpx.MockTransport(handler))


def test_turn_loop_appends_transcript(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel Turn")
    _hook(client, "voice", cid, {"CallSid": "CA1"})
    seen = {}

    def handler(req: httpx.Request):
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"message": {"role": "assistant", "content":
                              "Great question [1]. We build **modern** websites. What timeline do you have? "
                              "Extra sentence here."}})

    _ollama(monkeypatch, handler)
    r = _hook(client, "turn", cid, {"CallSid": "CA1", "SpeechResult": "What do you do exactly?"})
    assert r.status_code == 200
    assert "<Gather" in r.text and "We build modern websites. What timeline" not in r.text  # 2 sentences max
    assert "Great question. We build modern websites." in r.text and "Extra sentence" not in r.text
    assert "LIVE PHONE CALL" in seen["body"]
    d = client.get(f"{C}/{cid}", headers=s["h"]).json()
    assert [t["speaker"] for t in d["transcript"]] == ["agent", "contact", "agent"]
    assert d["transcript"][1]["text"] == "What do you do exactly?"


def test_llm_timeout_fallback(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel Timeout")
    _hook(client, "voice", cid, {"CallSid": "CA1"})

    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    _ollama(monkeypatch, handler)
    r = _hook(client, "turn", cid, {"CallSid": "CA1", "SpeechResult": "How much does it cost?"})
    assert r.status_code == 200 and "call you back" in r.text and "<Gather" in r.text
    d = client.get(f"{C}/{cid}", headers=s["h"]).json()
    assert any(e["type"] == "agent.fallback" for e in d["events"])


def test_invented_price_is_replaced(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel Price")
    _ollama(monkeypatch, lambda req: httpx.Response(200, json={"message": {"content": "It costs ₹25,000 only."}}))
    r = _hook(client, "turn", cid, {"SpeechResult": "What's the price?"})
    assert "25,000" not in r.text and "specialist will confirm" in r.text


def test_opt_out_creates_suppression_and_hangs_up(client, monkeypatch):
    from app.modules.compliance.models import ConsentRecord, SuppressionRecord

    s, cid, _ = _dialed(client, monkeypatch, "Tel Opt")
    _hook(client, "voice", cid, {"CallSid": "CA1"})
    r = _hook(client, "turn", cid, {"CallSid": "CA1", "SpeechResult": "Please don't call me again"})
    assert r.status_code == 200 and "<Hangup/>" in r.text and "<Gather" not in r.text
    with tenant_session(s["org"]) as db:
        sup = db.scalars(select(SuppressionRecord).where(SuppressionRecord.organization_id == s["org"])).all()
        assert len(sup) == 1 and sup[0].phone_normalized == "09876543210"
        cons = db.scalars(select(ConsentRecord).where(ConsentRecord.organization_id == s["org"])).all()
        assert cons and all(c.withdrawn_at is not None and "do_not_contact" in c.withdrawn_reason for c in cons)
    r = _call(client, s)
    assert r.status_code == 422 and "suppressed_contact" in r.json()["error"]["details"]["reasons"]


def test_human_escalation_dial_or_message(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel Esc")
    r = _hook(client, "turn", cid, {"SpeechResult": "Can I talk to a real person?"})
    assert "call you back" in r.text and "<Gather" in r.text and "<Dial>" not in r.text
    monkeypatch.setenv("TWILIO_ESCALATION_NUMBER", "+15550001111")
    r = _hook(client, "turn", cid, {"SpeechResult": "I want a human"})
    assert "<Dial>+15550001111</Dial>" in r.text


def test_status_completed_records_usage_and_outcome(client, monkeypatch):
    from app.modules.billing.models import BillingUsage
    from app.modules.crm.models import Lead

    s, cid, _ = _dialed(client, monkeypatch, "Tel Done")
    _hook(client, "voice", cid, {"CallSid": "CA1"})
    _hook(client, "turn", cid, {"SpeechResult": "We are interested, our budget is around 50000 rupees"})
    _hook(client, "turn", cid, {"SpeechResult": "We want it live next month"})
    params = {"CallSid": "CA1", "CallStatus": "completed", "CallDuration": "75", "Price": "-0.0260",
              "PriceUnit": "USD"}
    assert _hook(client, "status", cid, params).status_code == 204
    assert _hook(client, "status", cid, params).status_code == 204  # Twilio retry: idempotent
    d = client.get(f"{C}/{cid}", headers=s["h"]).json()
    assert d["status"] == "completed" and d["duration_s"] == 75 and d["price"] == pytest.approx(0.026)
    assert d["outcome"]["budget_max"] == 50000 or d["outcome"]["budget_min"] == 50000
    assert d["outcome"]["budget_evidence"] and d["outcome"]["timeline"]
    assert d["summary"] is not None
    with tenant_session(s["org"]) as db:
        rows = db.scalars(select(BillingUsage).where(BillingUsage.organization_id == s["org"],
                                                     BillingUsage.resource == "voice_minutes")).all()
        assert len(rows) == 1 and float(rows[0].quantity) == 2 and float(rows[0].cost) == pytest.approx(0.03, abs=0.01)
        lead = db.get(Lead, uuid.UUID(s["lead"]))
        assert lead.custom_fields["budget"]["currency"] == "INR" and lead.custom_fields.get("timeline")


def test_status_no_answer_without_outcome(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Tel NoAns")
    assert _hook(client, "status", cid, {"CallStatus": "no-answer", "CallDuration": "0"}).status_code == 204
    d = client.get(f"{C}/{cid}", headers=s["h"]).json()
    assert d["status"] == "no_answer" and d["outcome"] is None and "no_answer" in d["summary"]["summary"]


def test_webhooks_cross_tenant_isolation(client, monkeypatch):
    a, cid_a, _ = _dialed(client, monkeypatch, "Tel Org A")
    b = _setup(client, "Tel Org B")
    r = client.put("/api/v1/integrations/twilio", headers=b["h"], json={"credentials": {
        "account_sid": "ACorgB", "auth_token": "org-b-token", "from_number": "+15550002222"}})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/telephony/status", headers=b["h"]).json()["credential_source"] == "org"
    # org B's credentials cannot drive org A's session
    assert _hook(client, "turn", cid_a, {"SpeechResult": "stop"}, token="org-b-token").status_code == 403
    # org B's own call is signed with org B's token; org A's (env) token is rejected
    r = _call(client, b)
    cid_b = r.json()["id"]
    assert r.json()["status"] == "initiated"
    assert _hook(client, "voice", cid_b, {"CallSid": "CA9"}).status_code == 403
    assert _hook(client, "voice", cid_b, {"CallSid": "CA9"}, token="org-b-token").status_code == 200
    # org A cannot read org B's call; B's data untouched by A's webhooks
    assert client.get(f"{C}/{cid_b}", headers=a["h"]).status_code == 404
    assert len(client.get(f"{C}/{cid_a}", headers=a["h"]).json()["transcript"]) == 0
    # simulated sessions are not reachable through webhooks at all
    monkeypatch.setenv("ALLOW_TEST_CALLS", "false")
    sim = _call(client, a).json()
    assert sim["status"] == "simulated_completed"
    assert _hook(client, "voice", sim["id"], {"CallSid": "CA1"}).status_code == 404


def test_e164_normalisation():
    assert telephony.to_e164("098765 43210", "IN") == "+919876543210"
    assert telephony.to_e164("+91 98765-43210", None) == "+919876543210"
    assert telephony.to_e164("919876543210", "IN") == "+919876543210"
    assert telephony.to_e164("(415) 555-0100", "US") == "+14155550100"
    assert telephony.to_e164("12345", "IN") is None
    assert telephony.to_e164("98765 43210", None) is None
