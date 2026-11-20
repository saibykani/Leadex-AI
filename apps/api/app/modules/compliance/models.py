import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org():
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


def _user():
    return mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ConsentRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "consent_records"
    __table_args__ = (Index("ix_consent_org_lead_channel", "organization_id", "lead_id", "channel"),)
    organization_id: Mapped[uuid.UUID] = _org()
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20))
    basis: Mapped[str] = mapped_column(String(40))
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(1000))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_reason: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[uuid.UUID | None] = _user()


class SuppressionRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppression_records"
    __table_args__ = (
        Index("ix_suppression_org_email", "organization_id", "email_normalized"),
        Index("ix_suppression_org_phone", "organization_id", "phone_normalized"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    channel: Mapped[str] = mapped_column(String(20), default="all")
    email_normalized: Mapped[str | None] = mapped_column(String(320))
    phone_normalized: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))
    created_by_user_id: Mapped[uuid.UUID | None] = _user()


class CommunicationPreference(IdMixin, TimestampMixin, Base):
    __tablename__ = "communication_preferences"
    __table_args__ = (UniqueConstraint("organization_id", "lead_id", "channel", name="uq_comm_pref_lead_channel"),)
    organization_id: Mapped[uuid.UUID] = _org()
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(String(500))


class JurisdictionProfile(IdMixin, TimestampMixin, Base):
    """Platform-wide reference data (no tenant)."""

    __tablename__ = "jurisdiction_profiles"
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    rules: Mapped[dict] = mapped_column(JSON)


class KillSwitch(IdMixin, TimestampMixin, Base):
    __tablename__ = "kill_switches"
    __table_args__ = (Index("ix_kill_switch_org_active", "organization_id", "active"),)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(20))  # global | organization
    channel: Mapped[str] = mapped_column(String(20), default="all")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(500))
    set_by_user_id: Mapped[uuid.UUID | None] = _user()


class DataSubjectRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "data_subject_requests"
    __table_args__ = (Index("ix_dsr_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = _org()
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="open")
    subject_email: Mapped[str | None] = mapped_column(String(320))
    subject_phone: Mapped[str | None] = mapped_column(String(40))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    details: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = _user()
