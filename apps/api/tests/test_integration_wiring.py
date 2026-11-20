"""Cross-module wiring: plan limits / metering, automation events, dedicated encryption key."""
import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.db import tenant_session
from app.modules.billing.models import BillingUsage
from app.modules.compliance import crypto
from tests.conftest import register, tenant_headers

W = "/api/v1/workflows"


def _trigger_wf(client, h, trigger):
    graph = {"nodes": [{"id": "t", "type": "trigger", "config": {"trigger_type": trigger}},
                       {"id": "x", "type": "notification", "config": {}}],
             "edges": [{"source": "t", "target": "x"}]}
    wf = client.post(W, headers=h, json={"name": f"On {trigger}", "graph": graph}).json()
    assert client.post(f"{W}/{wf['id']}/versions", headers=h).status_code == 201
    return wf


def test_lead_created_event_starts_workflow(client):
    h = tenant_headers(register(client, "Wire Lead Event"))
    wf = _trigger_wf(client, h, "lead_created")
    r = client.post("/api/v1/leads", headers=h, json={"business_name": "Evented Bakery"})
    assert r.status_code == 201, r.text
    exs = client.get(f"{W}/{wf['id']}/executions", headers=h).json()
    assert exs["total"] == 1 and exs["items"][0]["trigger_type"] == "lead_created"


def test_lead_creation_survives_without_listeners_and_on_dispatch_error(client, monkeypatch):
    h = tenant_headers(register(client, "Wire No Listener"))
    assert client.post("/api/v1/leads", headers=h, json={"business_name": "Quiet Co"}).status_code == 201
    from app.modules.automation import engine

    def boom(*a, **k):
        raise RuntimeError("engine down")

    monkeypatch.setattr(engine, "dispatch_event", boom)
    assert client.post("/api/v1/leads", headers=h, json={"business_name": "Still Works"}).status_code == 201


def test_business_discovered_event(client):
    h = tenant_headers(register(client, "Wire Discovery Event"))
    wf = _trigger_wf(client, h, "business_discovered")
    r = client.post("/api/v1/discovery/search", headers=h,
                    json={"criteria": {"source": "simulated", "city": "Goa", "industry": "cafe", "limit": 2}})
    assert r.status_code == 201, r.text
    assert client.get(f"{W}/{wf['id']}/executions", headers=h).json()["total"] == 2
    a_org = uuid.UUID(h["X-Organization-Id"])
    with tenant_session(a_org) as db:
        rows = db.scalars(select(BillingUsage).where(BillingUsage.organization_id == a_org,
                                                     BillingUsage.resource == "searches")).all()
        assert len(rows) == 1 and float(rows[0].cost) == 0


@pytest.mark.plan_limits
def test_free_trial_limits_return_402(client):
    owner = register(client, "Wire Limits")
    h = tenant_headers(owner)
    # Free Trial allows 2 users: owner + 1
    for i, role in enumerate(("Sales Rep", "Viewer")):
        other = register(client, f"Wire Other {i}")
        r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                        json={"email": other["email"], "role": role})
        assert r.status_code == (201 if i == 0 else 402), r.text
    assert r.json()["error"]["code"] == "plan_limit_reached"
    # Free Trial allows 1 website generation per month
    lead = client.post("/api/v1/leads", headers=h, json={"business_name": "Site Co", "city": "Pune"}).json()
    tpl = client.get("/api/v1/websites/templates", headers=h).json()[0]["key"]
    body = {"lead_id": lead["id"], "template_key": tpl}
    assert client.post("/api/v1/websites/generate", headers=h, json=body).status_code == 201
    r = client.post("/api/v1/websites/generate", headers=h, json=body)
    assert r.status_code == 402 and r.json()["error"]["details"]["resource"] == "websites"


def test_encryption_key_and_legacy_fallback(monkeypatch):
    legacy_token = crypto._fernet(get_settings().jwt_secret).encrypt(b"old-secret").decode()
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    try:
        tok = crypto.encrypt("new-secret")
        assert Fernet(key.encode()).decrypt(tok.encode()) == b"new-secret"  # written with the dedicated key
        assert crypto.decrypt(tok) == "new-secret"
        assert crypto.decrypt(legacy_token) == "old-secret"  # old data still readable
    finally:
        monkeypatch.delenv("ENCRYPTION_KEY")
        get_settings.cache_clear()


def test_production_requires_encryption_key():
    base = {"app_env": "production", "jwt_secret": "p" * 40, "app_db_password": "strong-db-pass"}
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        Settings(**base, encryption_key=None).validate_for_runtime()
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        Settings(**base, encryption_key="not-a-key").validate_for_runtime()
    Settings(**base, encryption_key=Fernet.generate_key().decode()).validate_for_runtime()
