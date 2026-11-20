import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class Campaign(IdMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(20))  # email | whatsapp | voice
    # draft | pending_approval | approved | running | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="draft")
    spend_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cost_per_message: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    spent: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    send_window: Mapped[dict | None] = mapped_column(JSON)  # {"start_hour": 9, "end_hour": 18} UTC
    # Voice campaigns (migration 0021): which AI agent calls, and how many calls may run at once.
    voice_agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_agents.id", ondelete="SET NULL"))
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=3)
    whatsapp_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_templates.id", ondelete="SET NULL"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CampaignRecipient(IdMixin, TimestampMixin, Base):
    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_recipient"),
        Index("ix_campaign_recipients_org_due", "organization_id", "campaign_id", "next_due_at"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    # pending | blocked | simulated | sent | failed | replied | unsubscribed | completed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    gate_allowed: Mapped[bool | None] = mapped_column(Boolean)
    gate_simulated: Mapped[bool | None] = mapped_column(Boolean)
    gate_reasons: Mapped[list | None] = mapped_column(JSON)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CampaignApproval(IdMixin, Base):
    __tablename__ = "campaign_approvals"
    __table_args__ = (Index("ix_campaign_approvals_org_campaign", "organization_id", "campaign_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(20))  # approved | rejected
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CampaignEvent(IdMixin, Base):
    """Append-only. The application never updates or deletes rows."""

    __tablename__ = "campaign_events"
    __table_args__ = (Index("ix_campaign_events_org_campaign_created", "organization_id", "campaign_id",
                            "created_at"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(60))
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
