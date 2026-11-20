import uuid

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class DemoWorkspace(IdMixin, TimestampMixin, Base):
    """Marks an organization as an investor-demo workspace filled with FICTIONAL sample data.

    Demo data only ever lives in its own organization (never mixed into a real tenant). RLS lets a row be seen
    from inside the demo org itself or by the user who owns it (so the owner can find/reset it from a real org)."""

    __tablename__ = "demo_workspaces"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_demo_workspaces_org"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    summary: Mapped[dict | None] = mapped_column(JSON)
