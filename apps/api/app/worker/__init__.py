"""Background worker (Celery).

- app/worker/jobs.py: plain, testable job bodies (no Celery import).
- app/worker/tasks.py: Celery task wrappers (retries, time limits, overlap locks).
- app/worker/celery_app.py: Celery app + beat schedule.
- app/worker/runner.py: CeleryRunner for automation workflows (enabled with CELERY_ENABLED=true).

Every job iterates organizations and runs inside ``tenant_session(org_id)`` so PostgreSQL row-level security
applies to the restricted ``leadex_app`` role exactly as for API requests.
"""
