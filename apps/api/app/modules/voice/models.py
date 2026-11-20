import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


def _call() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("call_sessions.id", ondelete="CASCADE"))


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CallSession(IdMixin, TimestampMixin, Base):
    """status: queued | blocked | simulated_completed | not_configured | initiated | ringing | in_progress |
    completed | busy | no_answer | failed | canceled."""

    __tablename__ = "call_sessions"
    __table_args__ = (Index("ix_call_sessions_org_created", "organization_id", "created_at"),
                      Index("ix_call_sessions_org_lead", "organization_id", "lead_id"))
    organization_id: Mapped[uuid.UUID] = _org()
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_agents.id", ondelete="CASCADE"))
    agent_version: Mapped[int | None] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10), default="outbound")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    gate_reasons: Mapped[list | None] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(30), default="simulated")
    language: Mapped[str] = mapped_column(String(10), default="en")
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Telephony (migration 0015). provider_call_id = Twilio CallSid; error_message = provider error, verbatim.
    provider_call_id: Mapped[str | None] = mapped_column(String(64))
    to_number: Mapped[str | None] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    price_unit: Mapped[str | None] = mapped_column(String(8))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))


class CallEvent(IdMixin, Base):
    """Append-only call timeline."""

    __tablename__ = "call_events"
    __table_args__ = (Index("ix_call_events_org_call", "organization_id", "call_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    call_id: Mapped[uuid.UUID] = _call()
    type: Mapped[str] = mapped_column(String(60))
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()


class CallTranscript(IdMixin, Base):
    """Append-only transcript segments. speaker: agent | contact | system."""

    __tablename__ = "call_transcripts"
    __table_args__ = (Index("ix_call_transcripts_org_call", "organization_id", "call_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    call_id: Mapped[uuid.UUID] = _call()
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _created()


class CallSummary(IdMixin, TimestampMixin, Base):
    __tablename__ = "call_summaries"
    __table_args__ = (Index("ix_call_summaries_org_call", "organization_id", "call_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    call_id: Mapped[uuid.UUID] = _call()
    summary: Mapped[str] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)


class CallDisposition(IdMixin, TimestampMixin, Base):
    __tablename__ = "call_dispositions"
    __table_args__ = (Index("ix_call_dispositions_org_call", "organization_id", "call_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    call_id: Mapped[uuid.UUID] = _call()
    disposition: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CallRecording(IdMixin, TimestampMixin, Base):
    """Metadata only. Recording stays disabled unless a consent reference is captured."""

    __tablename__ = "call_recordings"
    __table_args__ = (Index("ix_call_recordings_org_call", "organization_id", "call_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    call_id: Mapped[uuid.UUID] = _call()
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_reference: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    duration_s: Mapped[int | None] = mapped_column(Integer)
