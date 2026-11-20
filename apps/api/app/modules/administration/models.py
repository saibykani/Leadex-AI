import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class Integration(IdMixin, TimestampMixin, Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("organization_id", "provider", name="uq_integration_org_provider"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="not_configured")
    config: Mapped[dict | None] = mapped_column(JSON)  # non-secret settings only


class IntegrationCredential(IdMixin, TimestampMixin, Base):
    __tablename__ = "integration_credentials"
    __table_args__ = (UniqueConstraint("integration_id", "name", name="uq_integration_cred_name"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    secret_enc: Mapped[str] = mapped_column(Text)


class Notification(IdMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_org_user", "organization_id", "user_id", "read_at"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportTicket(IdMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (Index("ix_support_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    status: Mapped[str] = mapped_column(String(20), default="open")
