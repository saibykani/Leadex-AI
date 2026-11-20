"""Safe cross-module event emission: a failing/absent workflow never breaks the caller's request."""
import logging
import uuid

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def emit_event(db: Session, organization_id: uuid.UUID, trigger_type: str, payload: dict,
               event_id: str | None = None) -> int:
    """Run automation.dispatch_event inside a SAVEPOINT; on any error roll back only the savepoint and log.
    Returns the number of executions started. Caller commits."""
    from app.modules.automation.engine import dispatch_event

    try:
        with db.begin_nested():
            return len(dispatch_event(db, organization_id, trigger_type, payload, event_id=event_id))
    except Exception:  # noqa: BLE001 - events are best effort by design
        log.exception("event dispatch failed: %s", trigger_type)
        return 0
