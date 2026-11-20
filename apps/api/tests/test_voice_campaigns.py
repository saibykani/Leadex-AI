import uuid

from tests.test_telephony import BASE, _configure, _env, _hook, _setup  # noqa: F401  (_env: autouse fixture)

C = "/api/v1/campaigns"
PHONES = ["+919876543210", "+919876543211", "+919876543212"]


def _lead(client, h, phone):
    r = client.post("/api/v1/leads", headers=h, json={"business_name": f"Biz {phone[-2:]}", "country": "IN",
                                                      "phone": phone, "email": f"{uuid.uuid4().hex[:6]}@d.example"})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    client.post(f"/api/v1/leads/{lid}/status", headers=h, json={"status": "verified"})
    client.post(f"/api/v1/leads/{lid}/status", headers=h, json={"status": "approved_for_outreach",
                                                                   "consent_reference": "form-1"})
    client.post("/api/v1/compliance/consents", headers=h, json={"lead_id": lid, "channel": "voice",
                                                                "basis": "express_consent", "evidence_text": "Form"})
    return lid


def test_voice_campaign_respects_concurrency_and_continues(client, monkeypatch):
    twilio = _configure(monkeypatch)
    monkeypatch.setenv("TEST_CALL_ALLOWLIST", ",".join(PHONES))
    s = _setup(client, "Voice Camp", phone=PHONES[0])
    h = s["h"]
    leads = [s["lead"], _lead(client, h, PHONES[1]), _lead(client, h, PHONES[2])]
    r = client.post(C, headers=h, json={"name": "Clinic calls", "channel": "voice"})
    cid = r.json()["id"]
    assert client.post(f"{C}/{cid}/recipients", headers=h, json={"lead_ids": leads}).status_code in (200, 201)
    sub = client.post(f"{C}/{cid}/submit", headers=h)
    assert sub.status_code == 422 and "voice_agent_required" in sub.text
    client.patch(f"{C}/{cid}", headers=h, json={"voice_agent_id": s["agent"], "max_concurrent_calls": 2})
    assert client.post(f"{C}/{cid}/submit", headers=h).status_code == 200
    assert client.post(f"{C}/{cid}/approval", headers=h, json={"decision": "approved"}).status_code == 200
    r = client.post(f"{C}/{cid}/start", headers={**h, "Idempotency-Key": "vc-1"})
    assert r.status_code == 200, r.text
    assert r.json()["dispatched"] == {"sent": 2}  # only 2 at once
    assert len(twilio.requests) == 2
    calls = client.get("/api/v1/calls", headers=h).json()["items"]
    first = next(c for c in calls if c["status"] == "initiated")
    # one call finishes -> a slot frees -> next tick dials the third lead
    _hook(client, "status", first["id"], {"CallSid": "CA1", "CallStatus": "no-answer", "CallDuration": "0"})
    t = client.post(f"{C}/{cid}/tick", headers=h)
    assert t.status_code == 200, t.text
    assert len(twilio.requests) == 3


def test_voice_campaign_rejects_foreign_agent(client, monkeypatch):
    s = _setup(client, "Voice A")
    other = _setup(client, "Voice B")
    r = client.post(C, headers=s["h"], json={"name": "x", "channel": "voice", "voice_agent_id": other["agent"]})
    assert r.status_code == 422 and "unknown_agent" in r.text


def test_voices_catalogue_has_indian_female_defaults(client):
    s = _setup(client, "Voice List")
    body = client.get("/api/v1/voices", headers=s["h"]).json()
    ids = {v["id"]: v for v in body["items"]}
    assert ids[body["defaults"]["en-IN"]]["gender"] == "female"
    assert ids[body["defaults"]["hi-IN"]]["gender"] == "female"
    assert any(v["gender"] == "male" for v in body["items"])
    assert {"ta-IN", "te-IN", "kn-IN"} <= set(body["defaults"])


def test_agent_voice_choice_used_and_invalid_falls_back(client, monkeypatch):
    from tests.test_telephony import _call

    _configure(monkeypatch)
    s = _setup(client, "Voice Pick")
    client.patch(f"/api/v1/agents/{s['agent']}", headers=s["h"], json={"voice": "Google.en-IN-Standard-B"})
    client.post(f"/api/v1/agents/{s['agent']}/publish", headers=s["h"])
    cid = _call(client, s).json()["id"]
    assert 'voice="Google.en-IN-Standard-B"' in _hook(client, "voice", cid, {"CallSid": "CA1"}).text
    client.patch(f"/api/v1/agents/{s['agent']}", headers=s["h"], json={"voice": "Google.ta-IN-Standard-A"})
    client.post(f"/api/v1/agents/{s['agent']}/publish", headers=s["h"])
    cid2 = _call(client, s).json()["id"]
    assert 'voice="Polly.Aditi"' in _hook(client, "voice", cid2, {"CallSid": "CA2"}).text  # Tamil voice: wrong language
