"""Discovery data model.

Provenance is field-level (BusinessSourceField). Google Places derived values carry `retention_until`
(Maps Platform terms allow caching content only temporarily; `place_id` may be kept indefinitely).
`usage_records` is append-only metering; billing may reuse it later.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org():
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


def _biz():
    return mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))


class Business(IdMixin, TimestampMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint("organization_id", "google_place_id", name="uq_businesses_org_place"),
        Index("ix_businesses_org_phone", "organization_id", "phone_normalized"),
        Index("ix_businesses_org_domain", "organization_id", "website_domain"),
        Index("ix_businesses_org_namecity", "organization_id", "name_city_key"),
        Index("ix_businesses_org_wstatus", "organization_id", "website_status"),
        Index("ix_businesses_org_created", "organization_id", "created_at"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str | None] = mapped_column(String(300))  # nullable: Google-derived names are purged on expiry
    industry: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(2))
    state: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    locality: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_normalized: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(500))
    website_domain: Mapped[str | None] = mapped_column(String(255))
    name_city_key: Mapped[str | None] = mapped_column(String(450))
    google_place_id: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(60))  # first source that produced the record
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    # unknown | has_website | no_website_listed | reachable | unreachable_retry
    website_status: Mapped[str] = mapped_column(String(30), default="unknown")
    contact_permission_status: Mapped[str] = mapped_column(String(30), default="unknown")
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessSource(IdMixin, Base):
    __tablename__ = "business_sources"
    __table_args__ = (Index("ix_business_sources_org_biz", "organization_id", "business_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = _biz()
    search_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_jobs.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(60))
    source_ref: Mapped[str | None] = mapped_column(String(300))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessSourceField(IdMixin, Base):
    __tablename__ = "business_source_fields"
    __table_args__ = (Index("ix_bsf_org_biz", "organization_id", "business_id"),
                      Index("ix_bsf_retention", "retention_until"))
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = _biz()
    field: Mapped[str] = mapped_column(String(60))
    value: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(60))
    source_ref: Mapped[str | None] = mapped_column(String(300))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessVerification(IdMixin, Base):
    __tablename__ = "business_verifications"
    __table_args__ = (Index("ix_bver_org_biz", "organization_id", "business_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = _biz()
    method: Mapped[str] = mapped_column(String(60))  # website_audit | manual | ...
    result: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict | None] = mapped_column(JSON)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebsiteAudit(IdMixin, Base):
    __tablename__ = "website_audits"
    __table_args__ = (Index("ix_waudit_org_biz_created", "organization_id", "business_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    business_id: Mapped[uuid.UUID] = _biz()
    url: Mapped[str] = mapped_column(String(500))
    final_url: Mapped[str | None] = mapped_column(String(1000))
    reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    ssl_valid: Mapped[bool | None] = mapped_column(Boolean)
    mobile_viewport: Mapped[bool | None] = mapped_column(Boolean)
    load_ms: Mapped[int | None] = mapped_column(Integer)
    has_contact_info: Mapped[bool | None] = mapped_column(Boolean)
    has_cta: Mapped[bool | None] = mapped_column(Boolean)
    has_title: Mapped[bool | None] = mapped_column(Boolean)
    has_meta_description: Mapped[bool | None] = mapped_column(Boolean)
    broken_links_checked: Mapped[int] = mapped_column(Integer, default=0)
    broken_links_found: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int | None] = mapped_column(Integer)
    findings: Mapped[list | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedSearch(IdMixin, TimestampMixin, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (Index("ix_saved_searches_org", "organization_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(200))
    criteria: Mapped[dict] = mapped_column(JSON)
    schedule: Mapped[str | None] = mapped_column(String(120))  # cron text; executed by the scheduler (not yet)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "search_jobs"
    __table_args__ = (Index("ix_search_jobs_org_created", "organization_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    saved_search_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("saved_searches.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed
    criteria: Mapped[dict] = mapped_column(JSON)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_units: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageRecord(IdMixin, Base):
    """Append-only metering (UPDATE/DELETE revoked from the app role on PostgreSQL). Billing may reuse it."""

    __tablename__ = "usage_records"
    __table_args__ = (Index("ix_usage_org_resource_created", "organization_id", "resource", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    resource: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 6))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # FK added once campaigns exist
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    search_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_jobs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
