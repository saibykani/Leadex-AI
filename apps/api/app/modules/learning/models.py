import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)


class ScriptVariant(IdMixin, TimestampMixin, Base):
    """An alternative call opening for an agent. The bandit picks among active variants."""

    __tablename__ = "agent_script_variants"
    __table_args__ = (Index("ix_script_variants_org_agent", "organization_id", "agent_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_agents.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    opening: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CallLearning(IdMixin, Base):
    """One row per AI call: which variant was used and how the call went.

    reward: 1 (good outcome), 0 (bad), NULL (not yet known / no conversation, excluded from learning).
    reward_source: auto (from the extracted outcome) | human (a reviewer's rating, overrides auto).
    """

    __tablename__ = "call_learning"
    __table_args__ = (Index("ix_call_learning_org_agent", "organization_id", "agent_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_agents.id", ondelete="CASCADE"))
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sessions.id", ondelete="CASCADE"), unique=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_script_variants.id", ondelete="SET NULL"))
    reward: Mapped[int | None] = mapped_column(Integer)
    reward_source: Mapped[str | None] = mapped_column(String(10))
    label: Mapped[str | None] = mapped_column(String(40))  # interested | not_interested | opted_out | no_conversation
    feedback_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
