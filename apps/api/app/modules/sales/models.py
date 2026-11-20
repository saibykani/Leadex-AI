"""Sales module tables.

* plan_display, sales_settings, sales_booked_slots: global platform tables (no organization_id, no RLS). They hold
  only public marketing data / slot times — no personal data.
* sales_inquiries: tenant table (RLS) stored in the PLATFORM OWNER organization.
* sales_inquiries_inbox: fallback (no RLS, organization_id-less) used only when no platform-owner organization exists;
  readable only by superadmins. A setup warning is surfaced on /sales/settings.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

MONEY = Numeric(14, 2)


class PlanDisplay(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_display"
    plan_code: Mapped[str] = mapped_column(String(40), unique=True)
    price_monthly: Mapped[Decimal | None] = mapped_column(MONEY)
    price_annual: Mapped[Decimal | None] = mapped_column(MONEY)  # per month, billed annually
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    contact_sales: Mapped[bool] = mapped_column(Boolean, default=False)
    highlight: Mapped[bool] = mapped_column(Boolean, default=False)
    badge: Mapped[str | None] = mapped_column(String(40))
    tagline: Mapped[str | None] = mapped_column(String(200))
    bullets: Mapped[list | None] = mapped_column(JSON)


class SalesSettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "sales_settings"
    key: Mapped[str] = mapped_column(String(20), unique=True, default="default")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    weekdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])
    day_start: Mapped[str] = mapped_column(String(5), default="09:00")
    day_end: Mapped[str] = mapped_column(String(5), default="17:00")
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=15)
    min_notice_hours: Mapped[int] = mapped_column(Integer, default=12)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    booking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SalesBookedSlot(IdMixin, TimestampMixin, Base):
    __tablename__ = "sales_booked_slots"
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), unique=True)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reference: Mapped[str] = mapped_column(String(20))
    ics_token: Mapped[str] = mapped_column(String(64), unique=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)


class _InquiryBase:
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="new")
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320))
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(120))
    team_size: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(2))
    phone: Mapped[str | None] = mapped_column(String(40))
    interests: Mapped[list | None] = mapped_column(JSON)
    message: Mapped[str | None] = mapped_column(Text)
    preferred_time: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str | None] = mapped_column(String(64))
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_ack_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))


class SalesInquiry(_InquiryBase, IdMixin, TimestampMixin, Base):
    __tablename__ = "sales_inquiries"
    __table_args__ = (Index("ix_sales_inquiries_org_email_type", "organization_id", "email", "type", "created_at"),
                      Index("ix_sales_inquiries_org_status", "organization_id", "status"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class SalesInquiryInbox(_InquiryBase, IdMixin, TimestampMixin, Base):
    __tablename__ = "sales_inquiries_inbox"
    __table_args__ = (Index("ix_sales_inbox_email_type", "email", "type", "created_at"),)
