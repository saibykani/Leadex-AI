"""Celery application + beat schedule.

Run (see docker-compose.yml services ``worker`` / ``beat``):
    celery -A app.worker.celery_app worker -l info
    celery -A app.worker.celery_app beat -l info

Broker and result backend are REDIS_URL. Without REDIS_URL (tests) tasks run eagerly in-process.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.modules.registry import import_models

import_models()  # complete SQLAlchemy metadata (relationships / FKs across modules)

_settings = get_settings()
_broker = _settings.redis_url or "memory://"

celery_app = Celery("leadex", broker=_broker, backend=_settings.redis_url or "cache+memory://",
                    include=["app.worker.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # redeliver if a worker dies mid-task (all tasks are idempotent)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=240,
    task_time_limit=300,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    task_always_eager=_settings.redis_url is None,
    beat_schedule={
        "saved-searches-every-minute": {"task": "leadex.run_due_saved_searches", "schedule": 60.0},
        "campaigns-every-minute": {"task": "leadex.tick_running_campaigns", "schedule": 60.0},
        "workflows-every-minute": {"task": "leadex.resume_due_workflows", "schedule": 60.0},
        "purge-google-daily": {"task": "leadex.purge_expired_google_fields",
                               "schedule": crontab(hour=3, minute=0)},
        "billing-daily": {"task": "leadex.billing_daily", "schedule": crontab(hour=0, minute=30)},
    },
)

# Workflows started inside worker tasks (e.g. events fired by campaigns) also go through the configured runner.
from app.worker.runner import install_runner  # noqa: E402

install_runner()
app = celery_app  # `celery -A app.worker.celery_app` finds `app` / `celery_app`
