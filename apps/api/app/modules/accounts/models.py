import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class AccountToken(IdMixin, Base):
    """Single-use, hashed, expiring tokens for password reset, email verification and invitations.

    Global table (no RLS): looked up by token hash before any tenant is known. Holds no tenant data beyond
    the invited organization/role ids.
    """

    __tablename__ = "account_tokens"
    purpose: Mapped[str] = mapped_column(String(20))  # password_reset | email_verify | invite
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
