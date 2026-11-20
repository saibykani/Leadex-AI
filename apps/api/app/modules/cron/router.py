"""Scheduled jobs over HTTP, for serverless hosts (Vercel) where no Celery worker/beat runs.

Call ``GET /api/v1/internal/cron/{job}`` with ``Authorization: Bearer $CRON_SECRET`` (Vercel Cron sends this
header automatically). Jobs are the same idempotent sweeps the Celery beat runs; disabled unless CRON_SECRET is set.
"""
import hmac
import os

from fastapi import APIRouter, Header

from app.core.errors import AppError
from app.worker import jobs

router = APIRouter(tags=["cron"])

JOBS = {
    "minute": ("saved_searches", "campaigns", "workflows"),
    "saved_searches": ("saved_searches",),
    "campaigns": ("campaigns",),
    "workflows": ("workflows",),
    "daily": ("purge_google", "billing"),
}
_FN = {
    "saved_searches": jobs.run_due_saved_searches,
    "campaigns": jobs.tick_running_campaigns,
    "workflows": jobs.resume_due_workflows,
    "purge_google": jobs.purge_expired_google_fields,
    "billing": jobs.billing_daily,
}


@router.get("/internal/cron/{job}")
def run_cron(job: str, authorization: str | None = Header(None)):
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise AppError(404, "not_found", "Not found")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise AppError(401, "unauthorized", "Invalid cron secret")
    if job not in JOBS:
        raise AppError(404, "unknown_job", "Unknown job")
    return {"job": job, "results": {name: _FN[name]() for name in JOBS[job]}}
