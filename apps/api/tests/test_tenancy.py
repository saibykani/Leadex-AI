import uuid

import pytest

from tests.conftest import IS_PG, register, tenant_headers


def test_cross_tenant_access_denied(client):
    a, b = register(client, "Tenant A"), register(client, "Tenant B")
    # B cannot read A's organization, members, roles or audit logs
    assert client.get(f"/api/v1/organizations/{a['org_id']}", headers=b["headers"]).status_code == 404
    assert client.get(f"/api/v1/organizations/{a['org_id']}/members", headers=b["headers"]).status_code == 404
    assert client.get("/api/v1/audit-logs", headers=tenant_headers(b, a["org_id"])).status_code == 404
    assert client.get("/api/v1/roles", headers=tenant_headers(b, a["org_id"])).status_code == 404
    # B cannot add itself to A
    r = client.post(f"/api/v1/organizations/{a['org_id']}/members", headers=b["headers"],
                    json={"email": b["email"], "role": "Owner"})
    assert r.status_code == 404
    # B's org list does not contain A
    ids = [o["id"] for o in client.get("/api/v1/organizations", headers=b["headers"]).json()]
    assert ids == [b["org_id"]]


def test_audit_logs_scoped_to_tenant(client):
    a, b = register(client, "Audit A"), register(client, "Audit B")
    logs_a = client.get("/api/v1/audit-logs", headers=tenant_headers(a)).json()
    assert logs_a["total"] >= 1
    me_b = client.get("/api/v1/auth/me", headers=b["headers"]).json()["user"]["id"]
    assert me_b not in {i["actor_user_id"] for i in logs_a["items"]}


def test_tenant_header_required(client):
    a = register(client)
    assert client.get("/api/v1/roles", headers=a["headers"]).status_code == 400
    assert client.get("/api/v1/roles", headers=tenant_headers(a, str(uuid.uuid4()))).status_code == 404


def test_rbac_viewer_cannot_manage_members(client):
    owner, viewer = register(client, "RBAC Org"), register(client, "Viewer Home")
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": viewer["email"], "role": "Viewer"})
    assert r.status_code == 201, r.text
    # viewer can read the org but cannot add members or read audit logs
    assert client.get(f"/api/v1/organizations/{owner['org_id']}", headers=viewer["headers"]).status_code == 200
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=viewer["headers"],
                    json={"email": owner["email"], "role": "Admin"})
    assert r.status_code == 403
    assert client.get("/api/v1/audit-logs", headers=tenant_headers(viewer, owner["org_id"])).status_code == 403
    # duplicate membership rejected
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": viewer["email"], "role": "Viewer"})
    assert r.status_code == 409


def test_create_additional_org(client):
    a = register(client)
    r = client.post("/api/v1/organizations", headers=a["headers"], json={"name": "Second Org", "country_code": "gb"})
    assert r.status_code == 201
    assert len(client.get("/api/v1/organizations", headers=a["headers"]).json()) == 2


@pytest.mark.skipif(not IS_PG, reason="Row-level security requires PostgreSQL")
def test_postgres_rls_blocks_unscoped_reads(client):
    from sqlalchemy import text

    from app.core.db import SessionLocal

    a, b = register(client, "RLS A"), register(client, "RLS B")
    with SessionLocal() as db:
        db.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": b["org_id"]})
        rows = db.execute(text("SELECT organization_id FROM organization_memberships")).all()
        assert {str(r[0]) for r in rows} == {b["org_id"]}
        rows = db.execute(text("SELECT organization_id FROM audit_logs")).all()
        assert {str(r[0]) for r in rows} <= {b["org_id"]}
        db.execute(text("SELECT set_config('app.current_org', '', false)"))
        assert db.execute(text("SELECT count(*) FROM organization_memberships")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM leads")).scalar() == 0
        db.rollback()

    # A fresh pooled connection must start unscoped (no leaked tenant/user from earlier requests).
    with SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM organization_memberships")).scalar() == 0
        assert a["org_id"]


@pytest.mark.skipif(not IS_PG, reason="Grants are PostgreSQL-specific")
def test_postgres_app_role_cannot_bypass_rls_or_rewrite_audit(client):
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from app.core.db import SessionLocal

    a = register(client, "Audit Immutability")
    with SessionLocal() as db:
        row = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert row == (False, False)
        db.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": a["org_id"]})
        for stmt in ("UPDATE audit_logs SET action = 'tampered'", "DELETE FROM audit_logs",
                     "DELETE FROM lead_activities"):
            with pytest.raises(ProgrammingError):
                db.execute(text(stmt))
            db.rollback()
            db.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": a["org_id"]})
