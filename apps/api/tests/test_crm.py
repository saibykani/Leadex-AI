import uuid

from tests.conftest import register, tenant_headers

L = "/api/v1/leads"


def _lead(client, h, **kw):
    body = {"business_name": "Sunrise Dental", **kw}
    r = client.post(L, headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _add_member(client, owner, other, role):
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text


def _status(client, h, lead_id, status, **kw):
    return client.post(f"{L}/{lead_id}/status", headers=h, json={"status": status, **kw})


def test_lead_crud_and_activity(client):
    a = register(client, "CRM CRUD")
    h = tenant_headers(a)
    lead = _lead(client, h, email="Info@Sunrise.example", phone="+91 98765 43210", website="https://www.sunrise.example",
                 industry="dental", country="in", city="Pune", custom_fields={"chairs": 4})
    assert lead["status"] == "discovered" and lead["country"] == "IN" and lead["custom_fields"] == {"chairs": 4}
    assert client.get(f"{L}/{lead['id']}", headers=h).json()["business_name"] == "Sunrise Dental"
    r = client.patch(f"{L}/{lead['id']}", headers=h, json={"city": "Mumbai", "score": 70})
    assert r.status_code == 200 and r.json()["city"] == "Mumbai" and r.json()["score"] == 70
    acts = client.get(f"{L}/{lead['id']}/activities", headers=h).json()
    assert {i["type"] for i in acts["items"]} == {"lead.created", "lead.updated"}
    assert client.delete(f"{L}/{lead['id']}", headers=h).status_code == 204
    assert client.get(f"{L}/{lead['id']}", headers=h).status_code == 404
    assert client.get(L, headers=h).json()["total"] == 0
    actions = {i["action"] for i in client.get("/api/v1/audit-logs", headers=h).json()["items"]}
    assert {"lead.create", "lead.update", "lead.delete"} <= actions


def test_list_filters_sort_pagination(client):
    a = register(client, "CRM Filters")
    h = tenant_headers(a)
    me = client.get("/api/v1/auth/me", headers=a["headers"]).json()["user"]["id"]
    x = _lead(client, h, business_name="Alpha Bakery", city="Delhi", owner_user_id=me)
    _lead(client, h, business_name="Beta Gym", city="Goa")
    y = _lead(client, h, business_name="Gamma Bakes")
    assert _status(client, h, y["id"], "verified").status_code == 200
    assert client.get(L, headers=h).json()["total"] == 3
    assert [i["id"] for i in client.get(L, headers=h, params={"status": "verified"}).json()["items"]] == [y["id"]]
    assert {i["id"] for i in client.get(L, headers=h, params={"q": "bak"}).json()["items"]} == {x["id"], y["id"]}
    assert [i["id"] for i in client.get(L, headers=h, params={"owner": me}).json()["items"]] == [x["id"]]
    names = [i["business_name"] for i in client.get(L, headers=h, params={"sort": "business_name"}).json()["items"]]
    assert names == ["Alpha Bakery", "Beta Gym", "Gamma Bakes"]
    p = client.get(L, headers=h, params={"page": 2, "page_size": 2, "sort": "business_name"}).json()
    assert p["total"] == 3 and [i["business_name"] for i in p["items"]] == ["Gamma Bakes"]
    assert client.get(L, headers=h, params={"sort": "password"}).status_code == 422


def test_owner_must_be_member(client):
    a, b = register(client, "Owner A"), register(client, "Owner B")
    b_id = client.get("/api/v1/auth/me", headers=b["headers"]).json()["user"]["id"]
    r = client.post(L, headers=tenant_headers(a), json={"business_name": "X", "owner_user_id": b_id})
    assert r.status_code == 422
    r = client.post(L, headers=tenant_headers(a), json={"business_name": "X", "owner_user_id": str(uuid.uuid4())})
    assert r.status_code == 422


def test_status_lifecycle(client):
    a = register(client, "CRM Lifecycle")
    h = tenant_headers(a)
    lead = _lead(client, h, email="owner@shop.example")
    lid = lead["id"]
    # contact data alone is not consent; skipping verification is invalid too
    assert _status(client, h, lid, "contacted").status_code == 409
    assert _status(client, h, lid, "bogus").status_code == 422
    assert _status(client, h, lid, "verified").status_code == 200
    r = _status(client, h, lid, "approved_for_outreach")
    assert r.status_code == 422 and r.json()["error"]["code"] == "consent_required"
    assert _status(client, h, lid, "approved_for_outreach", consent_reference="  ").status_code == 422
    r = _status(client, h, lid, "approved_for_outreach", consent_reference="form-2026-001")
    assert r.status_code == 200 and r.json()["consent_reference"] == "form-2026-001"
    acts = client.get(f"{L}/{lid}/activities", headers=h).json()["items"]
    change = next(i for i in acts if i["type"] == "status.changed" and i["data"]["to"] == "approved_for_outreach")
    assert change["data"]["consent_reference"] == "form-2026-001"
    for s in ("contacted", "interested", "qualified", "meeting_scheduled", "proposal_sent", "negotiation"):
        assert _status(client, h, lid, s).status_code == 200, s
    assert _status(client, h, lid, "do_not_contact").status_code == 200
    # terminal: no way out without an explicit admin override with a reason
    assert _status(client, h, lid, "contacted").status_code == 409
    assert _status(client, h, lid, "verified", admin_override=True).status_code == 422
    r = _status(client, h, lid, "verified", admin_override=True, reason="Opt-out recorded in error")
    assert r.status_code == 200 and r.json()["status"] == "verified"


def test_admin_override_requires_admin_role(client):
    owner, rep = register(client, "Override Org"), register(client, "Rep Home")
    _add_member(client, owner, rep, "Sales Rep")
    lead = _lead(client, tenant_headers(owner))
    hr = tenant_headers(rep, owner["org_id"])
    assert _status(client, hr, lead["id"], "suppressed").status_code == 200
    r = _status(client, hr, lead["id"], "verified", admin_override=True, reason="please")
    assert r.status_code == 403


def test_duplicate_detection(client):
    a, b = register(client, "Dup A"), register(client, "Dup B")
    h = tenant_headers(a)
    lead = _lead(client, h, email="hello@acme.example", phone="+1 (555) 010-2000", website="acme.example")
    for kw in ({"email": " HELLO@acme.example"}, {"phone": "15550102000"}, {"website": "https://www.ACME.example/about"}):
        r = client.post(L, headers=h, json={"business_name": "Acme 2", **kw})
        assert r.status_code == 409, kw
        assert r.json()["error"]["details"]["existing_lead_id"] == lead["id"]
    other = _lead(client, h, business_name="Other", email="x@other.example")
    r = client.patch(f"{L}/{other['id']}", headers=h, json={"email": "hello@acme.example"})
    assert r.status_code == 409
    # other tenants are unaffected
    _lead(client, tenant_headers(b), email="hello@acme.example")


def test_notes_tasks(client):
    a = register(client, "CRM Notes")
    h = tenant_headers(a)
    lid = _lead(client, h)["id"]
    r = client.post(f"{L}/{lid}/notes", headers=h, json={"body": "Called front desk"})
    assert r.status_code == 201
    assert [n["body"] for n in client.get(f"{L}/{lid}/notes", headers=h).json()] == ["Called front desk"]
    r = client.post(f"{L}/{lid}/tasks", headers=h, json={"title": "Follow up", "due_at": "2000-01-01T00:00:00Z"})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert len(client.get(f"{L}/{lid}/tasks", headers=h).json()) == 1
    s = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s["open_tasks"] == 1 and s["overdue_tasks"] == 1
    r = client.patch(f"{L}/tasks/{tid}", headers=h, json={"completed": True})
    assert r.status_code == 200 and r.json()["completed_at"] is not None
    s = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s["open_tasks"] == 0 and s["overdue_tasks"] == 0
    types = {i["type"] for i in client.get(f"{L}/{lid}/activities", headers=h).json()["items"]}
    assert {"note.added", "task.created", "task.completed"} <= types


def test_cross_tenant_isolation(client):
    a, b = register(client, "Iso A"), register(client, "Iso B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    lid = _lead(client, ha, email="secret@a.example")["id"]
    tid = client.post(f"{L}/{lid}/tasks", headers=ha, json={"title": "t"}).json()["id"]
    client.post(f"{L}/{lid}/notes", headers=ha, json={"body": "n"})
    for path in (f"{L}/{lid}", f"{L}/{lid}/notes", f"{L}/{lid}/tasks", f"{L}/{lid}/activities"):
        assert client.get(path, headers=hb).status_code == 404, path
    assert client.patch(f"{L}/{lid}", headers=hb, json={"city": "x"}).status_code == 404
    assert client.delete(f"{L}/{lid}", headers=hb).status_code == 404
    assert _status(client, hb, lid, "verified").status_code == 404
    assert client.post(f"{L}/{lid}/notes", headers=hb, json={"body": "x"}).status_code == 404
    assert client.patch(f"{L}/tasks/{tid}", headers=hb, json={"completed": True}).status_code == 404
    assert client.get(L, headers=hb).json()["total"] == 0
    assert client.get("/api/v1/dashboard/summary", headers=hb).json()["total_leads"] == 0
    # B cannot pose as A via the header
    assert client.get(L, headers=tenant_headers(b, a["org_id"])).status_code == 404


def test_viewer_cannot_write(client):
    owner, viewer = register(client, "View Org"), register(client, "Viewer Home 2")
    _add_member(client, owner, viewer, "Viewer")
    lid = _lead(client, tenant_headers(owner))["id"]
    hv = tenant_headers(viewer, owner["org_id"])
    assert client.get(L, headers=hv).json()["total"] == 1
    assert client.get("/api/v1/dashboard/summary", headers=hv).status_code == 200
    assert client.post(L, headers=hv, json={"business_name": "Nope"}).status_code == 403
    assert client.patch(f"{L}/{lid}", headers=hv, json={"city": "x"}).status_code == 403
    assert client.delete(f"{L}/{lid}", headers=hv).status_code == 403
    assert _status(client, hv, lid, "verified").status_code == 403
    assert client.post(f"{L}/{lid}/notes", headers=hv, json={"body": "x"}).status_code == 403
    assert client.post(f"{L}/{lid}/tasks", headers=hv, json={"title": "x"}).status_code == 403


def test_dashboard_summary_counts(client):
    a = register(client, "Dash Org")
    h = tenant_headers(a)
    s = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s["total_leads"] == 0 and s["open_tasks"] == 0 and set(s["by_status"].values()) == {0}
    assert "suppressed" in s["by_status"]
    ids = [_lead(client, h, business_name=f"Biz {i}")["id"] for i in range(3)]
    _status(client, h, ids[0], "verified")
    _status(client, h, ids[1], "lost")
    client.delete(f"{L}/{ids[2]}", headers=h)
    s = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s["total_leads"] == 2
    assert s["by_status"]["verified"] == 1 and s["by_status"]["lost"] == 1 and s["by_status"]["discovered"] == 0
