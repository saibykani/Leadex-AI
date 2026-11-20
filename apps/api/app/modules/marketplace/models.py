"""Marketplace: customer requirements, service providers, matching, referrals and commission ledger.

Money is always Numeric(14,2) plus an ISO-4217 currency code. Ledger-style tables
(referral_events, commission_transactions) are append-only: the application never updates or
deletes them and migration 0010 revokes UPDATE/DELETE from the runtime role.
"""
import uuid
from datetime import datetime
from decimal import Decimal

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

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

MONEY = Numeric(14, 2)


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)


class ServiceCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "service_categories"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_service_categories_org_slug"),)
    organization_id: Mapped[uuid.UUID] = _org()
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class MatchingSettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "marketplace_matching_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_matching_settings_org"),)
    organization_id: Mapped[uuid.UUID] = _org()
    weights: Mapped[dict] = mapped_column(JSON)


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_customers_org_email"),)
    organization_id: Mapped[uuid.UUID] = _org()
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))  # stored lower-case
    phone: Mapped[str | None] = mapped_column(String(40))


class CustomerRequirement(IdMixin, TimestampMixin, Base):
    __tablename__ = "customer_requirements"
    __table_args__ = (Index("ix_requirements_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = _org()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_categories.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    budget_min: Mapped[Decimal | None] = mapped_column(MONEY)
    budget_max: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    timeline: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict | None] = mapped_column(JSON)
    contact_permission: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_reference: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | matched | referred | closed


class ServiceProvider(IdMixin, TimestampMixin, Base):
    __tablename__ = "service_providers"
    organization_id: Mapped[uuid.UUID] = _org()
    business_name: Mapped[str] = mapped_column(String(300))
    legal_name: Mapped[str | None] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    service_areas: Mapped[list | None] = mapped_column(JSON)  # [{"city": "Pune", "country": "IN"}]
    experience_years: Mapped[int | None] = mapped_column(Integer)
    portfolio: Mapped[list | None] = mapped_column(JSON)
    credentials: Mapped[list | None] = mapped_column(JSON)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    availability: Mapped[str] = mapped_column(String(20), default="available")  # available|limited|unavailable
    price_min: Mapped[Decimal | None] = mapped_column(MONEY)
    price_max: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    pricing_notes: Mapped[str | None] = mapped_column(Text)
    portal_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ProviderCategory(IdMixin, Base):
    __tablename__ = "provider_categories"
    __table_args__ = (UniqueConstraint("provider_id", "category_id", name="uq_provider_category"),)
    organization_id: Mapped[uuid.UUID] = _org()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_categories.id", ondelete="CASCADE"))


class ProviderDocument(IdMixin, Base):
    __tablename__ = "provider_documents"
    organization_id: Mapped[uuid.UUID] = _org()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderVerification(IdMixin, Base):
    """History of verification decisions. Recorded by a human (manual) — never inferred."""

    __tablename__ = "provider_verifications"
    organization_id: Mapped[uuid.UUID] = _org()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(20))  # manual | registry
    registry_name: Mapped[str | None] = mapped_column(String(80))
    reference: Mapped[str | None] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[str | None] = mapped_column(Text)
    document_ids: Mapped[list | None] = mapped_column(JSON)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderMatch(IdMixin, Base):
    __tablename__ = "provider_matches"
    __table_args__ = (Index("ix_provider_matches_org_req", "organization_id", "requirement_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_requirements.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Referral(IdMixin, TimestampMixin, Base):
    __tablename__ = "referrals"
    __table_args__ = (Index("ix_referrals_org_status", "organization_id", "status"),
                      UniqueConstraint("requirement_id", "provider_id", name="uq_referral_req_provider"))
    organization_id: Mapped[uuid.UUID] = _org()
    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_requirements.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30))
    deal_value: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ReferralEvent(IdMixin, Base):
    """Append-only."""

    __tablename__ = "referral_events"
    __table_args__ = (Index("ix_referral_events_org_ref", "organization_id", "referral_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id", ondelete="CASCADE"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommissionAgreement(IdMixin, TimestampMixin, Base):
    __tablename__ = "commission_agreements"
    organization_id: Mapped[uuid.UUID] = _org()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_providers.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(20))  # fixed | percentage | negotiated
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    splits: Mapped[list | None] = mapped_column(JSON)  # [{"party": "...", "pct": "60"}]
    settlement_conditions: Mapped[dict | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class CommissionTransaction(IdMixin, Base):
    """Append-only commission ledger. Amounts are always positive; `kind` gives the meaning."""

    __tablename__ = "commission_transactions"
    __table_args__ = (Index("ix_commission_tx_org_ref", "organization_id", "referral_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id", ondelete="CASCADE"))
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commission_agreements.id",
                                                                       ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    reference: Mapped[str | None] = mapped_column(String(200))
    data: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommissionDispute(IdMixin, TimestampMixin, Base):
    __tablename__ = "commission_disputes"
    organization_id: Mapped[uuid.UUID] = _org()
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id", ondelete="CASCADE"))
    raised_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | resolved | rejected
    resolution: Mapped[str | None] = mapped_column(Text)
