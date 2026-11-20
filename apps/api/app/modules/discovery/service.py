"""Discovery domain logic: job execution, budget, de-duplication, provenance, retention purge."""
import json
import re
import uuid
from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.automation.events import emit_event
from app.modules.crm.service import normalize_phone, website_domain
from app.modules.discovery.adapters import ADAPTERS, AdapterError, RawBusiness, SearchResult
from app.modules.discovery.config import get_discovery_settings
from app.modules.discovery.models import (
    Business,
    BusinessSource,
    BusinessSourceField,
    SearchJob,
    UsageRecord,
)

BILLABLE_RESOURCES = ("google_places_request",)
TRACKED_FIELDS = ("name", "industry", "category", "address", "country", "state", "city", "locality",
                  "postal_code", "lat", "lng", "phone", "email", "website")
MAX_LEN = {"name": 300, "industry": 120, "category": 120, "address": 500, "country": 2, "state": 120,
           "city": 120, "locality": 120, "postal_code": 20, "phone": 40, "email": 320, "website": 500}


def name_city_key(name: str | None, city: str | None) -> str | None:
    if not name:
        return None
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()  # noqa: E731
    return f"{norm(name)}|{norm(city)}"[:450]


def get_business(db: Session, ctx: TenantContext, business_id: uuid.UUID) -> Business:
    b = db.scalar(select(Business).where(Business.id == business_id, Business.organization_id == ctx.organization_id,
                                         Business.deleted_at.is_(None)))
    if b is None:
        raise AppError(404, "not_found", "Business not found")
    return b


def _day_start() -> datetime:
    now = utcnow()
    return datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)


def requests_used_today(db: Session, org_id: uuid.UUID) -> int:
    return db.scalar(select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
        UsageRecord.organization_id == org_id, UsageRecord.resource.in_(BILLABLE_RESOURCES),
        UsageRecord.created_at >= _day_start())) or 0


def check_budget(db: Session, org_id: uuid.UUID) -> None:
    budget = get_discovery_settings().daily_request_budget
    used = requests_used_today(db, org_id)
    if used >= budget:
        raise AppError(429, "discovery_budget_exceeded",
                       f"Daily discovery request budget reached ({used}/{budget}). Try again tomorrow.",
                       {"used": used, "budget": budget})


def _find_duplicate(db: Session, org_id: uuid.UUID, raw: RawBusiness, phone_n, domain, nck) -> Business | None:
    base = select(Business).where(Business.organization_id == org_id, Business.deleted_at.is_(None))
    for cond in (
        Business.google_place_id == raw.place_id if raw.place_id else None,
        Business.phone_normalized == phone_n if phone_n else None,
        Business.website_domain == domain if domain else None,
        Business.name_city_key == nck if nck else None,
    ):
        if cond is not None:
            hit = db.scalars(base.where(cond).limit(1)).first()
            if hit is not None:
                return hit
    return None


def _clip(k: str, v):
    return v[:MAX_LEN[k]] if isinstance(v, str) and k in MAX_LEN else v


def ingest(db: Session, org_id: uuid.UUID, job: SearchJob, raw: RawBusiness, source: str,
           simulated: bool) -> tuple[Business, bool]:
    """Insert or merge one record. Returns (business, created). Existing values are never overwritten;
    only empty fields are filled, and every contributed value is recorded as provenance."""
    f = {k: _clip(k, v) for k, v in raw.fields.items() if k in TRACKED_FIELDS}
    phone_n = normalize_phone(f.get("phone"))
    domain = website_domain(f.get("website"))
    nck = name_city_key(f.get("name"), f.get("city"))
    biz = _find_duplicate(db, org_id, raw, phone_n, domain, nck)
    created = biz is None
    now = utcnow()
    if created:
        biz = Business(organization_id=org_id, source=source, is_simulated=simulated, collected_at=now,
                       verification_status="unverified", website_status="unknown")
        db.add(biz)
    elif biz.is_simulated != simulated:
        # never merge simulated data into real records (or vice versa): keep them separate
        biz = Business(organization_id=org_id, source=source, is_simulated=simulated, collected_at=now,
                       verification_status="unverified", website_status="unknown")
        db.add(biz)
        created = True
    for k, v in f.items():
        if getattr(biz, k) in (None, ""):
            setattr(biz, k, v)
    if raw.place_id and not biz.google_place_id:
        biz.google_place_id = raw.place_id
    biz.phone_normalized = normalize_phone(biz.phone)
    biz.website_domain = website_domain(biz.website)
    biz.name_city_key = name_city_key(biz.name, biz.city)
    if biz.website and biz.website_status in ("unknown", "no_website_listed"):
        biz.website_status = "has_website"
    elif not biz.website and raw.website_known_absent and biz.website_status == "unknown":
        biz.website_status = "no_website_listed"
    db.flush()
    db.add(BusinessSource(organization_id=org_id, business_id=biz.id, search_job_id=job.id, source=source,
                          source_ref=raw.source_ref, is_simulated=simulated, collected_at=now))
    for k, v in f.items():
        db.add(BusinessSourceField(organization_id=org_id, business_id=biz.id, field=k, value=str(v),
                                   source=source, source_ref=raw.source_ref, collected_at=now,
                                   retention_until=raw.retention.get(k)))
    if raw.place_id:
        db.add(BusinessSourceField(organization_id=org_id, business_id=biz.id, field="google_place_id",
                                   value=raw.place_id, source=source, source_ref=raw.source_ref, collected_at=now,
                                   retention_until=None))
    _store_photo_refs(db, org_id, biz, raw, source, now)
    return biz, created


def _store_photo_refs(db: Session, org_id: uuid.UUID, biz: Business, raw: RawBusiness, source: str, now) -> None:
    """Google photo references -> provenance rows (field='photo', JSON value) with the same retention as other
    Places content; the purge job nulls them on expiry. No image bytes are stored."""
    photos = raw.fields.get("photos") or []
    if not photos:
        return
    known = set(db.scalars(select(BusinessSourceField.value).where(
        BusinessSourceField.business_id == biz.id, BusinessSourceField.field == "photo",
        BusinessSourceField.purged_at.is_(None))))
    known_names = {json.loads(v).get("name") for v in known if v}
    for ph in photos:
        if ph.get("name") in known_names:
            continue
        db.add(BusinessSourceField(organization_id=org_id, business_id=biz.id, field="photo",
                                   value=json.dumps(ph), source=source, source_ref=raw.source_ref,
                                   collected_at=now, retention_until=raw.retention.get("photos")))


def _matches(biz: Business, website_status: str | None) -> bool:
    return website_status is None or biz.website_status == website_status


def create_job(db: Session, ctx: TenantContext, source: str, criteria: dict,
               saved_search_id: uuid.UUID | None = None) -> SearchJob:
    job = SearchJob(organization_id=ctx.organization_id, source=source, criteria=criteria, status="queued",
                    is_simulated=source == "simulated", created_by_user_id=ctx.user.id,
                    saved_search_id=saved_search_id)
    db.add(job)
    db.commit()
    return job


def record_usage(db: Session, org_id: uuid.UUID, job: SearchJob, result: SearchResult) -> None:
    if result.requests_made and result.usage_resource:
        db.add(UsageRecord(organization_id=org_id, resource=result.usage_resource, quantity=result.requests_made,
                           unit_cost=result.unit_cost, search_job_id=job.id))
        job.cost_units += result.requests_made


def execute_job(db: Session, ctx: TenantContext, job: SearchJob, run) -> SearchJob:
    """Run synchronously. TODO(phase-3b): move to a Celery task; this function is the task body."""
    job.status, job.started_at = "running", utcnow()
    db.commit()
    try:
        result: SearchResult = run()
    except AdapterError as e:
        partial = getattr(e, "result", None)
        if partial is not None:
            record_usage(db, ctx.organization_id, job, partial)
        job.status, job.error, job.finished_at = "failed", str(e), utcnow()
        db.commit()
        return job
    record_usage(db, ctx.organization_id, job, result)
    simulated = job.source == "simulated"
    ws = (job.criteria or {}).get("website_status")
    seen: set[uuid.UUID] = set()
    for raw in result.records:
        biz, created = ingest(db, ctx.organization_id, job, raw, job.source, simulated)
        if biz.id in seen:  # duplicate within the same batch
            job.duplicate_count += 1
            continue
        if not _matches(biz, ws):
            continue
        seen.add(biz.id)
        job.results_count += 1
        if created:
            job.new_count += 1
            emit_event(db, ctx.organization_id, "business_discovered",
                       {"business_id": str(biz.id), "search_job_id": str(job.id), "source": job.source},
                       event_id=str(biz.id))
        else:
            job.duplicate_count += 1
    job.status, job.finished_at = "completed", utcnow()
    db.commit()
    return job


def run_search(db: Session, ctx: TenantContext, criteria: dict, saved_search_id=None) -> SearchJob:
    source = criteria.get("source")
    adapter = ADAPTERS.get(source)
    if adapter is None or not adapter.supports_search:
        raise AppError(422, "invalid_source", f"Unknown or non-searchable source '{source}'",
                       {"searchable": [n for n, a in ADAPTERS.items() if a.supports_search]})
    st = adapter.status()
    if st["status"] == "not_configured":
        raise AppError(409, "source_not_configured", st.get("detail") or f"{source} is not configured")
    if not adapter.simulated:
        check_budget(db, ctx.organization_id)
    job = create_job(db, ctx, source, criteria, saved_search_id)
    return execute_job(db, ctx, job, lambda: adapter.search(criteria))


def purge_expired_provider_fields(db: Session, now: datetime | None = None) -> int:
    """Null out provider content whose retention has passed (Google Places ToS). Keeps place_id.
    Intended to run daily from the scheduler. Returns number of provenance rows purged."""
    now = now or utcnow()
    rows = db.scalars(select(BusinessSourceField).where(BusinessSourceField.retention_until.is_not(None),
                                                        BusinessSourceField.retention_until < now,
                                                        BusinessSourceField.purged_at.is_(None))).all()
    for row in rows:
        biz = db.get(Business, row.business_id)
        if biz is not None and row.field in TRACKED_FIELDS:
            # Only clear the business column if no other un-purged, non-expiring source supplied the same value
            other = db.scalar(select(BusinessSourceField.id).where(
                BusinessSourceField.business_id == biz.id, BusinessSourceField.field == row.field,
                BusinessSourceField.id != row.id, BusinessSourceField.retention_until.is_(None),
                BusinessSourceField.purged_at.is_(None)).limit(1))
            if other is None and getattr(biz, row.field) is not None and str(getattr(biz, row.field)) == row.value:
                setattr(biz, row.field, None)
                biz.phone_normalized = normalize_phone(biz.phone)
                biz.website_domain = website_domain(biz.website)
                biz.name_city_key = name_city_key(biz.name, biz.city)
        row.value, row.purged_at = None, now
    db.commit()
    return len(rows)


def export_filter(db: Session, org_id: uuid.UUID, businesses: list[Business]) -> dict[uuid.UUID, set[str]]:
    """Per business: the fields that must be blanked in exports because their current value is backed only by
    retention-limited provider content (Google Places). Maps Platform terms forbid exporting/redistributing
    Places content; place_id is exempt. A value also supplied by a non-restricted source (e.g. the customer's
    own CSV) remains exportable."""
    if not businesses:
        return {}
    rows = db.execute(select(BusinessSourceField.business_id, BusinessSourceField.field, BusinessSourceField.value,
                             BusinessSourceField.retention_until).where(
        BusinessSourceField.organization_id == org_id,
        BusinessSourceField.business_id.in_([b.id for b in businesses]))).all()
    free: dict[tuple, set] = {}
    restricted: dict[tuple, set] = {}
    for bid, fld, val, ret in rows:
        (free if ret is None else restricted).setdefault((bid, fld), set()).add(val)
    out: dict[uuid.UUID, set[str]] = {}
    for b in businesses:
        blocked = set()
        for fld in TRACKED_FIELDS:
            cur = getattr(b, fld)
            if cur is None:
                continue
            if (b.id, fld) in restricted and str(cur) not in free.get((b.id, fld), set()):
                blocked.add(fld)
        out[b.id] = blocked
    return out


def purge_expired_provider_fields_all_tenants(now: datetime | None = None) -> int:
    """Scheduler entry point: runs the purge once per organization inside a tenant-bound session,
    so row-level security is respected (the app role cannot see other tenants' rows)."""
    from sqlalchemy import select as _select

    from app.core.db import SessionLocal, tenant_session
    from app.modules.identity.models import Organization

    with SessionLocal() as db:
        org_ids = list(db.scalars(_select(Organization.id)))
    total = 0
    for org_id in org_ids:
        with tenant_session(org_id) as db:
            total += purge_expired_provider_fields(db, now=now)
            db.commit()
    return total
