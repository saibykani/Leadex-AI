import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_SETTINGS = (("org", "app.current_org"), ("user", "app.current_user"))


def _apply(conn, info: dict) -> None:
    for key, name in _SETTINGS:
        value = info.get(key)
        conn.exec_driver_sql("SELECT set_config(%(n)s, %(v)s, true)", {"n": name, "v": str(value) if value else ""})


if engine.dialect.name == "postgresql":

    @event.listens_for(SessionLocal, "after_begin")
    def _bind_tenant_on_begin(session, _transaction, connection):
        """Re-apply tenant/actor at the start of EVERY transaction (transaction-local, so nothing leaks
        through the pool and commits that release the connection do not drop the binding)."""
        _apply(connection, session.info)


def _is_pg(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _set(db: Session, key: str, value) -> None:
    db.info[key] = value
    if _is_pg(db) and db.in_transaction():
        _apply(db.connection(), db.info)  # already inside a transaction: apply immediately


def set_tenant(db: Session, organization_id: uuid.UUID | None) -> None:
    """Bind the tenant for PostgreSQL row-level security."""
    _set(db, "org", organization_id)


def set_actor(db: Session, user_id: uuid.UUID | None) -> None:
    """Bind the acting user (lets RLS show a user their own memberships across tenants)."""
    _set(db, "user", user_id)


@contextmanager
def tenant_session(organization_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Iterator[Session]:
    """Session bound to one tenant, for background jobs/workers/tests outside the request cycle.
    Row-level security applies exactly as for API requests."""
    db = SessionLocal()
    try:
        set_tenant(db, organization_id)
        if user_id:
            set_actor(db, user_id)
        yield db
    finally:
        db.close()
