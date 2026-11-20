import uuid
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.modules.marketplace import engine
from tests.conftest import register, tenant_headers

M = "/api/v1/marketplace"


def _cat(client, h, slug="architecture"):
    cats = client.get(f"{M}/categories", headers=h).json()
    return next(c["id"] for c in cats if c["slug"] == slug)


def _provider(client, h, **kw):
    r = client.post(f"{M}/providers", headers=h, json={"business_name": "Studio", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _requirement(client, h, cat, email="buyer@example.com", **kw):
    body = {"customer": {"full_name": "Buyer", "email": email}, "category_id": cat, "title": "New villa design",
            "city": "Pune", "country": "in", "budget_min": "500000", "budget_max": "1500000", "currency": "INR",
            "contact_permission": True, "consent_reference": "web-form-2026-11-01", **kw}
    r = client.post(f"{M}/requirements", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _verify(client, h, pid):
    r = client.post(f"{M}/providers/{pid}/verify", headers=h,
                    json={"decision": "verified", "evidence": "RERA certificate checked on state portal by staff",
                          "reference": "P52100012345"})
    assert r.status_code == 201, r.text


def _add_member(client, owner, other, role):
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text


def _user_id(client, acct):
    return client.get("/api/v1/auth/me", headers=acct["headers"]).json()["user"]["id"]


def _referral(client, h, req_id, pid, key=None):
    hdr = {**h, "Idempotency-Key": key} if key else h
    return client.post("/api/v1/referrals", headers=hdr, json={"requirement_id": req_id, "provider_id": pid})


def _walk(client, h, rid, *statuses, deal_value=None):
    for s in statuses:
        body = {"status": s}
        if s == "converted" and deal_value:
            body["deal_value"] = deal_value
        r = client.post(f"/api/v1/referrals/{rid}/status", headers=h, json=body)
        assert r.status_code == 200, r.text


TO_CONVERTED = ("invited", "accepted", "introduced", "meeting", "quotation", "converted")


# ---------------------------------------------------------------- matching
def test_matching_explanations_and_unverified_ranked_lower(client):
    a = register(client, "Mkt Match")
    h = tenant_headers(a)
    cat = _cat(client, h)
    common = {"category_ids": [cat], "service_areas": [{"city": "Pune", "country": "IN"}], "experience_years": 12,
              "price_min": "400000", "price_max": "2000000"}
    good = _provider(client, h, **{**common, "business_name": "Verified Arch"})
    _verify(client, h, good["id"])
    unv = _provider(client, h, **{**common, "business_name": "Unverified Arch"})
    far = _provider(client, h, business_name="Far Away", category_ids=[_cat(client, h, "construction")],
                    service_areas=[{"city": "Oslo", "country": "NO"}], availability="unavailable")
    req = _requirement(client, h, cat)
    r = client.post(f"{M}/requirements/{req['id']}/match", headers=h)
    assert r.status_code == 200, r.text
    ms = r.json()
    assert [m["provider_id"] for m in ms] == [good["id"], unv["id"], far["id"]]
    top = ms[0]
    assert top["score"] == 100 and top["explanation"]["unverified_flag"] is False
    assert set(top["explanation"]["factors"]) == {"category", "location", "budget", "availability", "experience",
                                                  "verification", "preferences"}
    assert "Serves Pune" in top["explanation"]["factors"]["location"]["reason"]
    assert ms[1]["explanation"]["unverified_flag"] is True and ms[1]["score"] < top["score"]
    assert ms[2]["explanation"]["factors"]["category"]["score"] == 0
    # persisted
    assert len(client.get(f"{M}/requirements/{req['id']}/matches", headers=h).json()) == 3
    assert client.get(f"{M}/requirements/{req['id']}", headers=h).json()["status"] == "matched"
    # configurable weights: only location matters -> verified/unverified differ by penalty only
    w = {k: 0 for k in engine.DEFAULT_WEIGHTS} | {"location": 10}
    assert client.put(f"{M}/matching-weights", headers=h, json=w).status_code == 200
    ms = client.post(f"{M}/requirements/{req['id']}/match", headers=h).json()
    assert ms[0]["score"] == 100 and ms[1]["score"] == 85 and ms[2]["score"] == 0


def test_preferences_factor():
    req = engine.ReqView("c", "Pune", "IN", None, None, "INR", {"verified_only": True, "keywords": ["villa"]})
    prov = engine.ProvView({"c"}, [], None, None, "INR", "available", 5, "verified", "we design villas")
    _, ex = engine.score_match(req, prov, engine.DEFAULT_WEIGHTS)
    assert ex["factors"]["preferences"]["score"] == 1


# ---------------------------------------------------------------- providers / verification / docs
def test_provider_documents_and_manual_verification(client):
    a = register(client, "Mkt Docs")
    h = tenant_headers(a)
    p = _provider(client, h)
    url = f"{M}/providers/{p['id']}/documents"
    auth = {k: v for k, v in h.items()}
    r = client.post(url, headers=auth, data={"document_type": "RERA"},
                    files={"file": ("rera.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["document_type"] == "rera" and doc["size_bytes"] == 13
    bad = client.post(url, headers=auth, data={"document_type": "license"},
                      files={"file": ("x.exe", b"MZ....", "application/octet-stream")})
    assert bad.status_code == 415
    spoof = client.post(url, headers=auth, data={"document_type": "license"},
                        files={"file": ("x.pdf", b"MZ....", "application/pdf")})
    assert spoof.status_code == 415
    big = client.post(url, headers=auth, data={"document_type": "license"},
                      files={"file": ("b.pdf", b"%PDF" + b"0" * (5 * 1024 * 1024), "application/pdf")})
    assert big.status_code == 413
    assert len(client.get(url, headers=h).json()) == 1
    dl = client.get(f"{url}/{doc['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == b"%PDF-1.4 test"
    v = f"{M}/providers/{p['id']}/verify"
    # registry checks are not integrated -> never fabricated
    r = client.post(v, headers=h, json={"method": "registry", "registry_name": "rera", "decision": "verified"})
    assert r.status_code == 501 and r.json()["error"]["details"]["status"] == "not_configured"
    assert all(x["status"] == "not_configured" for x in client.get(f"{M}/registries", headers=h).json())
    assert client.post(v, headers=h, json={"decision": "verified"}).status_code == 422  # evidence required
    r = client.post(v, headers=h, json={"decision": "verified", "document_ids": [doc["id"]], "reference": "R1"})
    assert r.status_code == 201 and r.json()["method"] == "manual"
    assert client.get(f"{M}/providers/{p['id']}", headers=h).json()["verification_status"] == "verified"
    assert len(client.get(f"{M}/providers/{p['id']}/verifications", headers=h).json()) == 1


# ---------------------------------------------------------------- referrals
def test_referral_lifecycle_and_idempotency(client):
    a = register(client, "Mkt Ref")
    h = tenant_headers(a)
    cat = _cat(client, h)
    p = _provider(client, h, category_ids=[cat])
    req = _requirement(client, h, cat)
    client.post(f"{M}/requirements/{req['id']}/match", headers=h)
    r1 = _referral(client, h, req["id"], p["id"], key="ref-key-1")
    assert r1.status_code == 201, r1.text
    r2 = _referral(client, h, req["id"], p["id"], key="ref-key-1")
    assert r2.status_code == 201 and r2.json()["id"] == r1.json()["id"]
    assert r2.headers.get("Idempotent-Replayed") == "true"
    other = _provider(client, h, business_name="Other")
    assert _referral(client, h, req["id"], other["id"], key="ref-key-1").status_code == 409  # key reuse
    assert _referral(client, h, req["id"], p["id"]).status_code == 409  # duplicate pair
    assert client.get("/api/v1/referrals", headers=h).json()["total"] == 1
    rid = r1.json()["id"]
    assert r1.json()["status"] == "matched"
    s = client.post(f"/api/v1/referrals/{rid}/status", headers=h, json={"status": "converted"})
    assert s.status_code == 409 and "allowed" in s.json()["error"]["details"]
    assert client.post(f"/api/v1/referrals/{rid}/status", headers=h, json={"status": "bogus"}).status_code == 422
    _walk(client, h, rid, *TO_CONVERTED)
    assert client.post(f"/api/v1/referrals/{rid}/status", headers=h, json={"status": "lost"}).status_code == 409
    ev = client.get(f"/api/v1/referrals/{rid}/events", headers=h).json()
    assert [e["to_status"] for e in ev] == ["matched", *TO_CONVERTED]


def test_referral_requires_contact_permission(client):
    a = register(client, "Mkt Consent")
    h = tenant_headers(a)
    cat = _cat(client, h)
    p = _provider(client, h)
    req = _requirement(client, h, cat, contact_permission=False, consent_reference=None)
    assert _referral(client, h, req["id"], p["id"]).status_code == 422
    bad = client.post(f"{M}/requirements", headers=h, json={
        "customer": {"full_name": "B", "email": "b@example.com"}, "category_id": cat, "title": "x",
        "contact_permission": True})
    assert bad.status_code == 422


# ---------------------------------------------------------------- commissions
def test_commission_calculation_and_splits():
    assert engine.compute_commission("fixed", Decimal("25000"), None, None) == Decimal("25000.00")
    assert engine.compute_commission("percentage", Decimal("2.5"), Decimal("1234567.89"), None) == Decimal("30864.20")
    assert engine.compute_commission("percentage", Decimal("1"), Decimal("0.50"), None) == Decimal("0.01")  # half-up
    assert engine.compute_commission("negotiated", None, None, Decimal("999.999")) == Decimal("1000.00")
    with pytest.raises(AppError):
        engine.compute_commission("percentage", Decimal("2"), None, None)
    with pytest.raises(AppError):
        engine.validate_splits([{"party": "a", "pct": 60}, {"party": "b", "pct": "40.01"}])
    with pytest.raises(AppError):
        engine.validate_splits([{"party": "a", "pct": 50}, {"party": "a", "pct": 10}])
    s = engine.validate_splits([{"party": "a", "pct": "33.33"}, {"party": "b", "pct": "33.33"},
                                {"party": "c", "pct": "33.34"}])
    parts = engine.split_amount(Decimal("100.00"), s)
    assert sum(Decimal(p["amount"]) for p in parts) == Decimal("100.00")
    assert [p["amount"] for p in parts] == ["33.33", "33.33", "33.34"]
    parts = engine.split_amount(Decimal("0.01"), engine.validate_splits([{"party": "a", "pct": 50},
                                                                          {"party": "b", "pct": 50}]))
    assert sum(Decimal(p["amount"]) for p in parts) == Decimal("0.01") and all(
        Decimal(p["amount"]) >= 0 for p in parts)
    parts = engine.split_amount(Decimal("1000"), engine.validate_splits([{"party": "agent", "pct": 60}]))
    assert parts == [{"party": "agent", "pct": "60", "amount": "600.00"},
                     {"party": "organization", "pct": "40", "amount": "400.00"}]


def _converted_with_agreement(client, h, agreement):
    cat = _cat(client, h)
    p = _provider(client, h, category_ids=[cat])
    req = _requirement(client, h, cat, email=f"c{uuid.uuid4().hex[:6]}@example.com")
    rid = _referral(client, h, req["id"], p["id"]).json()["id"]
    r = client.post("/api/v1/commissions/agreements", headers=h, json={"provider_id": p["id"], **agreement})
    assert r.status_code == 201, r.text
    return p, rid, r.json()


def test_commission_ledger_settlement_rules(client):
    a = register(client, "Mkt Ledger")
    h = tenant_headers(a)
    base = "/api/v1/referrals"
    p, rid, ag = _converted_with_agreement(client, h, {
        "type": "percentage", "value": "2", "currency": "INR",
        "splits": [{"party": "agent", "pct": "70"}, {"party": "partner", "pct": "30"}]})
    bad = client.post("/api/v1/commissions/agreements", headers=h, json={
        "provider_id": p["id"], "type": "fixed", "value": "10", "splits": [{"party": "a", "pct": 80},
                                                                            {"party": "b", "pct": 30}]})
    assert bad.status_code == 422
    # not converted yet
    assert client.post(f"{base}/{rid}/commission/accrue", headers=h, json={"deal_value": "1000000"}).status_code == 409
    _walk(client, h, rid, "matched", *TO_CONVERTED)
    assert client.post(f"{base}/{rid}/commission/accrue", headers=h, json={}).status_code == 422  # no deal value
    r = client.post(f"{base}/{rid}/commission/accrue", headers=h, json={"deal_value": "1000000.50"})
    assert r.status_code == 201 and r.json()["amount"] == "20000.01"
    assert client.post(f"{base}/{rid}/commission/accrue", headers=h,
                       json={"deal_value": "1"}).status_code == 409  # once
    # settle before invoice/payment refused
    s = client.post(f"{base}/{rid}/commission/settle", headers=h)
    assert s.status_code == 409 and s.json()["error"]["code"] == "settlement_conditions_unmet"
    assert client.post(f"{base}/{rid}/commission/invoice", headers=h, json={"amount": "99999"}).status_code == 422
    assert client.post(f"{base}/{rid}/commission/invoice", headers=h, json={}).status_code == 201
    assert client.post(f"{base}/{rid}/commission/payment", headers=h, json={"amount": "10000"}).status_code == 201
    assert client.post(f"{base}/{rid}/commission/settle", headers=h).status_code == 409  # partially paid
    assert client.post(f"{base}/{rid}/commission/refund", headers=h, json={"amount": "500"}).status_code == 201
    assert client.post(f"{base}/{rid}/commission/refund", headers=h, json={"amount": "10000"}).status_code == 422
    assert client.post(f"{base}/{rid}/commission/payment", headers=h, json={}).status_code == 201  # rest
    # dispute blocks settlement
    d = client.post(f"{base}/{rid}/commission/disputes", headers=h, json={"reason": "Deal value disputed"})
    assert d.status_code == 201
    view = client.get(f"{base}/{rid}/commission", headers=h).json()
    assert view["settleable"] is False and "There is an open dispute" in view["blockers"]
    assert client.post(f"{base}/{rid}/commission/settle", headers=h).status_code == 409
    r = client.post(f"/api/v1/commissions/disputes/{d.json()['id']}/resolve", headers=h,
                    json={"status": "rejected", "resolution": "Deal value confirmed by invoice"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    s = client.post(f"{base}/{rid}/commission/settle", headers=h)
    assert s.status_code == 201, s.text
    alloc = s.json()["data"]["allocation"]
    assert [x["amount"] for x in alloc] == ["14000.01", "6000.00"]
    assert client.post(f"{base}/{rid}/commission/settle", headers=h).status_code == 409  # already
    assert client.post(f"{base}/{rid}/commission/refund", headers=h, json={"amount": "1"}).status_code == 409
    summ = client.get("/api/v1/commissions", headers=h).json()
    b = summ["balances"][0]
    assert b["currency"] == "INR" and b["accrued"] == "20000.01" and b["paid"] == "20500.01"
    assert b["refunded"] == "500.00" and b["settled"] == "20000.01" and b["outstanding"] == "0.00"
    assert summ["open_disputes"] == 0


def test_fixed_commission_dispute_reversal(client):
    a = register(client, "Mkt Reversal")
    h = tenant_headers(a)
    _, rid, _ = _converted_with_agreement(client, h, {"type": "fixed", "value": "5000", "currency": "inr"})
    _walk(client, h, rid, "matched", *TO_CONVERTED)
    base = f"/api/v1/referrals/{rid}/commission"
    assert client.post(f"{base}/accrue", headers=h, json={}).json()["amount"] == "5000.00"
    d = client.post(f"{base}/disputes", headers=h, json={"reason": "Customer cancelled", "amount": "2000"}).json()
    r = client.post(f"/api/v1/commissions/disputes/{d['id']}/resolve", headers=h,
                    json={"status": "resolved", "resolution": "Partial credit", "reversal_amount": "2000"})
    assert r.status_code == 200
    view = client.get(base, headers=h).json()
    assert view["balances"][0]["accrued"] == "5000.00" and view["balances"][0]["reversed"] == "2000.00"
    assert client.post(f"{base}/invoice", headers=h, json={}).json()["amount"] == "3000.00"


# ---------------------------------------------------------------- tenancy / rbac / portals
def test_cross_tenant_and_rbac(client):
    a, b = register(client, "Mkt A"), register(client, "Mkt B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    p = _provider(client, ha)
    cat = _cat(client, ha)
    req = _requirement(client, ha, cat)
    assert client.get(f"{M}/providers/{p['id']}", headers=hb).status_code == 404
    assert client.get(f"{M}/requirements/{req['id']}", headers=hb).status_code == 404
    assert _referral(client, hb, req["id"], p["id"]).status_code == 404
    rid = _referral(client, ha, req["id"], p["id"]).json()["id"]
    assert client.get(f"/api/v1/referrals/{rid}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/referrals/{rid}/commission", headers=hb).status_code == 404
    v = register(client, "Mkt Viewer home")
    _add_member(client, a, v, "Viewer")
    hv = tenant_headers(v, a["org_id"])
    assert client.get(f"{M}/providers", headers=hv).status_code == 403
    assert client.post(f"{M}/providers", headers=hv, json={"business_name": "x"}).status_code == 403
    assert client.get("/api/v1/commissions", headers=hv).status_code == 403
    assert client.post(f"/api/v1/referrals/{rid}/commission/settle", headers=hv).status_code == 403
    m = register(client, "Mkt Manager home")
    _add_member(client, a, m, "Manager")
    assert client.get("/api/v1/commissions", headers=tenant_headers(m, a["org_id"])).status_code == 403


def test_provider_and_customer_portals(client):
    a = register(client, "Mkt Portal")
    h = tenant_headers(a)
    pu, other = register(client, "Portal prov home"), register(client, "Portal other home")
    _add_member(client, a, pu, "Viewer")
    _add_member(client, a, other, "Viewer")
    cat = _cat(client, h)
    mine = _provider(client, h, business_name="Mine", category_ids=[cat], portal_user_id=_user_id(client, pu))
    theirs = _provider(client, h, business_name="Theirs", category_ids=[cat])
    assert client.post(f"{M}/providers", headers=h, json={
        "business_name": "x", "portal_user_id": str(uuid.uuid4())}).status_code == 422
    req = _requirement(client, h, cat, email=other["email"].upper())
    r_mine = _referral(client, h, req["id"], mine["id"]).json()["id"]
    r_theirs = _referral(client, h, req["id"], theirs["id"]).json()["id"]
    hp = tenant_headers(pu, a["org_id"])
    lst = client.get("/api/v1/portal/provider/referrals", headers=hp).json()
    assert [x["id"] for x in lst] == [r_mine]
    assert lst[0]["customer"] is None  # contact withheld until accepted
    assert client.post(f"/api/v1/portal/provider/referrals/{r_theirs}/accept", headers=hp).status_code == 404
    assert client.post(f"/api/v1/portal/provider/referrals/{r_mine}/accept", headers=hp).status_code == 409
    _walk(client, h, r_mine, "matched", "invited")
    acc = client.post(f"/api/v1/portal/provider/referrals/{r_mine}/accept", headers=hp)
    assert acc.status_code == 200 and acc.json()["customer"]["email"] == other["email"].lower()
    assert client.post(f"/api/v1/portal/provider/referrals/{r_mine}/status", headers=hp,
                       json={"status": "introduced"}).status_code == 403  # staff-only step
    assert client.get("/api/v1/portal/provider/earnings", headers=hp).json() == []
    # someone without linkage sees nothing
    ho = tenant_headers(other, a["org_id"])
    assert client.get("/api/v1/portal/provider/referrals", headers=ho).json() == []
    # customer portal: matched by email
    reqs = client.get("/api/v1/portal/customer/requirements", headers=ho).json()
    assert [x["id"] for x in reqs] == [req["id"]]
    det = client.get(f"/api/v1/portal/customer/requirements/{req['id']}", headers=ho).json()
    assert {x["provider_name"] for x in det["referrals"]} == {"Mine", "Theirs"}
    assert client.get("/api/v1/portal/customer/requirements", headers=hp).json() == []
    assert client.get(f"/api/v1/portal/customer/requirements/{req['id']}", headers=hp).status_code == 404
