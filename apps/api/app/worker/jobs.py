"""Plain job bodies (no Celery dependency) so they can be unit-tested directly.

Each job lists organization ids with a tenant-less session (the organizations table is not row-level-secured),
then processes every organization inside its own ``tenant_session`` with a commit per org. A failure in one
organization is logged, rolled back and reported in the summary; the remaining organizations still run.
"""
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, tenant_session, utcnow

log = logging.getLogger("leadex.worker")


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def org_ids() -> list[uuid.UUID]:
    from app.modules.identity.models import Organization

    with SessionLocal() as db:
        return list(db.scalars(select(Organization.id).order_by(Organization.created_at, Organization.id)))


def for_each_org(name: str, fn: Callable[[Session, uuid.UUID], int], orgs: list[uuid.UUID] | None = None) -> dict:
    """Run ``fn(db, org_id)`` per organization. Returns {"job", "orgs", "processed", "failed": [org ids]}."""
    summary: dict = {"job": name, "orgs": 0, "processed": 0, "failed": []}
    for org_id in orgs if orgs is not None else org_ids():
        summary["orgs"] += 1
        with tenant_session(org_id) as db:
            try:
                summary["processed"] += int(fn(db, org_id) or 0)
                db.commit()
            except Exception:
                db.rollback()
                log.exception("worker job %s failed for organization %s", name, org_id)
                summary["failed"].append(str(org_id))
    if summary["failed"] or summary["processed"]:
        log.info("worker job %s: %s", name, summary)
    return summary


# ---------------------------------------------------------------- discovery: scheduled saved searches
def is_due(schedule: str | None, last_run_at: datetime | None, created_at: datetime | None, now: datetime) -> bool:
    """Due when the first cron fire time after the last run (or creation) is <= now (UTC). Invalid cron: never."""
    if not schedule or not croniter.is_valid(schedule):
        return False
    base = _aware(last_run_at) or _aware(created_at) or now
    return croniter(schedule, base).get_next(datetime) <= now


def run_due_saved_searches_for_org(db: Session, org_id: uuid.UUID, now: datetime | None = None) -> int:
    from app.modules.discovery import service as dsvc
    from app.modules.discovery.models import SavedSearch

    now = now or utcnow()
    ran = 0
    rows = db.scalars(select(SavedSearch).where(SavedSearch.organization_id == org_id,
                                                SavedSearch.schedule.is_not(None))).all()
    for s in rows:
        if not is_due(s.schedule, s.last_run_at, s.created_at, now):
            continue
        # Mark first (idempotency): a failing provider must not make the search re-fire every minute,
        # and an overlapping/redelivered task sees it as not due.
        s.last_run_at = now
        db.commit()
        ctx = SimpleNamespace(organization_id=org_id, user=SimpleNamespace(id=s.created_by_user_id))
        try:
            dsvc.run_search(db, ctx, dict(s.criteria or {}), s.id)  # type: ignore[arg-type]
            ran += 1
        except Exception:
            db.rollback()
            log.exception("scheduled saved search %s (org %s) failed", s.id, org_id)
    return ran


def run_due_saved_searches(now: datetime | None = None, orgs=None) -> dict:
    return for_each_org("saved_searches", lambda db, o: run_due_saved_searches_for_org(db, o, now), orgs)


# ---------------------------------------------------------------- campaigns
def tick_campaigns_for_org(db: Session, org_id: uuid.UUID, now: datetime | None = None) -> int:
    from app.modules.campaigns import service as csvc
    from app.modules.campaigns.models import Campaign

    n = 0
    for c in db.scalars(select(Campaign).where(Campaign.organization_id == org_id,
                                               Campaign.status == "running")).all():
        counts = csvc.process_due(db, c, None, now)
        db.commit()
        n += sum(counts.values())
    return n


def tick_running_campaigns(now: datetime | None = None, orgs=None) -> dict:
    return for_each_org("campaigns", lambda db, o: tick_campaigns_for_org(db, o, now), orgs)


# ---------------------------------------------------------------- automation
def resume_due_workflows_for_org(db: Session, org_id: uuid.UUID, now: datetime | None = None,
                                 limit: int = 200) -> int:
    from app.modules.automation import engine
    from app.modules.automation.models import WorkflowExecution

    now = now or utcnow()
    due = db.scalars(select(WorkflowExecution.id).where(
        WorkflowExecution.organization_id == org_id, WorkflowExecution.status == "waiting",
        WorkflowExecution.resume_at.is_not(None), WorkflowExecution.resume_at <= now).limit(limit)).all()
    for ex_id in due:
        engine.run_execution(db, ex_id, resume_output={"resumed_at": now.isoformat(), "by": "worker"})
        db.commit()
    return len(due)


def resume_due_workflows(now: datetime | None = None, orgs=None) -> dict:
    return for_each_org("workflows", lambda db, o: resume_due_workflows_for_org(db, o, now), orgs)


def run_workflow_execution(org_id: uuid.UUID, execution_id: uuid.UUID) -> str | None:
    """Body of the CeleryRunner task. run_execution is idempotent (resolved nodes are never re-run)."""
    from app.modules.automation import engine

    with tenant_session(org_id) as db:
        ex = engine.run_execution(db, execution_id)
        db.commit()
        return ex.status if ex is not None else None


# ---------------------------------------------------------------- discovery: Google Places retention purge
def purge_expired_google_fields(now: datetime | None = None, orgs=None) -> dict:
    from app.modules.discovery.service import purge_expired_provider_fields

    return for_each_org("purge_google", lambda db, o: purge_expired_provider_fields(db, now=now), orgs)


# ---------------------------------------------------------------- billing
def billing_daily_for_org(db: Session, org_id: uuid.UUID) -> int:
    """Trial expiry + renewal invoices (applied by get_subscription) and budget alerts for the month so far."""
    from app.modules.billing import service as bsvc
    from app.modules.billing.models import Subscription

    n = 0
    # Only orgs that already have a subscription: get_subscription would otherwise lazily create a trial.
    if db.scalar(select(Subscription.id).where(Subscription.organization_id == org_id)) is not None:
        bsvc.get_subscription(db, org_id)
        n += 1
    b = bsvc.get_budget(db, org_id)
    if b is not None and b.monthly_limit:
        n += len(bsvc._alert(db, org_id, "budget", "spend", bsvc.month_spend(db, org_id), b.monthly_limit,
                             b.alert_thresholds or (50, 80, 100)))
    return n


def billing_daily(orgs=None) -> dict:
    return for_each_org("billing", billing_daily_for_org, orgs)
