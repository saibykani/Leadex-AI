import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class PortalAccount(IdMixin, Base):
    """An external portal identity (provider or customer) inside one tenant.

    Global table (no RLS): looked up by email / token hash before any tenant is known. It holds only the
    login email and ids; all marketplace data stays in tenant tables behind RLS.
    """

    __tablename__ = "portal_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "role", "subject_id", name="uq_portal_account_subject"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # provider | customer
    subject_id: Mapped[uuid.UUID] = mapped_column()  # service_providers.id | customers.id (checked in code)
    email: Mapped[str] = mapped_column(String(320), index=True)  # lower-case
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PortalToken(IdMixin, Base):
    """Single-use, hashed, expiring magic-link token. Global table (see PortalAccount)."""

    __tablename__ = "portal_tokens"
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portal_accounts.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
