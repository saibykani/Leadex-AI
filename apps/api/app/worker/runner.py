"""CeleryRunner: automation Runner that executes workflows on the worker instead of in the request.

Switch: set ``CELERY_ENABLED=true`` in the API and worker environment. ``install_runner()`` (called at API and
worker start-up) then replaces ``engine.runner`` (default ``SyncRunner``). With any other value the in-process
SyncRunner stays the default, so tests and single-process dev behave exactly as before.

The execution row is only flushed when ``submit`` is called, so the task is enqueued after the session commits
(otherwise the worker could look for a row that is not yet visible, or that was rolled back).
"""
import os
import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

_PENDING = "celery_pending_executions"


def celery_enabled() -> bool:
    return os.environ.get("CELERY_ENABLED", "").strip().lower() == "true"


def _after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING, [])
    if not pending:
        return
    from app.worker.tasks import run_workflow_execution

    for org_id, ex_id in pending:
        run_workflow_execution.apply_async(args=[str(org_id), str(ex_id)], task_id=f"wf-exec-{ex_id}")


def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)


class CeleryRunner:
    def submit(self, db: Session, execution_id: uuid.UUID) -> None:
        from app.modules.automation.models import WorkflowExecution

        ex = db.get(WorkflowExecution, execution_id)
        if ex is None:
            return
        db.info.setdefault(_PENDING, []).append((ex.organization_id, execution_id))
        if not event.contains(db, "after_commit", _after_commit):
            event.listen(db, "after_commit", _after_commit)
            event.listen(db, "after_soft_rollback", lambda s, _t: _after_rollback(s))


def install_runner() -> None:
    if celery_enabled():
        from app.modules.automation import engine

        if not isinstance(engine.runner, CeleryRunner):
            engine.runner = CeleryRunner()
