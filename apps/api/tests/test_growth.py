"""insights, copilot, onboarding and demo workspaces."""
from tests.conftest import register, tenant_headers

API = "/api/v1"


def _lead(client, h, name, **kw):
    r = client.post(f"{API}/leads", headers=h, json={"business_name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_insights_empty_org_is_honest(client):
    a = register(client)
    h = tenant_headers(a)
    ov = client.get(f"{API}/insights/overview", headers=h).json()
    assert len(ov["points"]) == 30 and ov["totals"]["leads"] == 0 and ov["revenue"] == []
    pv = client.get(f"{API}/insights/pipeline-value", headers=h).json()
    assert pv["open_value"] == {} and pv["leads_without_budget"] == 0
    fc = client.get(f"{API}/insights/forecast", headers=h).json()
    assert fc["status"] == "insufficient_data" and fc["forecast"] == {} and "formula" in fc
    br = client.get(f"{API}/insights/briefing", headers=h).json()
    assert br["mode"] == "deterministic" and "empty" in br["text"].lower()


def test_insights_counts_real_leads(client):
    a = register(client)
    h = tenant_headers(a)
    _lead(client, h, "Alpha Dental", city="Pune", industry="healthcare")
    _lead(client, h, "Beta Realty", city="Mumbai", industry="real_estate")
    ov = client.get(f"{API}/insights/overview", headers=h).json()
    assert ov["totals"]["leads"] == 2 and ov["points"][-1]["leads"] == 2
    br = client.get(f"{API}/insights/briefing", headers=h).json()
    assert br["facts"]["new_leads_24h"] == 2 and "2 new leads" in br["text"]
    an = client.get(f"{API}/insights/analytics", headers=h).json()
    assert {r["key"] for r in an["by_city"]} == {"Pune", "Mumbai"}
    # tenant isolation
    b = register(client, org="Other Co")
    assert client.get(f"{API}/insights/overview", headers=tenant_headers(b)).json()["totals"]["leads"] == 0


def test_copilot_rules_and_guardrails(client):
    a = register(client)
    h = tenant_headers(a)
    _lead(client, h, "Alpha Dental", city="Pune")
    _lead(client, h, "Gamma Cafe", city="Delhi")
    r = client.post(f"{API}/copilot/ask", headers=h, json={"question": "How many leads in Pune?", "mode": "rules"})
    body = r.json()
    assert r.status_code == 200 and body["tool"] == "count_leads" and body["args"]["city"] == "Pune"
    assert "1 lead" in body["answer"] and body["rows"][0]["label"] == "Alpha Dental" and body["read_only"]
    r = client.post(f"{API}/copilot/ask", headers=h, json={"question": "Delete all my leads", "mode": "rules"})
    assert r.json()["refused"] is True
    r = client.post(f"{API}/copilot/ask", headers=h, json={"question": "What's the weather?", "mode": "rules"})
    assert r.json()["refused"] is True
    r = client.post(f"{API}/copilot/ask", headers=h, json={"question": "What is my pipeline value?"})
    assert r.json()["tool"] == "pipeline_value"
    # still two leads: copilot never writes
    assert client.get(f"{API}/leads", headers=h).json()["total"] == 2


def test_onboarding_progress(client):
    a = register(client)
    h = tenant_headers(a)
    s = client.get(f"{API}/onboarding", headers=h).json()
    assert s["completed"] == 0 and s["total"] == 6
    _lead(client, h, "Alpha Dental")
    s = client.post(f"{API}/onboarding/step", headers=h,
                    json={"step": "profile", "profile": {"industry": "agency", "city": "Pune"}}).json()
    done = {x["key"] for x in s["steps"] if x["done"]}
    assert done == {"profile", "businesses"} and s["profile"]["city"] == "Pune"
    s = client.post(f"{API}/onboarding/step", headers=h, json={"step": "integrations", "action": "skip"}).json()
    assert next(x for x in s["steps"] if x["key"] == "integrations")["skipped"]


def test_demo_workspace_is_separate(client):
    a = register(client)
    h = tenant_headers(a)
    assert client.get(f"{API}/demo", headers=a["headers"]).json()["exists"] is False
    r = client.post(f"{API}/demo", headers=a["headers"])
    assert r.status_code == 201, r.text
    demo_org = r.json()["organization_id"]
    assert client.post(f"{API}/demo", headers=a["headers"]).status_code == 409
    dh = tenant_headers(a, demo_org)
    assert client.get(f"{API}/demo/current", headers=dh).json()["is_demo"] is True
    assert client.get(f"{API}/demo/current", headers=h).json()["is_demo"] is False
    # demo data lives only in the demo org
    assert client.get(f"{API}/leads", headers=dh).json()["total"] == 18
    assert client.get(f"{API}/leads", headers=h).json()["total"] == 0
    fc = client.get(f"{API}/insights/forecast", headers=dh).json()
    assert fc["status"] == "ok" and fc["forecast"].get("INR", 0) > 0
    pv = client.get(f"{API}/insights/pipeline-value", headers=dh).json()
    assert pv["open_value"]["INR"] > 0
    assert client.get(f"{API}/insights/overview", headers=h).json()["totals"]["leads"] == 0
    # reset creates a fresh org; delete removes it from memberships
    r = client.post(f"{API}/demo/reset", headers=a["headers"])
    assert r.status_code == 200 and r.json()["organization_id"] != demo_org
    assert client.delete(f"{API}/demo", headers=a["headers"]).status_code == 204
    me = client.get(f"{API}/auth/me", headers=a["headers"]).json()
    assert len(me["memberships"]) == 1
    assert client.get(f"{API}/demo", headers=a["headers"]).json()["exists"] is False
