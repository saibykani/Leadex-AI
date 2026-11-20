import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class DncEntry(IdMixin, Base):
    """A number listed on a national do-not-call registry, as imported by this organization from its own
    registry subscription (e.g. TRAI NCPR / DLT scrub file, US National DNC download). Stored as E.164."""

    __tablename__ = "dnc_registry_entries"
    __table_args__ = (Index("ix_dnc_entries_org_phone", "organization_id", "phone_e164"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    country: Mapped[str] = mapped_column(String(2))
    phone_e164: Mapped[str] = mapped_column(String(20))
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dnc_registry_imports.id", ondelete="CASCADE"))


class DncImport(IdMixin, Base):
    __tablename__ = "dnc_registry_imports"
    __table_args__ = (Index("ix_dnc_imports_org_country", "organization_id", "country"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    country: Mapped[str] = mapped_column(String(2))
    source: Mapped[str] = mapped_column(String(200))
    rows: Mapped[int] = mapped_column(Integer)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    imported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
