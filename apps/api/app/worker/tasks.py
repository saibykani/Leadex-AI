"""Celery task wrappers around app.worker.jobs.

- Transient DB/broker errors retry with exponential backoff (max 3).
- Periodic sweeps take a short Redis lock so overlapping beat ticks (slow run, duplicate beat) don't run twice.
  Item-level idempotency lives in the jobs (saved searches mark last_run_at first; campaigns only send due
  recipients; workflow resume only touches due ``waiting`` executions; run_execution never re-runs nodes).
"""
import logging
import uuid
from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import get_settings
from app.worker import jobs
from app.worker.celery_app import celery_app

log = logging.getLogger("leadex.worker")

TRANSIENT = (OperationalError, DBAPIError, ConnectionError, TimeoutError)
_RETRY = {"autoretry_for": TRANSIENT, "retry_backoff": True, "retry_backoff_max": 300, "retry_jitter": True,
          "max_retries": 3}


@contextmanager
def single_flight(name: str, ttl: int):
    """Yield True if this process holds the lock (or Redis is not configured), False if another run holds it."""
    url = get_settings().redis_url
    if not url:
        yield True
        return
    import redis

    client = redis.Redis.from_url(url, socket_timeout=5)
    key = f"leadex:worker:lock:{name}"
    token = uuid.uuid4().hex
    got = bool(client.set(key, token, nx=True, ex=ttl))
    try:
        yield got
    finally:
        if got and client.get(key) == token.encode():
            client.delete(key)


def _sweep(name: str, ttl: int, fn) -> dict:
    with single_flight(name, ttl) as ok:
        if not ok:
            log.info("worker job %s skipped: previous run still in progress", name)
            return {"job": name, "skipped": "locked"}
        return fn()


@celery_app.task(name="leadex.run_due_saved_searches", **_RETRY)
def run_due_saved_searches() -> dict:
    return _sweep("saved_searches", 290, jobs.run_due_saved_searches)


@celery_app.task(name="leadex.tick_running_campaigns", **_RETRY)
def tick_running_campaigns() -> dict:
    return _sweep("campaigns", 290, jobs.tick_running_campaigns)


@celery_app.task(name="leadex.resume_due_workflows", **_RETRY)
def resume_due_workflows() -> dict:
    return _sweep("workflows", 290, jobs.resume_due_workflows)


@celery_app.task(name="leadex.purge_expired_google_fields", soft_time_limit=1700, time_limit=1800, **_RETRY)
def purge_expired_google_fields() -> dict:
    return _sweep("purge_google", 1800, jobs.purge_expired_google_fields)


@celery_app.task(name="leadex.billing_daily", soft_time_limit=1700, time_limit=1800, **_RETRY)
def billing_daily() -> dict:
    return _sweep("billing", 1800, jobs.billing_daily)


@celery_app.task(name="leadex.run_workflow_execution", **_RETRY)
def run_workflow_execution(org_id: str, execution_id: str) -> str | None:
    return jobs.run_workflow_execution(uuid.UUID(org_id), uuid.UUID(execution_id))
