import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class Lead(IdMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_org_status", "organization_id", "status"),
        Index("ix_leads_org_email", "organization_id", "email_normalized"),
        Index("ix_leads_org_phone", "organization_id", "phone_normalized"),
        Index("ix_leads_org_domain", "organization_id", "website_domain"),
        Index("ix_leads_org_created", "organization_id", "created_at"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    business_name: Mapped[str] = mapped_column(String(300))
    industry: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_normalized: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    email_normalized: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(500))
    website_domain: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(60), default="manual")
    status: Mapped[str] = mapped_column(String(40), default="discovered")
    score: Mapped[int | None] = mapped_column(Integer)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    consent_reference: Mapped[str | None] = mapped_column(String(255))
    custom_fields: Mapped[dict | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadContact(IdMixin, TimestampMixin, Base):
    __tablename__ = "lead_contacts"
    __table_args__ = (Index("ix_lead_contacts_org_lead", "organization_id", "lead_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))


class LeadNote(IdMixin, TimestampMixin, Base):
    __tablename__ = "lead_notes"
    __table_args__ = (Index("ix_lead_notes_org_lead", "organization_id", "lead_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)


class LeadTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "lead_tasks"
    __table_args__ = (
        Index("ix_lead_tasks_org_lead", "organization_id", "lead_id"),
        Index("ix_lead_tasks_org_due", "organization_id", "completed_at", "due_at"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class LeadActivity(IdMixin, Base):
    """Append-only timeline. The application never updates or deletes rows."""

    __tablename__ = "lead_activities"
    __table_args__ = (Index("ix_lead_activities_org_lead_created", "organization_id", "lead_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(60))
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
