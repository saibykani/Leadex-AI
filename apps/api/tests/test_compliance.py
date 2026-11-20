import uuid
from datetime import UTC, datetime

import pyotp
from sqlalchemy import update

from app.core.db import SessionLocal, tenant_session
from app.modules.compliance import checks
from app.modules.identity.models import User
from tests.conftest import register, tenant_headers

C = "/api/v1/compliance"
# 06:30 UTC = 12:00 IST (inside India's 09-21 window); 03:00 UTC = 08:30 IST (outside).
IN_DAY = datetime(2026, 11, 4, 6, 30, tzinfo=UTC)
IN_NIGHT = datetime(2026, 11, 4, 3, 0, tzinfo=UTC)


def _member(client, owner, role):
    other = register(client, f"Home {role}")
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text
    return tenant_headers(other, owner["org_id"])


def _approved_lead(client, h, **kw):
    body = {"business_name": "Sunrise Dental", "email": f"{uuid.uuid4().hex[:6]}@sunrise.example",
            "phone": "+91 98765 00000", "country": "IN", **kw}
    lead = client.post("/api/v1/leads", headers=h, json=body).json()
    for s, extra in (("verified", {}), ("approved_for_outreach", {"consent_reference": "form-1"})):
        r = client.post(f"/api/v1/leads/{lead['id']}/status", headers=h, json={"status": s, **extra})
        assert r.status_code == 200, r.text
    return lead


def _consent(client, h, lead_id, channel="email"):
    r = client.post(f"{C}/consents", headers=h, json={"lead_id": lead_id, "channel": channel,
                                                       "basis": "express_consent", "evidence_text": "Web form"})
    assert r.status_code == 201, r.text
    return r.json()


def _check(client, h, lead_id, channel="email"):
    r = client.post(f"{C}/check", headers=h, json={"lead_id": lead_id, "channel": channel})
    assert r.status_code == 200, r.text
    return r.json()


def _superadmin(acc):
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == acc["email"]).values(is_superadmin=True))
        db.commit()


def test_gate_consent_suppression_preferences(client):
    a = register(client, "Gate Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    d = _check(client, h, lead["id"])
    assert not d["allowed"] and "no_consent_record:email" in d["reasons"] and d["jurisdiction"] == "IN"
    consent = _consent(client, h, lead["id"])
    d = _check(client, h, lead["id"])
    assert d["allowed"] and d["simulated"] is True, d
    # opt-out preference blocks
    r = client.put(f"{C}/preferences/{lead['id']}", headers=h, json={"channel": "email", "allowed": False})
    assert r.status_code == 200
    assert "channel_opted_out" in _check(client, h, lead["id"])["reasons"]
    client.put(f"{C}/preferences/{lead['id']}", headers=h, json={"channel": "email", "allowed": True})
    # suppression on the normalized email blocks
    r = client.post(f"{C}/suppressions", headers=h, json={"email": lead["email"].upper(), "reason": "asked"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert "suppressed_contact" in _check(client, h, lead["id"])["reasons"]
    assert client.get(f"{C}/suppressions", headers=h).json()["total"] == 1
    assert client.delete(f"{C}/suppressions/{sid}", headers=h).status_code == 204
    assert _check(client, h, lead["id"])["allowed"]
    # withdrawal blocks and freezes the record
    r = client.post(f"{C}/consents/{consent['id']}/withdraw", headers=h, json={"reason": "unsubscribe"})
    assert r.status_code == 200 and r.json()["withdrawn_at"]
    assert "consent_withdrawn:email" in _check(client, h, lead["id"])["reasons"]
    r = client.patch(f"{C}/consents/{consent['id']}", headers=h, json={"basis": "written_consent"})
    assert r.status_code == 409
    actions = {i["action"] for i in client.get("/api/v1/audit-logs", headers=h,
                                                params={"page_size": 100}).json()["items"]}
    assert {"consent.create", "consent.withdraw", "suppression.create", "suppression.delete",
            "preference.set"} <= actions


def test_consent_validation_and_listing(client):
    a = register(client, "Consent Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    r = client.post(f"{C}/consents", headers=h, json={"lead_id": lead["id"], "channel": "email",
                                                       "basis": "express_consent"})
    assert r.status_code == 422  # evidence required
    r = client.post(f"{C}/consents", headers=h, json={"lead_id": lead["id"], "channel": "fax",
                                                       "basis": "express_consent", "evidence_text": "x"})
    assert r.status_code == 422
    c = _consent(client, h, lead["id"], "sms")
    assert client.get(f"{C}/consents", headers=h, params={"lead_id": lead["id"]}).json()["total"] == 1
    r = client.patch(f"{C}/consents/{c['id']}", headers=h, json={"evidence_url": "https://e.example/1"})
    assert r.status_code == 200 and r.json()["evidence_url"] == "https://e.example/1"


def test_kill_switches_and_rbac(client, monkeypatch):
    monkeypatch.setattr(checks, "now", lambda: IN_DAY)
    a = register(client, "Kill Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    _consent(client, h, lead["id"], "voice")
    assert _check(client, h, lead["id"], "voice")["allowed"]
    r = client.post(f"{C}/kill-switches", headers=h, json={"channel": "voice", "reason": "incident"})
    assert r.status_code == 201
    ks = r.json()
    assert "kill_switch_active:organization:voice" in _check(client, h, lead["id"], "voice")["reasons"]
    # org admins cannot create global switches
    assert client.post(f"{C}/kill-switches", headers=h,
                       json={"scope": "global", "reason": "x"}).status_code == 403
    rep = _member(client, a, "Sales Rep")
    assert client.post(f"{C}/kill-switches", headers=rep, json={"reason": "x"}).status_code == 403
    assert client.post(f"{C}/kill-switches/{ks['id']}/deactivate", headers=rep).status_code == 403
    assert client.post(f"{C}/kill-switches/{ks['id']}/deactivate", headers=h).json()["active"] is False
    assert _check(client, h, lead["id"], "voice")["allowed"]
    # global switch: super admin only
    assert client.post("/api/v1/admin/kill-switches", headers=a["headers"],
                       json={"scope": "global", "reason": "x"}).status_code == 403
    sa_acc = register(client, "Platform")
    _superadmin(sa_acc)
    g = client.post("/api/v1/admin/kill-switches", headers=sa_acc["headers"],
                    json={"scope": "global", "channel": "all", "reason": "platform freeze"})
    assert g.status_code == 201
    assert "kill_switch_active:global:all" in _check(client, h, lead["id"], "email")["reasons"]
    assert any(k["scope"] == "global" for k in client.get(f"{C}/kill-switches", headers=h).json())
    assert client.post(f"{C}/kill-switches/{g.json()['id']}/deactivate", headers=h).status_code == 404
    r = client.post(f"/api/v1/admin/kill-switches/{g.json()['id']}/deactivate", headers=sa_acc["headers"])
    assert r.status_code == 200 and r.json()["active"] is False


def test_calling_window_and_jurisdiction(client, monkeypatch):
    a = register(client, "Window Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    _consent(client, h, lead["id"], "voice")
    monkeypatch.setattr(checks, "now", lambda: IN_NIGHT)
    assert "outside_calling_window" in _check(client, h, lead["id"], "voice")["reasons"]
    monkeypatch.setattr(checks, "now", lambda: IN_DAY)
    assert _check(client, h, lead["id"], "voice")["allowed"]
    # unknown time zone (DEFAULT profile) blocks voice
    other = _approved_lead(client, h, country="BR", business_name="Rio Shop", phone="+55 11 0000 0000")
    _consent(client, h, other["id"], "voice")
    d = _check(client, h, other["id"], "voice")
    assert d["jurisdiction"] == "DEFAULT" and "calling_window_timezone_unknown" in d["reasons"]
    # no country at all
    nc = _approved_lead(client, h, country=None, business_name="Nowhere", phone="+1 555 000 1111")
    assert "jurisdiction_unknown" in _check(client, h, nc["id"])["reasons"]
    assert {j["code"] for j in client.get(f"{C}/jurisdictions", headers=h).json()} >= {"IN", "US", "EU", "DEFAULT"}
    assert client.post(f"{C}/check", headers=h, json={"lead_id": lead["id"], "channel": "fax"}).json()["reasons"] \
        == ["unknown_channel:fax"]


def test_within_window_multi_zone():
    rules = {"utc_offsets": [-5, -8], "voice": {"calling_window": [8, 21]}}
    assert checks.within_window(rules, "voice", datetime(2026, 1, 1, 17, 0, tzinfo=UTC))[0]  # 12:00 / 09:00
    assert not checks.within_window(rules, "voice", datetime(2026, 1, 1, 14, 0, tzinfo=UTC))[0]  # 06:00 PT


def test_cross_tenant_isolation(client):
    a, b = register(client, "Iso A"), register(client, "Iso B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    lead = _approved_lead(client, ha)
    c = _consent(client, ha, lead["id"])
    s = client.post(f"{C}/suppressions", headers=ha, json={"phone": "+1 555", "reason": "x"}).json()
    ks = client.post(f"{C}/kill-switches", headers=ha, json={"reason": "x"}).json()
    dsr = client.post(f"{C}/dsr", headers=ha, json={"type": "access", "subject_email": "a@b.example"}).json()
    assert client.get(f"{C}/consents/{c['id']}", headers=hb).status_code == 404
    assert client.post(f"{C}/consents/{c['id']}/withdraw", headers=hb, json={}).status_code == 404
    assert client.post(f"{C}/consents", headers=hb, json={"lead_id": lead["id"], "channel": "email",
                                                           "basis": "express_consent",
                                                           "evidence_text": "x"}).status_code == 404
    assert client.post(f"{C}/check", headers=hb, json={"lead_id": lead["id"], "channel": "email"}).status_code == 404
    assert client.delete(f"{C}/suppressions/{s['id']}", headers=hb).status_code == 404
    assert client.post(f"{C}/kill-switches/{ks['id']}/deactivate", headers=hb).status_code == 404
    assert client.patch(f"{C}/dsr/{dsr['id']}", headers=hb, json={"status": "in_progress"}).status_code == 404
    assert client.get(f"{C}/consents", headers=hb).json()["total"] == 0
    assert client.get(f"{C}/suppressions", headers=hb).json()["total"] == 0
    assert client.get(f"{C}/dsr", headers=hb).json()["total"] == 0
    assert all(k["organization_id"] != a["org_id"] for k in client.get(f"{C}/kill-switches", headers=hb).json())
    # B's kill switch never affects A
    client.post(f"{C}/kill-switches/{ks['id']}/deactivate", headers=ha)
    client.post(f"{C}/kill-switches", headers=hb, json={"reason": "b only"})
    assert not any(r.startswith("kill_switch") for r in _check(client, ha, lead["id"])["reasons"])


def test_viewer_rbac(client):
    a = register(client, "RBAC Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    viewer = _member(client, a, "Viewer")
    assert client.get(f"{C}/consents", headers=viewer).status_code == 200
    assert client.post(f"{C}/consents", headers=viewer, json={"lead_id": lead["id"], "channel": "email",
                                                               "basis": "express_consent",
                                                               "evidence_text": "x"}).status_code == 403
    assert client.post(f"{C}/suppressions", headers=viewer, json={"email": "a@b.c", "reason": "x"}).status_code == 403
    assert client.get(f"{C}/dsr", headers=viewer).status_code == 403
    rep = _member(client, a, "Sales Rep")
    s = client.post(f"{C}/suppressions", headers=rep, json={"email": "a@b.c", "reason": "x"})
    assert s.status_code == 201
    assert client.delete(f"{C}/suppressions/{s.json()['id']}", headers=rep).status_code == 403


def test_dsr_lifecycle(client):
    a = register(client, "DSR Org")
    h = tenant_headers(a)
    assert client.post(f"{C}/dsr", headers=h, json={"type": "deletion"}).status_code == 422
    d = client.post(f"{C}/dsr", headers=h, json={"type": "deletion", "subject_email": "X@Y.example"}).json()
    assert d["status"] == "open" and d["subject_email"] == "x@y.example" and d["due_at"]
    assert client.patch(f"{C}/dsr/{d['id']}", headers=h, json={"status": "completed"}).status_code == 422
    r = client.patch(f"{C}/dsr/{d['id']}", headers=h, json={"status": "completed", "resolution": "erased"})
    assert r.status_code == 200 and r.json()["completed_at"]
    assert client.patch(f"{C}/dsr/{d['id']}", headers=h, json={"status": "open"}).status_code == 409


def test_suspended_org_blocks_outreach(client):
    a = register(client, "Suspend Org")
    h = tenant_headers(a)
    lead = _approved_lead(client, h)
    _consent(client, h, lead["id"])
    sa_acc = register(client, "Platform 2")
    _superadmin(sa_acc)
    r = client.post(f"/api/v1/admin/organizations/{a['org_id']}/suspend", headers=sa_acc["headers"],
                    json={"reason": "abuse"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    # Suspended tenants are refused at the API layer (core/tenancy.py) ...
    r = client.post("/api/v1/compliance/check", headers=h, json={"lead_id": lead["id"], "channel": "email"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "organization_suspended"
    # ... and the outreach gate itself also blocks (defence in depth for workers that bypass the API).
    from app.modules.compliance.gate import check_outreach
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        d = check_outreach(db, uuid.UUID(a["org_id"]), uuid.UUID(lead["id"]), "email")
        assert not d.allowed and "organization_suspended" in d.reasons
    client.post(f"/api/v1/admin/organizations/{a['org_id']}/reactivate", headers=sa_acc["headers"])
    assert _check(client, h, lead["id"])["allowed"]


def test_superadmin_console(client):
    a = register(client, "Console Org")
    assert client.get("/api/v1/admin/organizations", headers=a["headers"]).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=a["headers"]).status_code == 403
    assert client.get("/api/v1/admin/usage", headers=a["headers"]).status_code == 403
    sa_acc = register(client, "Platform 3")
    _superadmin(sa_acc)
    hs = sa_acc["headers"]
    orgs = client.get("/api/v1/admin/organizations", headers=hs, params={"q": "console"}).json()
    assert any(o["id"] == a["org_id"] for o in orgs["items"])
    assert client.get("/api/v1/admin/users", headers=hs, params={"q": a["email"]}).json()["total"] == 1
    usage = client.get("/api/v1/admin/usage", headers=hs).json()
    row = next(o for o in usage["per_organization"] if o["organization_id"] == a["org_id"])
    assert row["members"] == 1 and usage["users"] >= 2
    logs = client.get("/api/v1/admin/audit-logs", headers=hs, params={"organization_id": a["org_id"]}).json()
    assert logs["total"] >= 1 and all(i["organization_id"] == a["org_id"] for i in logs["items"])
    assert client.post(f"/api/v1/admin/organizations/{uuid.uuid4()}/suspend", headers=hs,
                       json={"reason": "x"}).status_code == 404


def test_integrations_never_return_secrets(client):
    a = register(client, "Integr Org")
    h = tenant_headers(a)
    items = client.get("/api/v1/integrations", headers=h).json()
    assert all(i["status"] == "not_configured" for i in items)
    r = client.put("/api/v1/integrations/twilio", headers=h, json={"credentials": {"account_sid": "AC123"}})
    assert r.status_code == 200 and r.json()["status"] == "not_configured"
    r = client.put("/api/v1/integrations/twilio", headers=h,
                   json={"credentials": {"auth_token": "s3cr3t-token"}, "config": {"from_number": "+15550001"}})
    assert r.status_code == 200 and r.json()["status"] == "configured"
    assert "s3cr3t-token" not in r.text and "AC123" not in r.text
    listing = client.get("/api/v1/integrations", headers=h)
    assert "s3cr3t-token" not in listing.text
    tw = next(i for i in listing.json() if i["provider"] == "twilio")
    assert tw["credential_names"] == ["account_sid", "auth_token"]
    from app.modules.administration.router import get_credential

    with tenant_session(uuid.UUID(a["org_id"])) as db:
        assert get_credential(db, uuid.UUID(a["org_id"]), "twilio", "auth_token") == "s3cr3t-token"
        from sqlalchemy import select

        from app.modules.administration.models import IntegrationCredential
        assert all("s3cr3t" not in c for c in db.scalars(select(IntegrationCredential.secret_enc)))
    assert client.put("/api/v1/integrations/nope", headers=h, json={}).status_code == 404
    viewer = _member(client, a, "Viewer")
    assert client.put("/api/v1/integrations/twilio", headers=viewer, json={}).status_code == 403
    b = register(client, "Integr B")
    tb = next(i for i in client.get("/api/v1/integrations", headers=tenant_headers(b)).json()
              if i["provider"] == "twilio")
    assert tb["status"] == "not_configured"
    r = client.delete("/api/v1/integrations/twilio/credentials", headers=h)
    assert r.json()["status"] == "not_configured" and r.json()["credential_names"] == []


def test_mfa_flow(client):
    a = register(client, "MFA Org")
    hh = a["headers"]
    assert client.post("/api/v1/auth/mfa/verify", headers=hh, json={"code": "123456"}).status_code == 409
    setup = client.post("/api/v1/auth/mfa/setup", headers=hh).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    totp = pyotp.TOTP(setup["secret"])
    assert client.post("/api/v1/auth/mfa/verify", headers=hh, json={"code": "000000"}).status_code in (422,)
    r = client.post("/api/v1/auth/mfa/verify", headers=hh, json={"code": totp.now()})
    assert r.status_code == 200 and r.json()["mfa_enabled"]
    with SessionLocal() as db:
        from sqlalchemy import select
        enc = db.scalar(select(User.mfa_secret_enc).where(User.email == a["email"]))
        assert enc and setup["secret"] not in enc
    login = {"email": a["email"], "password": a["password"]}
    r = client.post("/api/v1/auth/login", json=login)
    assert r.status_code == 401 and r.json()["error"]["code"] == "mfa_required"
    r = client.post("/api/v1/auth/login", json={**login, "otp_code": "000000"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_otp"
    r = client.post("/api/v1/auth/login", json={**login, "otp_code": totp.now()})
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.post("/api/v1/auth/mfa/disable", headers=hh,
                       json={"code": totp.now(), "password": "wrong"}).status_code == 422
    r = client.post("/api/v1/auth/mfa/disable", headers=hh, json={"code": totp.now(), "password": a["password"]})
    assert r.status_code == 200 and not r.json()["mfa_enabled"]
    assert client.post("/api/v1/auth/login", json=login).status_code == 200


def test_notifications_and_tickets(client):
    a, b = register(client, "Notif A"), register(client, "Notif B")
    h = tenant_headers(a)
    from app.modules.administration.router import notify

    with tenant_session(uuid.UUID(a["org_id"])) as db:
        n = notify(db, uuid.UUID(a["org_id"]), None, "system", "Welcome")
        db.commit()
        nid = str(n.id)
    assert client.get("/api/v1/notifications", headers=h).json()["total"] == 1
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=tenant_headers(b)).status_code == 404
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=h).json()["read_at"]
    assert client.get("/api/v1/notifications", headers=h, params={"unread": True}).json()["total"] == 0
    t = client.post("/api/v1/support/tickets", headers=h, json={"subject": "Help me", "body": "Details"})
    assert t.status_code == 201
    assert client.get("/api/v1/support/tickets", headers=h).json()["total"] == 1
    assert client.get("/api/v1/support/tickets", headers=tenant_headers(b)).json()["total"] == 0
