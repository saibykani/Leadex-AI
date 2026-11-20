import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.db import tenant_session, utcnow
from app.core.errors import AppError
from app.modules.billing import service as svc
from app.modules.billing.models import Subscription
from tests.conftest import register, tenant_headers

B = "/api/v1/billing"


def _member(client, owner, role):
    other = register(client, f"Home {uuid.uuid4().hex[:6]}")
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text
    return tenant_headers(other, owner["org_id"])


def _sub_update(org_id, **fields):
    with tenant_session(uuid.UUID(org_id)) as db:
        sub = db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
        for k, v in fields.items():
            setattr(sub, k, v)
        db.commit()


def test_plans_and_lazy_trial(client):
    a = register(client, "Bill Trial")
    h = tenant_headers(a)
    plans = client.get(f"{B}/plans", headers=h).json()
    assert [p["code"] for p in plans] == ["free_trial", "starter", "professional", "business", "enterprise",
                                          "white_label"]
    assert all(p["currency"] == "USD" for p in plans) and plans[1]["price_monthly"] == "49.00"
    assert set(plans[0]["limits"]) == set(svc.RESOURCES)
    sub = client.get(f"{B}/subscription", headers=h).json()
    assert sub["plan"]["code"] == "free_trial" and sub["status"] == "trialing" and sub["trial_end"]
    usage = {i["resource"]: i for i in client.get(f"{B}/usage", headers=h).json()["items"]}
    assert usage["users"]["used"] == 1 and usage["users"]["limit"] == 2 and usage["users"]["level"] == "warning"
    provs = {p["name"]: p["status"] for p in client.get(f"{B}/providers", headers=h).json()}
    assert provs == {"simulated": "simulated", "stripe": "not_configured", "razorpay": "not_configured"}


def test_plan_limit_enforced_with_alerts(client):
    a = register(client, "Bill Limits")
    h = tenant_headers(a)
    for i in range(3):  # Free Trial allows 3 workflows
        assert client.post("/api/v1/workflows", headers=h, json={"name": f"w{i}"}).status_code == 201
    r = client.post("/api/v1/workflows", headers=h, json={"name": "too many"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "plan_limit_reached"
    alerts = client.get(f"{B}/alerts", headers=h).json()
    got = sorted(x["threshold"] for x in alerts if x["kind"] == "plan_limit" and x["resource"] == "workflows")
    assert got == [50, 80, 100]
    usage = {i["resource"]: i for i in client.get(f"{B}/usage", headers=h).json()["items"]}
    assert usage["workflows"]["percent"] == 100.0 and usage["workflows"]["level"] == "exceeded"


def test_record_usage_budget_alerts_and_hard_stop(client):
    a = register(client, "Bill Budget")
    h = tenant_headers(a)
    r = client.put(f"{B}/budget", headers=h, json={"monthly_limit": "10.00", "hard_stop": True})
    assert r.status_code == 200 and r.json()["paid_fallback_enabled"] is False
    org = uuid.UUID(a["org_id"])
    with tenant_session(org) as db:
        svc.record_usage(db, org, "voice_minutes", 5, cost=Decimal("6.00"))
        svc.record_usage(db, org, "ai_conversations", 1, cost=Decimal("3.00"))
        db.commit()
        try:
            svc.record_usage(db, org, "voice_minutes", 1, cost=Decimal("2.00"))
            raise AssertionError("expected budget hard stop")
        except AppError as e:
            assert e.status_code == 402 and e.code == "budget_exceeded"
        db.rollback()
    b = client.get(f"{B}/budget", headers=h).json()
    assert b["month_spend"] == "9.00"
    assert sorted(x["threshold"] for x in b["alerts"] if x["kind"] == "budget") == [50, 80]
    usage = client.get(f"{B}/usage", headers=h).json()
    vm = {i["resource"]: i for i in usage["items"]}["voice_minutes"]
    assert vm["used"] == 5 and vm["cost"] == "6.00" and usage["total_cost"] == "9.00"
    # metered resource limit (Free Trial: 30 voice minutes)
    with tenant_session(org) as db:
        try:
            svc.enforce_limit(db, org, "voice_minutes", 26)
            raise AssertionError("expected plan limit")
        except AppError as e:
            assert e.code == "plan_limit_reached"
    assert client.put(f"{B}/budget", headers=h, json={"alert_thresholds": [0]}).status_code == 422


def test_upgrade_pay_proration_downgrade(client):
    a = register(client, "Bill Change")
    h = tenant_headers(a)
    r = client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subscription"]["status"] == "active" and body["subscription"]["plan"]["code"] == "starter"
    inv = body["invoice"]
    assert inv["total"] == "49.00" and inv["status"] == "open"
    assert client.post(f"{B}/invoices/{inv['id']}/pay", headers=h, json={"provider": "stripe"}).status_code == 422
    p = client.post(f"{B}/invoices/{inv['id']}/pay", headers=h, json={"provider": "simulated"})
    assert p.status_code == 200 and p.json()["simulated"] is True and p.json()["status"] == "succeeded"
    assert client.post(f"{B}/invoices/{inv['id']}/pay", headers=h, json={}).status_code == 409
    # mid-period upgrade: halfway through -> charge half the difference
    now = utcnow()
    _sub_update(a["org_id"], current_period_start=now - timedelta(days=15), current_period_end=now + timedelta(days=15))
    up = client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "professional"}).json()
    assert up["proration"]["type"] == "prorated"
    assert abs(Decimal(up["invoice"]["total"]) - Decimal("50.00")) <= Decimal("0.05")
    assert {ln["description"] for ln in up["invoice"]["lines"]} == {"Unused time on Starter",
                                                                     "Remaining time on Professional"}
    # downgrade: credit exceeds charge -> zero invoice, credit noted
    down = client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"}).json()
    assert down["invoice"]["total"] == "0.00" and down["invoice"]["status"] == "paid" and down["invoice"]["notes"]
    assert client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"}).status_code == 409
    assert client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "free_trial"}).status_code == 422
    assert client.get(f"{B}/invoices", headers=h).json()["total"] == 3


def test_downgrade_blocked_by_usage(client):
    a = register(client, "Bill Downgrade")
    h = tenant_headers(a)
    assert client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "professional"}).status_code == 200
    for _ in range(3):
        _member(client, a, "Viewer")  # 4 users > Starter's 3
    r = client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "downgrade_blocked"
    assert r.json()["error"]["details"]["users"] == {"used": 4, "limit": 3}


def test_trial_expiry_and_renewal(client):
    a = register(client, "Bill Expiry")
    h = tenant_headers(a)
    client.get(f"{B}/subscription", headers=h)
    _sub_update(a["org_id"], trial_end=utcnow() - timedelta(minutes=1))
    assert client.get(f"{B}/subscription", headers=h).json()["status"] == "past_due"
    r = client.post("/api/v1/workflows", headers=h, json={"name": "x"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "subscription_inactive"
    assert client.post(f"{B}/subscription/change", headers=h, json={"plan_code": "starter"}).status_code == 200
    assert client.post("/api/v1/workflows", headers=h, json={"name": "x"}).status_code == 201
    # period renewal issues an invoice on next read
    now = utcnow()
    _sub_update(a["org_id"], current_period_start=now - timedelta(days=31), current_period_end=now - timedelta(days=1))
    invs = client.get(f"{B}/invoices", headers=h).json()
    assert invs["total"] == 2 and invs["items"][0]["total"] == "49.00"
    assert client.get(f"{B}/subscription", headers=h).json()["status"] == "active"


def test_rbac_and_cross_tenant(client):
    a, b = register(client, "Bill A"), register(client, "Bill B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    inv = client.post(f"{B}/subscription/change", headers=ha, json={"plan_code": "starter"}).json()["invoice"]
    assert client.post(f"{B}/invoices/{inv['id']}/pay", headers=hb, json={}).status_code == 404
    assert client.get(f"{B}/invoices", headers=hb).json()["total"] == 0
    admin = _member(client, a, "Admin")  # Admin lacks billing:manage
    assert client.get(f"{B}/subscription", headers=admin).status_code == 200
    assert client.post(f"{B}/subscription/change", headers=admin, json={"plan_code": "business"}).status_code == 403
    assert client.put(f"{B}/budget", headers=admin, json={}).status_code == 403
    assert client.post(f"{B}/invoices/{inv['id']}/pay", headers=admin, json={}).status_code == 403

