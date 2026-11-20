"""Pipeline data model (migration 0014).

* business_images: images the customer is allowed to use (owner-supplied uploads, or images found on the
  business's OWN website and confirmed by a user). Google Places photos are NEVER stored here: they are only
  referenced in provenance (field='photo') and proxied for in-app display (Maps Platform terms).
* conversation_outcomes: structured result of a conversation (test lab or call).
* pipeline_runs: one-click pipeline state, one row per (org, business); every step's status is recorded.
* pipeline_settings: per-org sales package price ranges used by the budget-discovery agent.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


def _org():
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


class BusinessImage(IdMixin, TimestampMixin, Base):
    __tablename__ = "business_images"
    __table_args__ = (Index("ix_business_images_org_biz", "organization_id", "business_id"),
                      UniqueConstraint("public_token", name="uq_business_images_token"))
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(30))  # owner_supplied | from_business_website
    status: Mapped[str] = mapped_column(String(20), default="pending_review")  # pending_review|approved|rejected
    permission_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    permission_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    origin_url: Mapped[str | None] = mapped_column(String(1000))
    filename: Mapped[str | None] = mapped_column(String(255))
    alt: Mapped[str | None] = mapped_column(String(300))
    public_token: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ConversationOutcome(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversation_outcomes"
    __table_args__ = (Index("ix_conv_outcomes_org_lead", "organization_id", "lead_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_agents.id", ondelete="SET NULL"))
    call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("call_sessions.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(20))  # test_lab | browser_voice | call
    extraction_mode: Mapped[str] = mapped_column(String(10))  # llm | rules
    model: Mapped[str | None] = mapped_column(String(120))
    interest: Mapped[str] = mapped_column(String(10))  # high | medium | low | none | unknown
    budget_min: Mapped[float | None] = mapped_column(Numeric(14, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(14, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    budget_evidence: Mapped[str | None] = mapped_column(Text)
    timeline: Mapped[str | None] = mapped_column(String(200))
    timeline_evidence: Mapped[str | None] = mapped_column(Text)
    decision_maker: Mapped[str | None] = mapped_column(String(200))
    decision_maker_evidence: Mapped[str | None] = mapped_column(Text)
    objections: Mapped[list | None] = mapped_column(JSON)
    next_step: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    transcript: Mapped[list | None] = mapped_column(JSON)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PipelineRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("organization_id", "business_id", name="uq_pipeline_runs_org_biz"),)
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    website_project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("website_projects.id",
                                                                            ondelete="SET NULL"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_agents.id", ondelete="SET NULL"))
    call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("call_sessions.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|completed|needs_action|failed
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PipelineSettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_pipeline_settings_org"),)
    organization_id: Mapped[uuid.UUID] = _org()
    # [{name, min, max, currency, description}]
    packages: Mapped[list] = mapped_column(JSON, default=list)
