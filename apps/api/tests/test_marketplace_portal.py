from datetime import timedelta

from sqlalchemy import select

from app.core.db import SessionLocal, utcnow
from app.core.security import create_portal_token
from app.modules.identity.models import AuditLog
from app.modules.marketplace_portal.models import PortalToken
from tests.conftest import register, tenant_headers

M = "/api/v1/marketplace"
P = "/api/v1/marketplace-portal"


def _cat(client, h):
    return next(c["id"] for c in client.get(f"{M}/categories", headers=h).json() if c["slug"] == "architecture")


def _provider(client, h, name, email):
    r = client.post(f"{M}/providers", headers=h, json={"business_name": name, "email": email})
    assert r.status_code == 201, r.text
    return r.json()


def _req(client, h, cat, email, title="Villa design"):
    r = client.post(f"{M}/requirements", headers=h, json={
        "customer": {"full_name": "Buyer", "email": email, "phone": "+911234567890"}, "category_id": cat,
        "title": title, "city": "Pune", "country": "in", "contact_permission": True, "consent_reference": "form-1"})
    assert r.status_code == 201, r.text
    return r.json()


def _refer(client, h, req_id, pid, invited=True):
    r = client.post("/api/v1/referrals", headers=h, json={"requirement_id": req_id, "provider_id": pid})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    if invited:
        for s in ("matched", "invited"):
            if s == "matched" and r.json()["status"] == "matched":
                continue
            assert client.post(f"/api/v1/referrals/{rid}/status", headers=h, json={"status": s}).status_code == 200
    return rid


def _token_from(link):
    return link.split("token=")[1]


def _signin(client, invite_json):
    """Exchange the (simulated) invite link for a portal session; returns auth headers."""
    r = client.post(f"{P}/exchange", json={"token": _token_from(invite_json["dev_link"])})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['portal_token']}"}


def _setup(client):
    a = register(client, "Portal Org")
    h = tenant_headers(a)
    cat = _cat(client, h)
    p1 = _provider(client, h, "Studio One", "one@studio.example.com")
    p2 = _provider(client, h, "Studio Two", "two@studio.example.com")
    q1 = _req(client, h, cat, "alice@buyer.example.com", "Alice villa")
    q2 = _req(client, h, cat, "bob@buyer.example.com", "Bob flat")
    r1 = _refer(client, h, q1["id"], p1["id"])
    r2 = _refer(client, h, q2["id"], p2["id"])
    return {"a": a, "h": h, "p1": p1, "p2": p2, "q1": q1, "q2": q2, "r1": r1, "r2": r2}


def test_invite_link_and_provider_flow(client):
    s = _setup(client)
    inv = client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"])
    assert inv.status_code == 201, inv.text
    assert inv.json()["simulated"] is True and "/portal/auth?token=" in inv.json()["dev_link"]
    ph = _signin(client, inv.json())
    me = client.get(f"{P}/me", headers=ph).json()
    assert me["role"] == "provider" and me["subject_id"] == s["p1"]["id"]
    assert client.get(f"{P}/provider/profile", headers=ph).json()["business_name"] == "Studio One"
    refs = client.get(f"{P}/provider/referrals", headers=ph).json()
    assert [r["id"] for r in refs] == [s["r1"]]
    assert refs[0]["customer"] is None  # contact withheld until accepted
    # another provider's referral is invisible and untouchable
    assert client.post(f"{P}/provider/referrals/{s['r2']}/accept", headers=ph).status_code == 404
    acc = client.post(f"{P}/provider/referrals/{s['r1']}/accept", headers=ph)
    assert acc.status_code == 200 and acc.json()["status"] == "accepted"
    assert acc.json()["customer"]["email"] == "alice@buyer.example.com"
    assert client.post(f"{P}/provider/referrals/{s['r1']}/decline", headers=ph).status_code == 409
    com = client.get(f"{P}/provider/commissions", headers=ph).json()
    assert [x["referral_id"] for x in com["referrals"]] == [s["r1"]] and com["totals"] == []
    # customer area not available to a provider session
    assert client.get(f"{P}/customer/requirements", headers=ph).status_code == 403
    # staff view reflects the portal action and audit entries exist
    assert client.get(f"/api/v1/referrals/{s['r1']}", headers=s["h"]).json()["status"] == "accepted"
    with SessionLocal() as db:
        actions = set(db.scalars(select(AuditLog.action).where(AuditLog.action.like("marketplace.portal.%"))))
    assert {"marketplace.portal.invite", "marketplace.portal.login", "marketplace.portal.referral_accepted"} <= actions


def test_provider_decline(client):
    s = _setup(client)
    inv = client.post(f"{M}/providers/{s['p2']['id']}/portal-invite", headers=s["h"]).json()
    ph = _signin(client, inv)
    r = client.post(f"{P}/provider/referrals/{s['r2']}/decline", headers=ph)
    assert r.status_code == 200 and r.json()["status"] == "declined" and r.json()["customer"] is None


def test_customer_sees_only_own_requirement_and_withdraws(client):
    s = _setup(client)
    inv = client.post(f"{M}/requirements/{s['q1']['id']}/portal-invite", headers=s["h"])
    assert inv.status_code == 201 and inv.json()["role"] == "customer"
    ch = _signin(client, inv.json())
    reqs = client.get(f"{P}/customer/requirements", headers=ch).json()
    assert [r["id"] for r in reqs] == [s["q1"]["id"]]
    assert reqs[0]["referrals"][0]["provider_name"] == "Studio One"
    assert client.get(f"{P}/customer/requirements/{s['q2']['id']}", headers=ch).status_code == 404
    assert client.post(f"{P}/customer/requirements/{s['q2']['id']}/withdraw-contact", headers=ch).status_code == 404
    w = client.post(f"{P}/customer/requirements/{s['q1']['id']}/withdraw-contact", headers=ch)
    assert w.status_code == 200 and w.json()["contact_permission"] is False
    assert client.get(f"{M}/requirements/{s['q1']['id']}", headers=s["h"]).json()["contact_permission"] is False
    assert client.get(f"{P}/provider/referrals", headers=ch).status_code == 403


def test_login_flow_and_no_enumeration(client):
    s = _setup(client)
    client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"])
    unknown = client.post(f"{P}/login", json={"email": "nobody@nowhere.example.com"})
    assert unknown.status_code == 202 and unknown.json()["dev_link"] is None
    known = client.post(f"{P}/login", json={"email": "ONE@studio.example.com"})
    assert known.status_code == 202 and known.json()["dev_link"]
    ph = _signin(client, known.json())
    assert client.get(f"{P}/me", headers=ph).status_code == 200


def test_token_is_single_use_expired_and_unknown_rejected(client):
    s = _setup(client)
    inv = client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"]).json()
    tok = _token_from(inv["dev_link"])
    assert client.post(f"{P}/exchange", json={"token": tok}).status_code == 200
    assert client.post(f"{P}/exchange", json={"token": tok}).status_code == 400  # used
    inv2 = client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"]).json()
    tok2 = _token_from(inv2["dev_link"])
    with SessionLocal() as db:
        t = db.scalars(select(PortalToken).where(PortalToken.used_at.is_(None))
                       .order_by(PortalToken.created_at.desc())).first()
        t.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.post(f"{P}/exchange", json={"token": tok2}).status_code == 400  # expired
    assert client.post(f"{P}/exchange", json={"token": "x" * 40}).status_code == 400  # unknown


def test_token_types_not_interchangeable(client):
    s = _setup(client)
    inv = client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"]).json()
    ph = _signin(client, inv)
    assert client.get("/api/v1/auth/me", headers=ph).status_code == 401
    assert client.get(f"{M}/providers", headers={**ph, "X-Organization-Id": s["a"]["org_id"]}).status_code == 401
    assert client.get(f"{P}/me", headers=s["a"]["headers"]).status_code == 401  # staff token on portal
    assert client.get(f"{P}/me").status_code == 401
    assert client.get(f"{P}/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_cross_tenant_isolation_and_revocation(client):
    s = _setup(client)
    b = register(client, "Other Org")
    hb = tenant_headers(b)
    cat_b = _cat(client, hb)
    pb = _provider(client, hb, "Foreign Studio", "one@studio.example.com")  # same email, different tenant
    qb = _req(client, hb, cat_b, "alice@buyer.example.com", "Foreign req")
    rb = _refer(client, hb, qb["id"], pb["id"])
    inv_a = client.post(f"{M}/providers/{s['p1']['id']}/portal-invite", headers=s["h"]).json()
    inv_b = client.post(f"{M}/providers/{pb['id']}/portal-invite", headers=hb).json()
    ha, hbp = _signin(client, inv_a), _signin(client, inv_b)
    assert [r["id"] for r in client.get(f"{P}/provider/referrals", headers=ha).json()] == [s["r1"]]
    assert [r["id"] for r in client.get(f"{P}/provider/referrals", headers=hbp).json()] == [rb]
    assert client.post(f"{P}/provider/referrals/{rb}/accept", headers=ha).status_code == 404
    assert client.post(f"{P}/provider/referrals/{s['r1']}/accept", headers=hbp).status_code == 404
    # a token claiming org A but a subject from org B is refused
    forged = create_portal_token(
        next(a["id"] for a in client.get(f"{M}/portal-access", headers=hb).json()),
        __import__("uuid").UUID(s["a"]["org_id"]), "provider", __import__("uuid").UUID(pb["id"]))
    assert client.get(f"{P}/provider/profile", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    # staff cannot invite or manage another tenant's records
    assert client.post(f"{M}/providers/{pb['id']}/portal-invite", headers=s["h"]).status_code == 404
    # revoke: existing session stops working
    acct = client.get(f"{M}/portal-access", headers=s["h"]).json()[0]
    assert client.delete(f"{M}/portal-access/{acct['id']}", headers=s["h"]).status_code == 204
    assert client.get(f"{P}/provider/profile", headers=ha).status_code == 401
    assert client.delete(f"{M}/portal-access/{acct['id']}", headers=hb).status_code == 404


def test_invite_requires_permission_and_email(client):
    a = register(client, "Perm Org")
    h = tenant_headers(a)
    r = client.post(f"{M}/providers", headers=h, json={"business_name": "No Email"})
    assert client.post(f"{M}/providers/{r.json()['id']}/portal-invite", headers=h).status_code == 422
    assert client.post(f"{M}/providers/{r.json()['id']}/portal-invite").status_code == 401
