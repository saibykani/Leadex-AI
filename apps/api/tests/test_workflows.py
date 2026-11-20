import uuid

import httpx
import pytest

from app.core.db import tenant_session
from app.modules.automation import engine
from tests.conftest import register, tenant_headers

W = "/api/v1/workflows"


def _n(id_, type_, **config):
    return {"id": id_, "type": type_, "config": config}


def _e(s, t, label=None):
    return {"source": s, "target": t, **({"label": label} if label else {})}


def _graph(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def _wf(client, h, graph, name="Flow"):
    r = client.post(W, headers=h, json={"name": name, "graph": graph})
    assert r.status_code == 201, r.text
    wf = r.json()
    r = client.post(f"{W}/{wf['id']}/versions", headers=h)
    assert r.status_code == 201, r.text
    return wf


def _run(client, h, wf_id, payload=None, key=None):
    hdr = {**h, **({"Idempotency-Key": key} if key else {})}
    r = client.post(f"{W}/{wf_id}/execute", headers=hdr, json={"payload": payload or {}})
    assert r.status_code in (200, 201), r.text
    return r


def _events(client, h, ex_id):
    return client.get(f"{W}/executions/{ex_id}/events", headers=h).json()


def _by_node(events):
    out = {}
    for e in events:
        out.setdefault(e["node_key"], []).append(e["event"])
    return out


def _lead(client, h, **kw):
    r = client.post("/api/v1/leads", headers=h, json={"business_name": "Hook Bakery", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_dag_validation(client):
    a = register(client, "WF Validate")
    h = tenant_headers(a)
    ok = _graph([_n("t", "trigger"), _n("x", "notification")], [_e("t", "x")])
    assert client.post(f"{W}/validate", headers=h, json=ok).json() == {"valid": True, "errors": []}
    cyc = _graph([_n("t", "trigger"), _n("a", "notification"), _n("b", "notification")],
                 [_e("t", "a"), _e("a", "b"), _e("b", "a")])
    res = client.post(f"{W}/validate", headers=h, json=cyc).json()
    assert not res["valid"] and "graph contains a cycle" in res["errors"]
    for bad in (
        _graph([_n("a", "notification")], []),  # no trigger
        _graph([_n("t", "trigger"), _n("t2", "trigger")], []),  # two triggers
        _graph([_n("t", "trigger"), _n("x", "teleport")], [_e("t", "x")]),  # unknown type
        _graph([_n("t", "trigger"), _n("x", "notification")], []),  # unreachable
        _graph([_n("t", "trigger"), _n("x", "notification", retries=99)], [_e("t", "x")]),
    ):
        assert not client.post(f"{W}/validate", headers=h, json=bad).json()["valid"]
    wf = client.post(W, headers=h, json={"name": "Cyclic", "graph": cyc}).json()
    r = client.post(f"{W}/{wf['id']}/versions", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_graph"
    # unpublished workflows cannot run
    assert client.post(f"{W}/{wf['id']}/execute", headers=h, json={}).status_code == 409


def test_branching_and_versions(client):
    a = register(client, "WF Branch")
    h = tenant_headers(a)
    g = _graph([_n("t", "trigger"), _n("c", "condition", field="payload.score", op="gte", value=50),
                _n("hot", "notification", message="hot"), _n("cold", "notification", message="cold"),
                _n("f", "filter", field="payload.city", op="eq", value="Pune"), _n("after", "notification")],
               [_e("t", "c"), _e("c", "hot", "true"), _e("c", "cold", "false"), _e("hot", "f"), _e("f", "after")])
    wf = _wf(client, h, g)
    ex = _run(client, h, wf["id"], {"score": 80, "city": "Goa"}).json()
    assert ex["status"] == "succeeded"
    ev = _by_node(_events(client, h, ex["id"]))
    assert ev["hot"][-1] == "succeeded" and ev["cold"] == ["skipped"]
    assert ev["f"][-1] == "succeeded" and ev["after"] == ["skipped"]  # filter halted
    ex2 = _run(client, h, wf["id"], {"score": 10}).json()
    ev2 = _by_node(_events(client, h, ex2["id"]))
    assert ev2["cold"][-1] == "succeeded" and ev2["hot"] == ["skipped"]
    # publish v2 -> versions are immutable and numbered
    assert client.post(f"{W}/{wf['id']}/versions", headers=h).status_code == 201
    vs = client.get(f"{W}/{wf['id']}/versions", headers=h).json()
    assert [v["version"] for v in vs] == [2, 1]
    an = client.get(f"{W}/{wf['id']}/analytics", headers=h).json()
    assert an["total"] == 2 and an["by_status"] == {"succeeded": 2} and an["success_rate"] == 1.0


def test_idempotent_execution(client):
    a = register(client, "WF Idem")
    h = tenant_headers(a)
    wf = _wf(client, h, _graph([_n("t", "trigger"), _n("x", "notification")], [_e("t", "x")]))
    r1 = _run(client, h, wf["id"], key="abc-1")
    r2 = _run(client, h, wf["id"], key="abc-1")
    assert r1.status_code == 201 and r2.status_code == 200 and r1.json()["id"] == r2.json()["id"]
    assert len(_events(client, h, r1.json()["id"])) == 4  # started/succeeded x2 -- not re-run
    assert _run(client, h, wf["id"], key="abc-2").json()["id"] != r1.json()["id"]
    assert client.get(f"{W}/{wf['id']}/executions", headers=h).json()["total"] == 2


@pytest.fixture
def fake_http(monkeypatch):
    calls = {"n": 0, "script": []}

    def handler(request):
        calls["n"] += 1
        step = calls["script"].pop(0) if calls["script"] else 200
        if step == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(step, json={"ok": step == 200})

    monkeypatch.setattr(engine, "_http_client",
                        lambda timeout: httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout))
    monkeypatch.setattr(engine, "_resolve", lambda host: ["10.0.0.5"] if host == "internal.example" else
                        ["93.184.216.34"])
    return calls


def test_api_request_retries_timeouts_and_ssrf(client, fake_http):
    a = register(client, "WF Http")
    h = tenant_headers(a)
    assert client.put(f"{W}/settings", headers=h,
                      json={"allowed_hosts": ["api.example.com", "internal.example"]}).status_code == 200
    g = _graph([_n("t", "trigger"), _n("r", "api_request", url="https://api.example.com/x", retries=2,
                                       timeout_seconds=5)], [_e("t", "r")])
    wf = _wf(client, h, g)
    fake_http["script"] = [500, 503, 200]
    ex = _run(client, h, wf["id"]).json()
    assert ex["status"] == "succeeded" and fake_http["n"] == 3
    ev = [e for e in _events(client, h, ex["id"]) if e["node_key"] == "r"]
    assert [e["event"] for e in ev] == ["started", "retried", "started", "retried", "started", "succeeded"]
    assert ev[-1]["attempt"] == 3
    # timeouts are retried, then fail the execution
    fake_http["script"] = ["timeout", "timeout", "timeout"]
    ex = _run(client, h, wf["id"]).json()
    assert ex["status"] == "failed" and "timeout" in ex["error"]
    # host not on allow-list -> non-retryable failure, no request made
    n = fake_http["n"]
    wf2 = _wf(client, h, _graph([_n("t", "trigger"), _n("r", "webhook_out", url="https://evil.example/x", retries=3)],
                                [_e("t", "r")]))
    ex = _run(client, h, wf2["id"]).json()
    assert ex["status"] == "failed" and "allow-list" in ex["error"] and fake_http["n"] == n
    # allow-listed host that resolves to a private IP is blocked (SSRF)
    wf3 = _wf(client, h, _graph([_n("t", "trigger"), _n("r", "api_request", url="http://internal.example/")],
                                [_e("t", "r")]))
    ex = _run(client, h, wf3["id"]).json()
    assert ex["status"] == "failed" and "SSRF" in ex["error"] and fake_http["n"] == n
    assert client.put(f"{W}/settings", headers=h, json={"allowed_hosts": ["http://x/y"]}).status_code == 422


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "192.168.0.1", "100.64.0.1"])
def test_ssrf_guard_blocks_private_ranges(monkeypatch, ip):
    monkeypatch.setattr(engine, "allowed_hosts", lambda db, org: ["h.example"])
    monkeypatch.setattr(engine, "_resolve", lambda host: [ip])
    with pytest.raises(engine.NodeError, match="SSRF"):
        engine.guard_url(None, uuid.uuid4(), "https://h.example/")
    with pytest.raises(engine.NodeError, match="http"):
        engine.guard_url(None, uuid.uuid4(), "file:///etc/passwd")


def test_approval_pauses_until_approved(client):
    a = register(client, "WF Approval")
    h = tenant_headers(a)
    g = _graph([_n("t", "trigger"), _n("ap", "approval", message="ok?"), _n("yes", "notification"),
                _n("no", "notification")], [_e("t", "ap"), _e("ap", "yes", "approved"), _e("ap", "no", "rejected")])
    wf = _wf(client, h, g)
    ex = _run(client, h, wf["id"]).json()
    assert ex["status"] == "waiting"
    assert "yes" not in _by_node(_events(client, h, ex["id"]))
    aps = client.get(f"{W}/approvals", headers=h).json()
    assert len(aps) == 1 and aps[0]["execution_id"] == ex["id"]
    r = client.post(f"{W}/approvals/{aps[0]['id']}/approve", headers=h, json={"comment": "go"})
    assert r.status_code == 200 and r.json()["status"] == "succeeded"
    ev = _by_node(_events(client, h, ex["id"]))
    assert ev["ap"] == ["started", "waiting_approval", "succeeded"] and ev["yes"][-1] == "succeeded"
    assert ev["no"] == ["skipped"]
    assert client.post(f"{W}/approvals/{aps[0]['id']}/approve", headers=h).status_code == 409
    # rejection follows the 'rejected' branch only
    ex2 = _run(client, h, wf["id"]).json()
    ap2 = client.get(f"{W}/approvals", headers=h).json()[0]
    assert client.post(f"{W}/approvals/{ap2['id']}/reject", headers=h).json()["status"] == "succeeded"
    ev2 = _by_node(_events(client, h, ex2["id"]))
    assert ev2["no"][-1] == "succeeded" and ev2["yes"] == ["skipped"]


def test_delay_and_resume(client):
    a = register(client, "WF Delay")
    h = tenant_headers(a)
    wf = _wf(client, h, _graph([_n("t", "trigger"), _n("d", "delay", seconds=0), _n("x", "notification")],
                               [_e("t", "d"), _e("d", "x")]))
    ex = _run(client, h, wf["id"]).json()
    assert ex["status"] == "waiting" and ex["resume_at"]
    r = client.post(f"{W}/executions/{ex['id']}/resume", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "succeeded"
    assert client.post(f"{W}/executions/{ex['id']}/resume", headers=h).status_code == 409
    wf2 = _wf(client, h, _graph([_n("t", "trigger"), _n("d", "delay", seconds=3600), _n("x", "notification")],
                                [_e("t", "d"), _e("d", "x")]))
    ex2 = _run(client, h, wf2["id"]).json()
    r = client.post(f"{W}/executions/{ex2['id']}/resume", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_due"
    assert client.post(f"{W}/executions/resume-due", headers=h).json() == []


def test_communication_nodes_go_through_gate(client):
    a = register(client, "WF Gate")
    h = tenant_headers(a)
    lead = _lead(client, h, email="x@hook.example")
    g = _graph([_n("t", "trigger"), _n("em", "email", template="intro"), _n("wa", "whatsapp"),
                _n("vc", "voice_call"), _n("cu", "crm_update", score=77), _n("la", "lead_assignment"),
                _n("ai", "ai_action", prompt="summarize")],
               [_e("t", "em"), _e("em", "wa"), _e("wa", "vc"), _e("vc", "cu"), _e("cu", "la"), _e("la", "ai")])
    wf = _wf(client, h, g)
    ex = _run(client, h, wf["id"], {"lead_id": lead["id"]}).json()
    assert ex["status"] == "succeeded", ex
    ev = {e["node_key"]: e for e in _events(client, h, ex["id"]) if e["event"] == "succeeded"}
    for k, ch in (("em", "email"), ("wa", "whatsapp"), ("vc", "voice")):
        out = ev[k]["output"]
        assert out["channel"] == ch and out["delivery"] == "blocked" and not out["gate"]["allowed"]
        assert any(r.startswith("lead_status_not_eligible") for r in out["gate"]["reasons"])
    assert ev["ai"]["output"]["simulated"] is True and "SIMULATED" in ev["ai"]["output"]["text"]
    got = client.get(f"/api/v1/leads/{lead['id']}", headers=h).json()
    assert got["score"] == 77 and got["owner_user_id"]
    # missing lead -> blocked as well (never sent)
    ex = _run(client, h, wf["id"], {}).json()
    em = [e for e in _events(client, h, ex["id"]) if e["node_key"] == "em" and e["event"] == "succeeded"][0]
    assert em["output"]["delivery"] == "blocked"


def test_crm_update_cannot_grant_consent(client):
    a = register(client, "WF Consent")
    h = tenant_headers(a)
    lead = _lead(client, h)
    wf = _wf(client, h, _graph([_n("t", "trigger"), _n("cu", "crm_update", status="approved_for_outreach")],
                               [_e("t", "cu")]))
    ex = _run(client, h, wf["id"], {"lead_id": lead["id"]}).json()
    assert ex["status"] == "failed" and "consent" in ex["error"]


def test_public_webhook_trigger(client):
    a = register(client, "WF Hook")
    h = tenant_headers(a)
    r = client.post(W, headers=h, json={"name": "Hooked", "graph": _graph(
        [_n("t", "trigger", trigger_type="webhook"), _n("x", "notification")], [_e("t", "x")])})
    wf, secret = r.json(), r.json()["webhook_secret"]
    assert secret and client.post(f"{W}/{wf['id']}/versions", headers=h).status_code == 201
    r = client.post(f"/api/v1/hooks/workflows/{wf['id']}/{secret}", json={"hello": 1})
    assert r.status_code == 202, r.text
    assert client.get(f"{W}/executions/{r.json()['execution_id']}", headers=h).json()["trigger_type"] == "webhook"
    assert client.post(f"/api/v1/hooks/workflows/{wf['id']}/wrong", json={}).status_code == 404
    assert client.post(f"/api/v1/hooks/workflows/{uuid.uuid4()}/{secret}", json={}).status_code == 404
    # idempotent webhook delivery
    k = {"Idempotency-Key": "evt-1"}
    e1 = client.post(f"/api/v1/hooks/workflows/{wf['id']}/{secret}", json={}, headers=k).json()
    e2 = client.post(f"/api/v1/hooks/workflows/{wf['id']}/{secret}", json={}, headers=k).json()
    assert e1["execution_id"] == e2["execution_id"]


def test_dispatch_event_for_other_modules(client):

    a = register(client, "WF Dispatch")
    h = tenant_headers(a)
    _wf(client, h, _graph([_n("t", "trigger", trigger_type="lead_created"), _n("x", "notification")], [_e("t", "x")]))
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        exs = engine.dispatch_event(db, uuid.UUID(a["org_id"]), "lead_created", {"lead_id": None}, event_id="1")
        db.commit()
        assert len(exs) == 1 and exs[0].status == "succeeded"
        again = engine.dispatch_event(db, uuid.UUID(a["org_id"]), "lead_created", {}, event_id="1")
        assert again[0].id == exs[0].id


def test_cross_tenant_and_rbac(client):
    a, b = register(client, "WF Tenant A"), register(client, "WF Tenant B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    wf = _wf(client, ha, _graph([_n("t", "trigger"), _n("ap", "approval")], [_e("t", "ap")]))
    ex = _run(client, ha, wf["id"]).json()
    ap = client.get(f"{W}/approvals", headers=ha).json()[0]
    assert client.get(f"{W}/{wf['id']}", headers=hb).status_code == 404
    assert client.post(f"{W}/{wf['id']}/execute", headers=hb, json={}).status_code == 404
    assert client.get(f"{W}/executions/{ex['id']}", headers=hb).status_code == 404
    assert client.get(f"{W}/executions/{ex['id']}/events", headers=hb).status_code == 404
    assert client.post(f"{W}/approvals/{ap['id']}/approve", headers=hb).status_code == 404
    assert client.get(W, headers=hb).json()["total"] == 0
    # a Viewer may read but not build, run or approve
    v = register(client, "WF Viewer Home")
    r = client.post(f"/api/v1/organizations/{a['org_id']}/members", headers=a["headers"],
                    json={"email": v["email"], "role": "Viewer"})
    assert r.status_code == 201, r.text
    hv = tenant_headers(v, a["org_id"])
    assert client.get(W, headers=hv).status_code == 200
    assert client.post(W, headers=hv, json={"name": "x"}).status_code == 403
    assert client.post(f"{W}/{wf['id']}/execute", headers=hv, json={}).status_code == 403
    assert client.post(f"{W}/approvals/{ap['id']}/approve", headers=hv).status_code == 403
    assert client.delete(f"{W}/{wf['id']}", headers=hv).status_code == 403
