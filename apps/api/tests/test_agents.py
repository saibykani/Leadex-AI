import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.modules.agents import config as ai_config
from app.modules.compliance import checks as compliance_checks
from tests.conftest import register, tenant_headers

A = "/api/v1/agents"
C = "/api/v1/calls"
DISCLOSURE = "This is an automated AI assistant calling on behalf of Acme."


@pytest.fixture(autouse=True)
def _no_ai_env(monkeypatch):
    """Tests never hit a real network: AI services unconfigured unless a test opts in with a MockTransport."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.setenv("VOICE_KILL_SWITCH", "false")
    monkeypatch.setattr(ai_config, "http_transport", None)
    # 06:30 UTC = 12:00 IST: inside India's calling window (owned by the compliance module).
    monkeypatch.setattr(compliance_checks, "now", lambda: datetime(2026, 11, 4, 6, 30, tzinfo=UTC))


def _mock(monkeypatch, handler, ollama=True, qdrant=False):
    if ollama:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    if qdrant:
        monkeypatch.setenv("QDRANT_URL", "http://qdrant.test")
    monkeypatch.setattr(ai_config, "http_transport", httpx.MockTransport(handler))


def _agent(client, h, **kw):
    body = {"name": "Sales Bot", "compliance_disclosure": DISCLOSURE, "greeting": "Hello there!",
            "tools": ["crm_lookup"], **kw}
    r = client.post(A, headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _approved_lead(client, h, **kw):
    r = client.post("/api/v1/leads", headers=h, json={"business_name": "Dental Co", "country": "IN",
                                                      "email": f"{uuid.uuid4().hex[:6]}@d.example", **kw})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert client.post(f"/api/v1/leads/{lid}/status", headers=h, json={"status": "verified"}).status_code == 200
    r = client.post(f"/api/v1/leads/{lid}/status", headers=h,
                    json={"status": "approved_for_outreach", "consent_reference": "form-123"})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/compliance/consents", headers=h, json={
        "lead_id": lid, "channel": "voice", "basis": "express_consent", "evidence_text": "Web form"})
    assert r.status_code == 201, r.text
    return lid


def _call(client, h, lead_id, agent_id, key=None):
    return client.post(C, headers={**h, "Idempotency-Key": key or uuid.uuid4().hex},
                       json={"lead_id": lead_id, "agent_id": agent_id})


def _add_member(client, owner, other, role):
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------- agents CRUD / templates / versions
def test_templates_and_from_template(client):
    h = tenant_headers(register(client, "Agents Tpl"))
    items = client.get(f"{A}/templates", headers=h).json()["items"]
    assert len(items) == 10  # 9 originals + website_sales_budget_discovery (pipeline)
    assert {"business_website_sales", "general_business_development"} <= {t["key"] for t in items}
    r = client.post(f"{A}/from-template", headers=h, json={"template_key": "real_estate_qualification",
                                                           "business_name": "Acme Homes"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["template_key"] == "real_estate_qualification" and "Acme Homes" in a["compliance_disclosure"]
    assert a["status"] == "draft"
    assert client.post(f"{A}/from-template", headers=h, json={"template_key": "nope"}).status_code == 404


def test_crud_publish_versions(client):
    h = tenant_headers(register(client, "Agents CRUD"))
    assert client.post(A, headers=h, json={"name": "x", "compliance_disclosure": "short"}).status_code == 422
    assert client.post(A, headers=h, json={"name": "x", "compliance_disclosure": DISCLOSURE,
                                           "tools": ["launch_missiles"]}).status_code == 422
    assert client.post(A, headers=h, json={"name": "x", "compliance_disclosure": DISCLOSURE,
                                           "language": "fr"}).status_code == 422
    a = _agent(client, h)
    v1 = client.post(f"{A}/{a['id']}/publish", headers=h)
    assert v1.status_code == 201 and v1.json()["version"] == 1
    assert v1.json()["snapshot"]["greeting"] == "Hello there!"
    r = client.patch(f"{A}/{a['id']}", headers=h, json={"greeting": "Hi again"})
    assert r.status_code == 200 and r.json()["status"] == "draft"  # edits require re-publish
    assert client.post(f"{A}/{a['id']}/publish", headers=h).json()["version"] == 2
    vs = client.get(f"{A}/{a['id']}/versions", headers=h).json()
    assert [v["version"] for v in vs] == [2, 1] and vs[1]["snapshot"]["greeting"] == "Hello there!"
    assert client.get(A, headers=h).json()["total"] == 1
    assert client.delete(f"{A}/{a['id']}", headers=h).status_code == 204
    assert client.get(f"{A}/{a['id']}", headers=h).status_code == 404


def test_cross_tenant_404(client):
    a, b = register(client, "Agents T1"), register(client, "Agents T2")
    ha, hb = tenant_headers(a), tenant_headers(b)
    ag = _agent(client, ha)
    lead = _approved_lead(client, ha)
    for method, path in [("get", f"{A}/{ag['id']}"), ("patch", f"{A}/{ag['id']}"), ("delete", f"{A}/{ag['id']}"),
                         ("post", f"{A}/{ag['id']}/publish"), ("get", f"{A}/{ag['id']}/knowledge"),
                         ("get", f"{A}/{ag['id']}/versions")]:
        kw = {"json": {"name": "x"}} if method == "patch" else {}
        assert getattr(client, method)(path, headers=hb, **kw).status_code == 404, path
    r = client.post(f"{A}/{ag['id']}/test", headers=hb, json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 404
    assert client.get(A, headers=hb).json()["total"] == 0
    # B cannot call A's lead with B's agent, nor use A's agent
    bg = _agent(client, hb)
    assert _call(client, hb, lead, bg["id"]).status_code == 404
    lead_b = _approved_lead(client, hb)
    assert _call(client, hb, lead_b, ag["id"]).status_code == 404
    call = _call(client, ha, lead, ag["id"]).json()
    call_id = call.get("id") or call["error"]["details"]["call_id"]
    assert client.get(f"{C}/{call_id}", headers=hb).status_code == 404
    assert client.get(C, headers=hb).json()["total"] == 0


def test_rbac(client):
    owner, rep, viewer = register(client, "Agents RBAC"), register(client, "Rep home"), register(client, "Viewer h")
    _add_member(client, owner, rep, "Sales Rep")
    _add_member(client, owner, viewer, "Viewer")
    ho = tenant_headers(owner)
    ag = _agent(client, ho)
    lead = _approved_lead(client, ho)
    hr, hv = tenant_headers(rep, owner["org_id"]), tenant_headers(viewer, owner["org_id"])
    assert client.get(A, headers=hr).status_code == 200  # agents:read
    assert client.post(A, headers=hr, json={"name": "x", "compliance_disclosure": DISCLOSURE}).status_code == 403
    assert client.post(f"{A}/{ag['id']}/publish", headers=hv).status_code == 403
    assert client.post(f"{A}/{ag['id']}/test", headers=hv,
                       json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 403
    assert _call(client, hr, lead, ag["id"]).status_code == 403  # calls:initiate
    assert _call(client, hv, lead, ag["id"]).status_code == 403


# ---------------------------------------------------------------- test lab
def test_simulated_test_run_with_knowledge_and_tools(client):
    h = tenant_headers(register(client, "Agents Sim"))
    ag = _agent(client, h, tools=["crm_lookup", "create_note"])
    lead = _approved_lead(client, h)
    r = client.post(f"{A}/{ag['id']}/knowledge", headers=h, json={
        "title": "Pricing", "content": "Our starter website plan costs 9999 rupees per year including hosting."})
    assert r.status_code == 201 and r.json()["embedding_status"] == "keyword_only" and r.json()["chunk_count"] == 1
    client.post(f"{A}/{ag['id']}/knowledge", headers=h, json={"title": "Hours", "content": "Open Monday to Friday."})
    body = {"messages": [{"role": "user", "content": "How much does the website plan cost?"}],
            "invoke_tools": [{"name": "crm_lookup", "arguments": {"lead_id": lead}},
                             {"name": "book_callback", "arguments": {"lead_id": lead}},
                             {"name": "create_note", "arguments": {"lead_id": lead, "body": "Asked about price"}}]}
    r = client.post(f"{A}/{ag['id']}/test", headers=h, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["simulated"] is True and out["provider"] == "simulated" and out["status"] == "ok"
    assert "(Simulated template reply" in out["reply"]
    assert out["retrieval_mode"] == "keyword" and out["citations"][0]["title"] == "Pricing"
    tc = {t["name"]: t for t in out["tool_calls"]}
    assert tc["crm_lookup"]["ok"] and tc["crm_lookup"]["result"]["business_name"] == "Dental Co"
    assert tc["book_callback"]["error"] == "tool_not_allowed"  # not in allow-list
    assert tc["create_note"]["result"]["dry_run"] is True
    assert client.get(f"/api/v1/leads/{lead}/notes", headers=h).json() == []  # dry run wrote nothing
    # deterministic
    again = client.post(f"{A}/{ag['id']}/test", headers=h, json=body).json()
    assert again["reply"] == out["reply"]
    runs = client.get(f"{A}/{ag['id']}/runs", headers=h).json()
    assert runs["total"] == 2 and runs["items"][0]["simulated"] is True
    # tool cannot reach another tenant's lead
    other = tenant_headers(register(client, "Agents Sim Other"))
    foreign = _approved_lead(client, other)
    r = client.post(f"{A}/{ag['id']}/test", headers=h, json={
        "messages": [{"role": "user", "content": "x"}],
        "invoke_tools": [{"name": "crm_lookup", "arguments": {"lead_id": foreign}}]}).json()
    assert r["tool_calls"][0]["error"] == "not_found"
    # knowledge delete
    kid = client.get(f"{A}/{ag['id']}/knowledge", headers=h).json()[0]["id"]
    assert client.delete(f"{A}/{ag['id']}/knowledge/{kid}", headers=h).status_code == 204
    assert len(client.get(f"{A}/{ag['id']}/knowledge", headers=h).json()) == 1


def test_ollama_not_configured_is_reported_not_faked(client):
    h = tenant_headers(register(client, "Agents NoLLM"))
    ag = _agent(client, h)
    r = client.post(f"{A}/{ag['id']}/test", headers=h,
                    json={"provider": "ollama", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "not_configured" and out["reply"] == "" and out["simulated"] is False
    assert "OLLAMA_BASE_URL" in out["error"]
    prov = {p["provider"]: p for p in client.get("/api/v1/ai/providers", headers=h).json()["providers"]}
    assert prov["ollama"]["status"] == "not_configured" and prov["qdrant"]["status"] == "not_configured"
    assert prov["simulated"]["simulated"] is True


def test_ollama_unreachable(client, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    _mock(monkeypatch, handler)
    h = tenant_headers(register(client, "Agents Down"))
    ag = _agent(client, h)
    out = client.post(f"{A}/{ag['id']}/test", headers=h,
                      json={"provider": "ollama", "messages": [{"role": "user", "content": "hi"}]}).json()
    assert out["status"] == "error" and out["reply"] == "" and "unreachable" in out["error"]
    prov = {p["provider"]: p for p in client.get("/api/v1/ai/providers", headers=h).json()["providers"]}
    assert prov["ollama"]["status"] == "unreachable"


def test_ollama_chat_tool_call_and_vector_rag(client, monkeypatch):
    seen = {"chat": 0, "search_filter": None}

    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/api/embeddings":
            return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
        if path == "/api/chat":
            seen["chat"] += 1
            body = json.loads(request.content)
            assert body["stream"] is False and "Pricing" in body["messages"][0]["content"]
            if seen["chat"] == 1:
                assert {t["function"]["name"] for t in body["tools"]} == {"crm_lookup"}
                return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [
                    {"function": {"name": "crm_lookup", "arguments": {"lead_id": seen["lead"]}}},
                    {"function": {"name": "create_note", "arguments": {"lead_id": seen["lead"], "body": "x"}}}]}})
            assert body["messages"][-1]["role"] == "tool"
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "It costs 9999 [1]."}})
        if path.startswith("/collections/") and request.method == "GET":
            return httpx.Response(404, json={})
        if path.endswith("/points/search"):
            seen["search_filter"] = json.loads(request.content)["filter"]
            return httpx.Response(200, json={"result": [{"id": seen["chunk"], "score": 0.9}]})
        if path.startswith("/collections/"):
            if path.endswith("/points"):
                seen["chunk"] = json.loads(request.content)["points"][0]["id"]
            return httpx.Response(200, json={"result": True})
        return httpx.Response(404)

    _mock(monkeypatch, handler, qdrant=True)
    h = tenant_headers(register(client, "Agents Ollama"))
    seen["lead"] = _approved_lead(client, h)
    ag = _agent(client, h)
    mc = client.post("/api/v1/ai/model-configs", headers=h,
                     json={"name": "local", "provider": "ollama", "model": "llama3.1:8b"}).json()
    client.patch(f"{A}/{ag['id']}", headers=h, json={"model_config_id": mc["id"]})
    k = client.post(f"{A}/{ag['id']}/knowledge", headers=h, json={"title": "Pricing", "content": "Plan is 9999."})
    assert k.json()["embedding_status"] == "embedded"
    out = client.post(f"{A}/{ag['id']}/test", headers=h,
                      json={"messages": [{"role": "user", "content": "price?"}]}).json()
    assert out["status"] == "ok" and out["simulated"] is False and out["reply"] == "It costs 9999 [1]."
    assert out["retrieval_mode"] == "vector" and out["citations"][0]["title"] == "Pricing"
    keys = {c["key"] for c in seen["search_filter"]["must"]}
    assert keys == {"org_id", "agent_id"}
    tc = {t["name"]: t for t in out["tool_calls"]}
    assert tc["crm_lookup"]["ok"] and tc["create_note"]["error"] == "tool_not_allowed"


# ---------------------------------------------------------------- calls
def test_call_requires_idempotency_key(client):
    h = tenant_headers(register(client, "Calls Idem"))
    ag = _agent(client, h)
    lead = _approved_lead(client, h)
    r = client.post(C, headers=h, json={"lead_id": lead, "agent_id": ag["id"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "idempotency_key_required"


def test_gate_blocks_unapproved_lead_and_unpublished_agent(client):
    h = tenant_headers(register(client, "Calls Block"))
    ag = _agent(client, h)
    lead = client.post("/api/v1/leads", headers=h, json={"business_name": "Raw Lead"}).json()["id"]
    r = _call(client, h, lead, ag["id"], key="k1")
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "call_blocked"
    reasons = err["details"]["reasons"]
    assert "agent_not_published" in reasons and "lead_status_not_eligible:discovered" in reasons
    assert "no_consent_reference" in reasons and "jurisdiction_unknown" in reasons
    detail = client.get(f"{C}/{err['details']['call_id']}", headers=h).json()
    assert detail["status"] == "blocked" and detail["transcript"] == []
    assert {e["type"] for e in detail["events"]} == {"call.requested", "call.blocked"}
    # replay returns the same stored response, without a second session
    again = _call(client, h, lead, ag["id"], key="k1")
    assert again.status_code == 422 and again.json() == r.json() and again.headers["Idempotent-Replay"] == "true"
    assert client.get(C, headers=h).json()["total"] == 1
    # same key, different body -> 409
    ag2 = _agent(client, h)
    assert _call(client, h, lead, ag2["id"], key="k1").status_code == 409


def test_allowed_call_is_simulated_and_kill_switches(client, monkeypatch):
    h = tenant_headers(register(client, "Calls Sim"))
    ag = _agent(client, h)
    lead = _approved_lead(client, h)
    assert client.post(f"{A}/{ag['id']}/publish", headers=h).status_code == 201
    r = _call(client, h, lead, ag["id"])
    assert r.status_code == 201, r.text
    call = r.json()
    assert call["status"] == "simulated_completed" and call["simulated"] is True and call["gate_reasons"] == []
    d = client.get(f"{C}/{call['id']}", headers=h).json()
    assert len(d["transcript"]) == 1 and d["transcript"][0]["speaker"] == "system"
    assert d["transcript"][0]["text"].startswith("[SIMULATION]") and d["transcript"][0]["simulated"] is True
    assert d["recording"]["enabled"] is False and d["summary"]["simulated"] is True
    # global kill switch
    monkeypatch.setenv("VOICE_KILL_SWITCH", "true")
    r = _call(client, h, lead, ag["id"])
    assert r.status_code == 422 and r.json()["error"]["details"]["reasons"] == ["global_kill_switch"]
    monkeypatch.setenv("VOICE_KILL_SWITCH", "false")
    # per-agent kill
    assert client.post(f"{A}/{ag['id']}/kill", headers=h).json()["status"] == "killed"
    r = _call(client, h, lead, ag["id"])
    assert r.status_code == 422 and "agent_killed" in r.json()["error"]["details"]["reasons"]
    assert client.post(f"{A}/{ag['id']}/test", headers=h,
                       json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 409
    assert client.post(f"{A}/{ag['id']}/publish", headers=h).status_code == 409
    assert client.post(f"{A}/{ag['id']}/reactivate", headers=h).json()["status"] == "draft"
    statuses = [c["status"] for c in client.get(C, headers=h).json()["items"]]
    assert sorted(statuses) == ["blocked", "blocked", "simulated_completed"]


def test_language_evaluation_gate(client):
    owner, mgr = register(client, "Calls Lang"), register(client, "Mgr home")
    _add_member(client, owner, mgr, "Manager")
    h = tenant_headers(owner)
    ag = _agent(client, h, language="hi")
    lead = _approved_lead(client, h)
    client.post(f"{A}/{ag['id']}/publish", headers=h)
    r = _call(client, h, lead, ag["id"])
    assert r.status_code == 422 and r.json()["error"]["details"]["reasons"] == ["language_evaluation_pending:hi"]
    hm = tenant_headers(mgr, owner["org_id"])
    assert client.post(f"{A}/{ag['id']}/evaluations", headers=hm,
                       json={"language": "hi", "passed": True}).status_code == 403
    client.post(f"{A}/{ag['id']}/evaluations", headers=h, json={"language": "hi", "passed": False, "score": 40})
    assert _call(client, h, lead, ag["id"]).status_code == 422
    client.post(f"{A}/{ag['id']}/evaluations", headers=h, json={"language": "hi", "passed": True, "score": 92})
    assert _call(client, h, lead, ag["id"]).status_code == 201
    langs = {x["code"]: x["status"] for x in client.get(f"{A}/languages", headers=h).json()["items"]}
    assert langs["en"] == "enabled" and all(v == "evaluation_pending" for k, v in langs.items() if k != "en")
    assert {"hi", "te", "ta", "kn", "ml", "mr", "bn", "gu"} <= set(langs)
