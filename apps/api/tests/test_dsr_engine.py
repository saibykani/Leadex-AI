from sqlalchemy import select

from app.core.db import tenant_session
from app.modules.compliance.models import SuppressionRecord
from app.modules.voice.models import CallTranscript
from tests.test_telephony import _dialed, _env, _hook  # noqa: F401  (_env: autouse fixture)

D = "/api/v1/compliance/dsr"


def test_export_then_erase_removes_personal_data(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "DSR Org")
    h = s["h"]
    _hook(client, "voice", cid, {"CallSid": "CA1"})
    _hook(client, "turn", cid, {"SpeechResult": "My name is Ravi and my budget is 40000 rupees"})
    client.post(f"/api/v1/leads/{s['lead']}/notes", headers=h, json={"body": "Ravi prefers mornings"})
    r = client.post(D, headers=h, json={"type": "deletion", "lead_id": s["lead"]})
    assert r.status_code == 201, r.text
    dsr = r.json()["id"]
    exp = client.post(f"{D}/{dsr}/export", headers=h).json()
    assert len(exp["records"]) == 1 and exp["records"][0]["call_transcripts"]
    assert any("Ravi" in t["text"] for t in exp["records"][0]["call_transcripts"])
    r = client.post(f"{D}/{dsr}/erase", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed" and "leads_erased=1" in r.json()["resolution"]
    with tenant_session(s["org"]) as db:
        assert not db.scalars(select(CallTranscript).where(CallTranscript.organization_id == s["org"])).all()
        assert db.scalar(select(SuppressionRecord).where(SuppressionRecord.organization_id == s["org"],
                                                         SuppressionRecord.reason.like("Erasure request%")))
    again = client.post(f"{D}/{dsr}/export", headers=h).json()
    assert again["records"] == [] or again["records"][0]["lead"]["business_name"] == "[erased]"
    assert client.post(f"{D}/{dsr}/erase", headers=h).status_code == 409


def test_erase_only_for_deletion_requests(client, monkeypatch):
    s, _cid, _ = _dialed(client, monkeypatch, "DSR Type")
    dsr = client.post(D, headers=s["h"], json={"type": "access", "lead_id": s["lead"]}).json()["id"]
    assert client.post(f"{D}/{dsr}/erase", headers=s["h"]).status_code == 422
