import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

WEBSITE_STATUSES = ("unknown", "has_website", "no_website_listed", "reachable", "unreachable_retry")
_CRON = re.compile(r"^\s*(\S+\s+){4}\S+\s*$")


def check_cron(v: str | None) -> str | None:
    if v is not None and v.strip() and not _CRON.match(v):
        raise ValueError("schedule must be a 5-field cron expression, e.g. '0 6 * * 1'")
    return v.strip() if v and v.strip() else None


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SearchCriteria(BaseModel):
    source: str = Field(max_length=60)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    state: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    locality: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    radius_km: float | None = Field(default=None, gt=0, le=50)
    industry: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=200)
    website_status: str | None = None
    limit: int = Field(default=20, ge=1, le=20)

    @field_validator("website_status")
    @classmethod
    def _ws(cls, v):
        if v is not None and v not in WEBSITE_STATUSES:
            raise ValueError(f"website_status must be one of {WEBSITE_STATUSES}")
        return v


class SearchRequest(BaseModel):
    criteria: SearchCriteria
    saved_search_id: uuid.UUID | None = None


class SearchJobOut(_ORM):
    id: uuid.UUID
    source: str
    status: str
    criteria: dict
    results_count: int
    new_count: int
    duplicate_count: int
    cost_units: int
    error: str | None
    is_simulated: bool
    saved_search_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SourceStatus(BaseModel):
    source: str
    label: str
    status: str  # configured | not_configured | available
    simulated: bool
    detail: str | None = None
    supports_search: bool = True


class SourcesOut(BaseModel):
    sources: list[SourceStatus]
    daily_request_budget: int
    requests_used_today: int


class BusinessOut(_ORM):
    id: uuid.UUID
    name: str | None
    industry: str | None
    category: str | None
    address: str | None
    country: str | None
    state: str | None
    city: str | None
    locality: str | None
    postal_code: str | None
    lat: float | None
    lng: float | None
    phone: str | None
    email: str | None
    website: str | None
    google_place_id: str | None
    source: str
    is_simulated: bool
    verification_status: str
    website_status: str
    contact_permission_status: str
    lead_id: uuid.UUID | None
    collected_at: datetime
    last_verified_at: datetime | None
    created_at: datetime


class ProvenanceOut(_ORM):
    id: uuid.UUID
    field: str
    value: str | None
    source: str
    source_ref: str | None
    collected_at: datetime
    retention_until: datetime | None
    purged_at: datetime | None


class BusinessSourceOut(_ORM):
    id: uuid.UUID
    source: str
    source_ref: str | None
    is_simulated: bool
    search_job_id: uuid.UUID | None
    collected_at: datetime


class AuditOut(_ORM):
    id: uuid.UUID
    url: str
    final_url: str | None
    reachable: bool
    http_status: int | None
    ssl_valid: bool | None
    mobile_viewport: bool | None
    load_ms: int | None
    has_contact_info: bool | None
    has_cta: bool | None
    has_title: bool | None
    has_meta_description: bool | None
    broken_links_checked: int
    broken_links_found: int
    score: int | None
    findings: list | None
    error: str | None
    attempts: int
    created_at: datetime


class VerificationOut(_ORM):
    id: uuid.UUID
    method: str
    result: str
    details: dict | None
    created_at: datetime


class BusinessDetail(BaseModel):
    business: BusinessOut
    sources: list[BusinessSourceOut]
    provenance: list[ProvenanceOut]
    audits: list[AuditOut]
    verifications: list[VerificationOut]


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    criteria: SearchCriteria
    schedule: str | None = Field(default=None, max_length=120)

    @field_validator("schedule")
    @classmethod
    def _cron(cls, v):
        return check_cron(v)


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    criteria: SearchCriteria | None = None
    schedule: str | None = Field(default=None, max_length=120)

    @field_validator("schedule")
    @classmethod
    def _cron(cls, v):
        return check_cron(v)


class SavedSearchOut(_ORM):
    id: uuid.UUID
    name: str
    criteria: dict
    schedule: str | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConvertOut(BaseModel):
    business_id: uuid.UUID
    lead_id: uuid.UUID
