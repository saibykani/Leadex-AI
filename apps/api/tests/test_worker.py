"""Worker jobs: per-org processing inside tenant_session, not-due skipping, per-org failure isolation.
Job bodies are called directly (no Redis); the CeleryRunner test runs the Celery task eagerly."""
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.db import tenant_session, utcnow
from app.modules.automation import engine
from app.modules.automation.models import WorkflowExecution
from app.modules.billing.models import BillingUsage, Budget, BudgetAlert, Subscription
from app.modules.campaigns import service as csvc
from app.modules.campaigns.models import Campaign, CampaignRecipient
from app.modules.discovery.models import Business, BusinessSourceField, SavedSearch, SearchJob
from app.worker import jobs
from app.worker.runner import CeleryRunner
from tests.conftest import register, tenant_headers
from tests.test_communication import _approve, _lead, _template
from tests.test_communication import _env as _comm_env  # noqa: F401 (autouse fixture: clears provider env)
from tests.test_workflows import _e, _graph, _n, _run, _wf

D = "/api/v1/discovery"


def _two_orgs(client, prefix):
    a, b = register(client, f"{prefix} A"), register(client, f"{prefix} B")
    return (a, tenant_headers(a), uuid.UUID(a["org_id"])), (b, tenant_headers(b), uuid.UUID(b["org_id"]))


def test_is_due():
    now = datetime(2026, 1, 5, 6, 0, 30, tzinfo=UTC)  # Monday 06:00:30
    assert jobs.is_due("* * * * *", now - timedelta(minutes=2), None, now)
    assert not jobs.is_due("* * * * *", now - timedelta(seconds=10), None, now)
    assert jobs.is_due("0 6 * * 1", now - timedelta(days=7), None, now)
    assert not jobs.is_due("0 6 * * 1", now - timedelta(seconds=20), None, now)
    assert not jobs.is_due("every day", None, now - timedelta(days=9), now)
    assert not jobs.is_due(None, None, None, now)
    assert jobs.is_due("* * * * *", None, (now - timedelta(minutes=5)).replace(tzinfo=None), now)  # naive (SQLite)


def test_saved_searches_per_org(client):
    (_, ha, oa), (_, hb, ob) = _two_orgs(client, "Wk Search")
    ids = {}
    for h, org in ((ha, oa), (hb, ob)):
        for name, sched in (("due", "* * * * *"), ("later", "0 6 * * 1")):
            r = client.post(f"{D}/saved-searches", headers=h, json={
                "name": name, "criteria": {"source": "simulated", "city": "Pune", "limit": 2}, "schedule": sched})
            assert r.status_code == 201, r.text
            ids[(org, name)] = uuid.UUID(r.json()["id"])
        with tenant_session(org) as db:
            for s in db.scalars(select(SavedSearch).where(SavedSearch.organization_id == org)):
                s.last_run_at = utcnow() - (timedelta(minutes=3) if s.name == "due" else timedelta(seconds=1))
            db.commit()
    out = jobs.run_due_saved_searches(orgs=[oa, ob])
    assert out["processed"] == 2 and out["failed"] == []
    for org in (oa, ob):
        with tenant_session(org) as db:
            js = db.scalars(select(SearchJob).where(SearchJob.organization_id == org)).all()
            assert [j.saved_search_id for j in js] == [ids[(org, "due")]]
            assert js[0].status == "completed" and js[0].new_count == 2
    # idempotent: immediately re-running finds nothing due
    assert jobs.run_due_saved_searches(orgs=[oa, ob])["processed"] == 0


def _running_campaign(client, h):
    lead = _lead(client, h)
    t = _template(client, h)
    r = client.post("/api/v1/campaigns", headers=h, json={"name": "Seq", "channel": "email", "email": {
        "steps": [{"template_id": t["id"], "delay_hours": 0}, {"template_id": t["id"], "delay_hours": 0}],
        "physical_address": "1 Market St"}})
    cid = r.json()["id"]
    client.post(f"/api/v1/campaigns/{cid}/recipients", headers=h, json={"lead_ids": [lead["id"]]})
    _approve(client, h, cid)
    r = client.post(f"/api/v1/campaigns/{cid}/start", headers={**h, "Idempotency-Key": uuid.uuid4().hex})
    assert r.json()["status"] == "running", r.text
    return uuid.UUID(cid)


def _campaign_status(org, cid):
    with tenant_session(org) as db:
        return db.get(Campaign, cid).status


def test_campaign_tick_per_org_and_failure_isolation(client, monkeypatch):
    (_, ha, oa), (_, hb, ob) = _two_orgs(client, "Wk Camp")
    ca, cb = _running_campaign(client, ha), _running_campaign(client, hb)
    real = csvc.process_due

    def flaky(db, c, actor, now=None):
        if c.organization_id == oa:
            raise RuntimeError("boom")
        return real(db, c, actor, now)

    monkeypatch.setattr(csvc, "process_due", flaky)
    out = jobs.tick_running_campaigns(orgs=[oa, ob])
    assert out["failed"] == [str(oa)] and out["processed"] == 1
    assert _campaign_status(oa, ca) == "running" and _campaign_status(ob, cb) == "completed"
    monkeypatch.setattr(csvc, "process_due", real)
    out = jobs.tick_running_campaigns(orgs=[oa, ob])
    assert out["failed"] == [] and out["processed"] == 1  # only org A's campaign was still running
    assert _campaign_status(oa, ca) == "completed"
    with tenant_session(oa) as db:  # no cross-tenant rows touched/visible
        assert {r.campaign_id for r in db.scalars(select(CampaignRecipient).where(
            CampaignRecipient.organization_id == oa))} == {ca}


def test_resume_due_workflows(client):
    (_, ha, oa), (_, hb, ob) = _two_orgs(client, "Wk Flow")
    ex = {}
    for h, org in ((ha, oa), (hb, ob)):
        for secs in (0, 3600):
            wf = _wf(client, h, _graph([_n("t", "trigger"), _n("d", "delay", seconds=secs), _n("x", "notification")],
                                       [_e("t", "d"), _e("d", "x")]))
            ex[(org, secs)] = uuid.UUID(_run(client, h, wf["id"]).json()["id"])
    out = jobs.resume_due_workflows(orgs=[oa, ob])
    assert out["processed"] == 2 and out["failed"] == []
    for org in (oa, ob):
        with tenant_session(org) as db:
            assert db.get(WorkflowExecution, ex[(org, 0)]).status == "succeeded"
            assert db.get(WorkflowExecution, ex[(org, 3600)]).status == "waiting"


def test_purge_expired_google_fields(client):
    (_, _, oa), (_, _, ob) = _two_orgs(client, "Wk Purge")
    past = utcnow() - timedelta(days=1)
    for org in (oa, ob):
        with tenant_session(org) as db:
            for name, ret in (("Expired Co", past), ("Fresh Co", utcnow() + timedelta(days=10))):
                biz = Business(organization_id=org, name=name, source="google_places")
                db.add(biz)
                db.flush()
                db.add(BusinessSourceField(organization_id=org, business_id=biz.id, field="name", value=name,
                                           source="google_places", retention_until=ret))
            db.commit()
    out = jobs.purge_expired_google_fields(orgs=[oa, ob])
    assert out["failed"] == [] and out["processed"] >= 2
    for org in (oa, ob):
        with tenant_session(org) as db:
            names = sorted(str(b.name) for b in db.scalars(select(Business).where(Business.organization_id == org)))
            assert names == ["Fresh Co", "None"]


def test_billing_daily(client):
    (_, ha, oa), (_, hb, ob) = _two_orgs(client, "Wk Bill")
    _, hc, oc = _two_orgs(client, "Wk Bill2")[0]
    for h in (ha, hb, hc):
        client.get("/api/v1/billing/subscription", headers=h)
    for org in (oa, ob):
        with tenant_session(org) as db:
            sub = db.scalar(select(Subscription).where(Subscription.organization_id == org))
            sub.trial_end = utcnow() - timedelta(minutes=1)
            db.commit()
    with tenant_session(oa) as db:
        db.add(BillingUsage(organization_id=oa, resource="ai_tokens", quantity=Decimal(1), cost=Decimal("9")))
        db.add(Budget(organization_id=oa, monthly_limit=Decimal("10"), alert_thresholds=[50, 80, 100]))
        db.commit()
    out = jobs.billing_daily(orgs=[oa, ob, oc])
    assert out["failed"] == []
    for org, status in ((oa, "past_due"), (ob, "past_due"), (oc, "trialing")):
        with tenant_session(org) as db:
            assert db.scalar(select(Subscription.status).where(Subscription.organization_id == org)) == status
    with tenant_session(oa) as db:
        assert sorted(db.scalars(select(BudgetAlert.threshold).where(BudgetAlert.organization_id == oa))) == [50, 80]
    with tenant_session(ob) as db:
        assert db.scalars(select(BudgetAlert).where(BudgetAlert.organization_id == ob)).all() == []
    assert jobs.billing_daily(orgs=[oa])["processed"] == 1  # alerts are not re-fired


def test_failure_in_one_org_does_not_stop_others(client):
    (_, _, oa), (_, _, ob) = _two_orgs(client, "Wk Iso")
    seen = []

    def fn(db, org):
        seen.append(org)
        if org == oa:
            raise RuntimeError("tenant A broken")
        return 1

    out = jobs.for_each_org("t", fn, orgs=[oa, ob])
    assert seen == [oa, ob] and out == {"job": "t", "orgs": 2, "processed": 1, "failed": [str(oa)]}


@pytest.fixture
def celery_runner(monkeypatch):
    monkeypatch.setattr(engine, "runner", CeleryRunner())


def test_celery_runner_runs_after_commit(client, celery_runner):
    from app.worker.celery_app import celery_app

    assert celery_app.conf.task_always_eager  # no REDIS_URL in tests -> eager
    a = register(client, "Wk Runner")
    h = tenant_headers(a)
    wf = _wf(client, h, _graph([_n("t", "trigger"), _n("x", "notification")], [_e("t", "x")]))
    ex_id = uuid.UUID(_run(client, h, wf["id"]).json()["id"])
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        assert db.get(WorkflowExecution, ex_id).status == "succeeded"
