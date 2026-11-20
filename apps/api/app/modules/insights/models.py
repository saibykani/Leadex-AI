import uuid

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class OnboardingProgress(IdMixin, TimestampMixin, Base):
    """First-run checklist state for one organization. `steps` maps step key -> {"done": bool, "at": iso, ...}.
    Most steps are ALSO derived from real data (e.g. a lead exists); stored flags only record explicit
    completions/skips the data cannot express (e.g. "integrations reviewed")."""

    __tablename__ = "onboarding_progress"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_onboarding_progress_org"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    steps: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict | None] = mapped_column(JSON)
