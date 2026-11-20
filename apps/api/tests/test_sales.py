import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.db import SessionLocal, tenant_session
from app.modules.compliance.models import ConsentRecord
from app.modules.crm.models import Lead, LeadTask
from app.modules.identity.models import Organization, User
from app.modules.sales.models import SalesBookedSlot, SalesInquiry, SalesInquiryInbox, SalesSettings
from tests.conftest import register, tenant_headers

P = "/api/v1/public"


def _form(**kw):
    base = {"type": "talk_to_sales", "name": "Ada Lovelace", "email": f"ada-{uuid.uuid4().hex[:6]}@corp.example",
            "company": "Analytical Ltd", "role": "CTO", "team_size": "11-50", "country": "gb",
            "interests": ["ai_agents", "crm"], "message": "We would like a walkthrough.", "privacy_ack": True,
            "marketing_consent": False, "form_started_at": int(time.time() * 1000) - 10_000}
    base.update(kw)
    return base


def _set_owner(org_id):
    with SessionLocal() as db:
        db.execute(update(Organization).values(is_platform_owner=False))
        if org_id:
            db.execute(update(Organization).where(Organization.id == uuid.UUID(org_id)).values(is_platform_owner=True))
        db.commit()


@pytest.fixture
def owner(client):
    a = register(client, "Leadex HQ Test")
    _set_owner(a["org_id"])
    with SessionLocal() as db:
        db.query(SalesBookedSlot).delete()
        db.query(SalesSettings).delete()
        db.commit()
    yield a
    _set_owner(None)


def test_contact_lands_in_owner_org_with_lead_consent_and_notification(client, owner):
    other = register(client, "Some Tenant")
    body = _form()
    r = client.post(f"{P}/sales/contact", json=body)
    assert r.status_code == 201, r.text
    ref = r.json()["reference"]
    assert ref.startswith("LX-") and r.json()["duplicate"] is False
    with tenant_session(uuid.UUID(owner["org_id"])) as db:
        inq = db.scalar(select(SalesInquiry).where(SalesInquiry.reference == ref))
        assert str(inq.organization_id) == owner["org_id"] and inq.lead_id
        lead = db.get(Lead, inq.lead_id)
        assert lead.source == "website:talk_to_sales" and lead.status == "interested"
        assert lead.consent_reference is None  # no marketing consent -> outreach gate stays closed
        bases = {c.basis for c in db.scalars(select(ConsentRecord).where(ConsentRecord.lead_id == lead.id))}
        assert bases == {"inbound_request"}
    inbox = client.get("/api/v1/sales/inquiries", headers=tenant_headers(owner)).json()
    assert [i["reference"] for i in inbox["items"]] == [ref]
    notes = client.get("/api/v1/notifications", headers=tenant_headers(owner)).json()
    assert any(ref in (n["body"] or "") for n in notes["items"])
    # other tenants see nothing
    assert client.get("/api/v1/sales/inquiries", headers=tenant_headers(other)).status_code == 403
    leads = client.get("/api/v1/leads", headers=tenant_headers(other)).json()
    assert all(lead["email"] != body["email"] for lead in leads["items"])


def test_marketing_consent_is_separate(client, owner):
    r = client.post(f"{P}/sales/contact", json=_form(marketing_consent=True))
    with tenant_session(uuid.UUID(owner["org_id"])) as db:
        inq = db.scalar(select(SalesInquiry).where(SalesInquiry.reference == r.json()["reference"]))
        lead = db.get(Lead, inq.lead_id)
        assert inq.marketing_consent and lead.consent_reference.startswith("website-marketing-opt-in:")
        bases = {c.basis for c in db.scalars(select(ConsentRecord).where(ConsentRecord.lead_id == lead.id))}
        assert bases == {"inbound_request", "express_consent"}


def test_honeypot_timing_privacy_and_validation(client, owner):
    assert client.post(f"{P}/sales/contact", json=_form(website="http://spam")).json()["error"]["code"] \
        == "spam_rejected"
    r = client.post(f"{P}/sales/contact", json=_form(form_started_at=int(time.time() * 1000)))
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_fast"
    r = client.post(f"{P}/sales/contact", json=_form(privacy_ack=False))
    assert r.status_code == 422 and r.json()["error"]["code"] == "privacy_ack_required"
    for bad in ({"email": "not-an-email"}, {"type": "hack"}, {"interests": ["bitcoin"]}, {"name": "x" * 500},
                {"message": "m" * 5000}, {"phone": "<script>"}, {"extra_field": 1}):
        assert client.post(f"{P}/sales/contact", json=_form(**bad)).status_code == 422, bad
    with tenant_session(uuid.UUID(owner["org_id"])) as db:
        assert db.scalar(select(SalesInquiry).where(SalesInquiry.email == "not-an-email")) is None


def test_rate_limit(client, owner):
    codes = [client.post(f"{P}/sales/contact", json=_form()).status_code for _ in range(7)]
    assert codes[:5] == [201] * 5 and codes[-1] == 429


def test_idempotent_within_window(client, owner):
    body = _form()
    a = client.post(f"{P}/sales/contact", json=body).json()
    b = client.post(f"{P}/sales/contact", json={**body, "email": body["email"].upper()}).json()
    assert b["duplicate"] is True and b["reference"] == a["reference"]
    c = client.post(f"{P}/sales/contact", json={**body, "type": "partnership"}).json()
    assert c["duplicate"] is False


def test_no_platform_owner_falls_back_to_inbox(client):
    _set_owner(None)
    body = _form()
    r = client.post(f"{P}/sales/contact", json=body)
    assert r.status_code == 201
    with SessionLocal() as db:
        assert db.scalar(select(SalesInquiryInbox).where(SalesInquiryInbox.email == body["email"]))
        assert db.scalar(select(SalesInquiry).where(SalesInquiry.email == body["email"])) is None


def _superadmin(client):
    a = register(client, "Platform Ops")
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == a["email"]).values(is_superadmin=True))
        db.commit()
    return a


def test_pricing_null_until_set_and_permissions(client, owner):
    plans = client.get(f"{P}/pricing").json()["plans"]
    assert plans and all(p["price_monthly"] is None and p["price_annual"] is None for p in plans)
    assert "free_trial" not in {p["code"] for p in plans}
    starter = next(p for p in plans if p["code"] == "starter")
    assert starter["limits"]["leads"] == 1000 and any("leads" in f for f in starter["features"])
    item = {"plan_code": "starter", "price_monthly": "39", "price_annual": "32", "currency": "USD",
            "highlight": True, "badge": "Popular", "tagline": "For small teams", "bullets": ["Email support"]}
    tenant = register(client, "Random Tenant")
    assert client.put("/api/v1/sales/plan-display", headers=tenant_headers(tenant),
                      json={"items": [item]}).status_code == 403
    assert client.get("/api/v1/sales/plan-display", headers=tenant_headers(tenant)).status_code == 403
    r = client.put("/api/v1/sales/plan-display", headers=tenant_headers(owner), json={"items": [item]})
    assert r.status_code == 200, r.text
    sa = _superadmin(client)
    assert client.put("/api/v1/sales/plan-display", headers=tenant_headers(sa),
                      json={"items": [{**item, "plan_code": "enterprise", "contact_sales": True,
                                       "price_monthly": "1"}]}).status_code == 200
    # superadmin outside the owner org cannot read the inbox (RLS-bound to the owner org)
    assert client.get("/api/v1/sales/inquiries", headers=tenant_headers(sa)).status_code == 403
    plans = {p["code"]: p for p in client.get(f"{P}/pricing").json()["plans"]}
    assert plans["starter"]["price_monthly"] == "39.00" and plans["starter"]["highlight"]
    assert plans["enterprise"]["price_monthly"] is None and plans["enterprise"]["contact_sales"]
    assert plans["business"]["price_monthly"] is None
    assert client.put("/api/v1/sales/plan-display", headers=tenant_headers(owner),
                      json={"items": [{**item, "plan_code": "nope"}]}).status_code == 422
    # reset so other runs see unset prices
    client.put("/api/v1/sales/plan-display", headers=tenant_headers(owner),
               json={"items": [{"plan_code": c} for c in ("starter", "enterprise")]})


def _next_weekday():
    d = datetime.now(UTC).date() + timedelta(days=3)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def test_slots_and_booking_conflicts(client, owner):
    h = tenant_headers(owner)
    s = {"timezone": "Asia/Kolkata", "weekdays": [0, 1, 2, 3, 4], "day_start": "10:00", "day_end": "12:00",
         "slot_minutes": 30, "buffer_minutes": 15, "min_notice_hours": 1, "horizon_days": 30, "booking_enabled": True}
    assert client.put("/api/v1/sales/settings", headers=h, json=s).status_code == 200
    assert client.put("/api/v1/sales/settings", headers=h, json={**s, "timezone": "Mars/Base"}).status_code == 422
    assert client.put("/api/v1/sales/settings", headers=register(client, "Outsider")["headers"] | {
        "X-Organization-Id": owner["org_id"]}, json=s).status_code in (403, 404)
    day = _next_weekday()
    slots = client.get(f"{P}/sales/slots", params={"date": day.isoformat()}).json()["slots"]
    assert [x["label"] for x in slots] == ["10:00", "10:45", "11:30"]  # 30 min slots + 15 min buffer
    weekend = day + timedelta(days=(5 - day.weekday()))
    assert client.get(f"{P}/sales/slots", params={"date": weekend.isoformat()}).json()["slots"] == []
    body = _form(type="demo_request", slot_start=slots[0]["start"])
    r = client.post(f"{P}/sales/book", json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["ics_url"]
    ics = client.get(out["ics_url"])
    assert ics.status_code == 200 and "BEGIN:VEVENT" in ics.text and out["reference"] in ics.text
    assert "Ada" not in ics.text  # no PII in the calendar file
    left = client.get(f"{P}/sales/slots", params={"date": day.isoformat()}).json()["slots"]
    assert [x["label"] for x in left] == ["10:45", "11:30"]
    r2 = client.post(f"{P}/sales/book", json=_form(type="demo_request", slot_start=slots[0]["start"]))
    assert r2.status_code == 409
    # a time that isn't an offered slot
    bad = (datetime.fromisoformat(slots[0]["start"]) + timedelta(minutes=7)).isoformat()
    assert client.post(f"{P}/sales/book", json=_form(type="demo_request", slot_start=bad)).status_code == 409
    with tenant_session(uuid.UUID(owner["org_id"])) as db:
        inq = db.scalar(select(SalesInquiry).where(SalesInquiry.reference == out["reference"]))
        assert inq.type == "demo_request" and inq.booking_start
        task = db.scalar(select(LeadTask).where(LeadTask.lead_id == inq.lead_id))
        assert task and out["reference"] in task.title


def test_inquiry_patch_and_cross_tenant(client, owner):
    ref = client.post(f"{P}/sales/contact", json=_form()).json()["reference"]
    h = tenant_headers(owner)
    item = next(i for i in client.get("/api/v1/sales/inquiries", headers=h).json()["items"] if i["reference"] == ref)
    me = client.get("/api/v1/auth/me", headers=owner["headers"]).json()
    r = client.patch(f"/api/v1/sales/inquiries/{item['id']}", headers=h,
                     json={"status": "contacted", "assignee_user_id": me["user"]["id"]})
    assert r.status_code == 200 and r.json()["status"] == "contacted"
    assert client.patch(f"/api/v1/sales/inquiries/{item['id']}", headers=h,
                        json={"status": "bogus"}).status_code == 422
    stranger = register(client, "Stranger")
    assert client.patch(f"/api/v1/sales/inquiries/{item['id']}", headers=h,
                        json={"assignee_user_id": client.get("/api/v1/auth/me", headers=stranger["headers"])
                              .json()["user"]["id"]}).status_code == 422
    assert client.patch(f"/api/v1/sales/inquiries/{item['id']}", headers=tenant_headers(stranger),
                        json={"status": "closed"}).status_code == 403
    assert client.get("/api/v1/sales/inquiries", headers=h, params={"status": "contacted"}).json()["total"] >= 1
