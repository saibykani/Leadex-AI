import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.automation.events import emit_event
from app.modules.billing import service as billing
from app.modules.crm import service as crm
from app.modules.crm.models import Lead
from app.modules.discovery import service as svc
from app.modules.discovery.adapters import ADAPTERS, CsvImportAdapter
from app.modules.discovery.adapters.csv_import import MAX_BYTES
from app.modules.discovery.config import get_discovery_settings
from app.modules.discovery.models import (
    Business,
    BusinessSource,
    BusinessSourceField,
    BusinessVerification,
    SavedSearch,
    SearchJob,
    WebsiteAudit,
)
from app.modules.discovery.schemas import (
    WEBSITE_STATUSES,
    AuditOut,
    BusinessDetail,
    BusinessOut,
    ConvertOut,
    SavedSearchIn,
    SavedSearchOut,
    SavedSearchUpdate,
    SearchJobOut,
    SearchRequest,
    SourcesOut,
    SourceStatus,
)
from app.modules.discovery.website_audit import run_audit
from app.modules.identity.schemas import Page

router = APIRouter(tags=["discovery"])

READ = require_permission("businesses:read")
WRITE = require_permission("businesses:write")
RUN = require_permission("discovery:run")


def _audit(db, ctx: TenantContext, action: str, entity_type: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=entity_type,
          entity_id=entity_id, data=data, request=request)


# ---------------------------------------------------------------- sources / search / jobs
@router.get("/discovery/sources", response_model=SourcesOut)
def sources(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return SourcesOut(
        sources=[SourceStatus(**a.status(), supports_search=a.supports_search) for a in ADAPTERS.values()],
        daily_request_budget=get_discovery_settings().daily_request_budget,
        requests_used_today=svc.requests_used_today(db, ctx.organization_id),
    )


@router.post("/discovery/search", response_model=SearchJobOut, status_code=201)
def search(body: SearchRequest, request: Request, ctx: TenantContext = Depends(RUN), db: Session = Depends(get_db)):
    saved = None
    if body.saved_search_id:
        saved = _saved(db, ctx, body.saved_search_id)
    criteria = body.criteria.model_dump(exclude_none=True)
    if criteria.get("country"):
        criteria["country"] = criteria["country"].upper()
    # Plan limit (searches/month) and, for billable providers, the hard budget stop before any external call.
    billing.enforce_limit(db, ctx.organization_id, "searches")
    unit_cost = get_discovery_settings().google_unit_cost
    if criteria.get("source") not in (None, "simulated"):
        billing.check_budget(db, ctx.organization_id, unit_cost)
    job = svc.run_search(db, ctx, criteria, saved.id if saved else None)
    if job.status != "failed" or job.cost_units:
        cost = 0 if job.source == "simulated" else round(float(job.cost_units or 0) * unit_cost, 4)
        billing.record_usage(db, ctx.organization_id, "searches", 1, cost,
                             meta={"search_job_id": str(job.id), "source": job.source})
    if saved:
        saved.last_run_at = utcnow()
    _audit(db, ctx, "discovery.search", "search_job", job.id, request,
           {"source": job.source, "status": job.status, "results": job.results_count})
    db.commit()
    return job


@router.post("/discovery/import", response_model=SearchJobOut, status_code=201)
async def import_csv(request: Request, file: UploadFile = File(...), ctx: TenantContext = Depends(RUN),
                     db: Session = Depends(get_db)):
    data = await file.read(MAX_BYTES + 1)
    from app.core.scanning import scan_bytes

    scan_bytes(data, file.filename or "import.csv")
    adapter: CsvImportAdapter = ADAPTERS["customer_import"]  # type: ignore[assignment]
    job = svc.create_job(db, ctx, adapter.name, {"source": adapter.name, "filename": file.filename})
    job = svc.execute_job(db, ctx, job, lambda: adapter.parse(data, file.filename))
    _audit(db, ctx, "discovery.import", "search_job", job.id, request,
           {"filename": file.filename, "status": job.status, "results": job.results_count})
    db.commit()
    return job


@router.get("/discovery/jobs", response_model=Page[SearchJobOut])
def list_jobs(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
              page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(SearchJob).where(SearchJob.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(SearchJob.created_at.desc(), SearchJob.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[SearchJobOut](items=[SearchJobOut.model_validate(r) for r in rows], total=total, page=page,
                              page_size=page_size)


@router.get("/discovery/jobs/{job_id}", response_model=SearchJobOut)
def get_job(job_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    job = db.scalar(select(SearchJob).where(SearchJob.id == job_id, SearchJob.organization_id == ctx.organization_id))
    if job is None:
        raise AppError(404, "not_found", "Search job not found")
    return job


# ---------------------------------------------------------------- export
EXPORT_COLUMNS = ("id", "name", "industry", "category", "address", "country", "state", "city", "locality",
                  "postal_code", "lat", "lng", "phone", "email", "website", "google_place_id", "source",
                  "is_simulated", "website_status", "verification_status")


@router.get("/discovery/export")
def export_csv(request: Request, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
               website_status: str | None = None, industry: str | None = None, city: str | None = None,
               q: str | None = Query(None, max_length=200), source: str | None = None):
    """CSV export. Values backed only by Google Places content are blanked: Google Maps Platform terms prohibit
    exporting or redistributing Places content outside the service (and it may only be cached temporarily).
    `google_place_id` is exempt from those restrictions and is exported so the customer can re-fetch details."""
    rows = db.scalars(_business_query(ctx, website_status, industry, city, q, source)
                      .order_by(Business.created_at, Business.id).limit(50_000)).all()
    blocked = svc.export_filter(db, ctx.organization_id, list(rows))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLUMNS)
    for b in rows:
        w.writerow(["" if c in blocked.get(b.id, ()) else _csv_safe(getattr(b, c)) for c in EXPORT_COLUMNS])
    _audit(db, ctx, "discovery.export", "business", None, request, {"rows": len(rows)})
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="businesses.csv"'})


def _csv_safe(v):
    if v is None:
        return ""
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s  # CSV formula injection guard


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- saved searches
def _saved(db: Session, ctx: TenantContext, sid: uuid.UUID) -> SavedSearch:
    s = db.scalar(select(SavedSearch).where(SavedSearch.id == sid, SavedSearch.organization_id == ctx.organization_id))
    if s is None:
        raise AppError(404, "not_found", "Saved search not found")
    return s


@router.get("/discovery/saved-searches", response_model=list[SavedSearchOut])
def list_saved(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(SavedSearch).where(SavedSearch.organization_id == ctx.organization_id)
                      .order_by(SavedSearch.created_at.desc())).all()


@router.post("/discovery/saved-searches", response_model=SavedSearchOut, status_code=201)
def create_saved(body: SavedSearchIn, request: Request, ctx: TenantContext = Depends(RUN),
                 db: Session = Depends(get_db)):
    s = SavedSearch(organization_id=ctx.organization_id, name=body.name.strip(),
                    criteria=body.criteria.model_dump(exclude_none=True), schedule=body.schedule,
                    created_by_user_id=ctx.user.id)
    db.add(s)
    db.flush()
    _audit(db, ctx, "saved_search.create", "saved_search", s.id, request, {"name": s.name})
    db.commit()
    return s


@router.get("/discovery/saved-searches/{sid}", response_model=SavedSearchOut)
def get_saved(sid: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _saved(db, ctx, sid)


@router.patch("/discovery/saved-searches/{sid}", response_model=SavedSearchOut)
def update_saved(sid: uuid.UUID, body: SavedSearchUpdate, request: Request, ctx: TenantContext = Depends(RUN),
                 db: Session = Depends(get_db)):
    s = _saved(db, ctx, sid)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        s.name = changes["name"].strip()
    if body.criteria is not None:
        s.criteria = body.criteria.model_dump(exclude_none=True)
    if "schedule" in changes:
        s.schedule = body.schedule
    _audit(db, ctx, "saved_search.update", "saved_search", s.id, request, {"fields": sorted(changes)})
    db.commit()
    db.refresh(s)
    return s


@router.delete("/discovery/saved-searches/{sid}", status_code=204)
def delete_saved(sid: uuid.UUID, request: Request, ctx: TenantContext = Depends(RUN), db: Session = Depends(get_db)):
    s = _saved(db, ctx, sid)
    db.delete(s)
    _audit(db, ctx, "saved_search.delete", "saved_search", sid, request)
    db.commit()


# ---------------------------------------------------------------- businesses
def _business_query(ctx, website_status, industry, city, q, source):
    base = select(Business).where(Business.organization_id == ctx.organization_id, Business.deleted_at.is_(None))
    if website_status:
        if website_status not in WEBSITE_STATUSES:
            raise AppError(422, "invalid_filter", f"website_status must be one of {list(WEBSITE_STATUSES)}")
        base = base.where(Business.website_status == website_status)
    if industry:
        base = base.where(func.lower(Business.industry) == industry.strip().lower())
    if city:
        base = base.where(func.lower(Business.city) == city.strip().lower())
    if source:
        base = base.where(Business.source == source)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        base = base.where(or_(func.lower(Business.name).like(like), func.lower(Business.city).like(like),
                              Business.website_domain.like(like), func.lower(Business.category).like(like)))
    return base


@router.get("/businesses", response_model=Page[BusinessOut])
def list_businesses(
    ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    website_status: str | None = None, industry: str | None = None, city: str | None = None,
    q: str | None = Query(None, max_length=200), source: str | None = None, job_id: uuid.UUID | None = None,
):
    base = _business_query(ctx, website_status, industry, city, q, source)
    if job_id:
        base = base.where(Business.id.in_(select(BusinessSource.business_id).where(
            BusinessSource.search_job_id == job_id, BusinessSource.organization_id == ctx.organization_id)))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Business.created_at.desc(), Business.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[BusinessOut](items=[BusinessOut.model_validate(r) for r in rows], total=total, page=page,
                             page_size=page_size)


@router.get("/businesses/{business_id}", response_model=BusinessDetail)
def get_business(business_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    b = svc.get_business(db, ctx, business_id)
    org = ctx.organization_id

    def q(model, order):
        return db.scalars(select(model).where(model.organization_id == org, model.business_id == b.id)
                          .order_by(order)).all()

    return BusinessDetail(
        business=BusinessOut.model_validate(b),
        sources=q(BusinessSource, BusinessSource.collected_at.desc()),
        provenance=q(BusinessSourceField, BusinessSourceField.field),
        audits=q(WebsiteAudit, WebsiteAudit.created_at.desc()),
        verifications=q(BusinessVerification, BusinessVerification.created_at.desc()),
    )


@router.post("/businesses/{business_id}/audit", response_model=AuditOut, status_code=201)
def audit_website(business_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    b = svc.get_business(db, ctx, business_id)
    if not b.website:
        raise AppError(422, "no_website", "This business has no website on record to audit")
    if b.is_simulated:
        raise AppError(422, "simulated_business", "Simulated businesses have no real website to audit")
    r = run_audit(b.website)
    a = WebsiteAudit(organization_id=ctx.organization_id, business_id=b.id, url=r.url, final_url=r.final_url,
                     reachable=r.reachable, http_status=r.http_status, ssl_valid=r.ssl_valid,
                     mobile_viewport=r.mobile_viewport, load_ms=r.load_ms, has_contact_info=r.has_contact_info,
                     has_cta=r.has_cta, has_title=r.has_title, has_meta_description=r.has_meta_description,
                     broken_links_checked=r.broken_links_checked, broken_links_found=r.broken_links_found,
                     score=r.score, findings=r.findings, error=r.error, attempts=r.attempts)
    db.add(a)
    if r.network_failure:
        b.website_status = "unreachable_retry"
        result = "unreachable_retry"
    elif r.score is None:
        result = "refused"
    else:
        b.website_status = "reachable" if r.reachable else "has_website"
        result = "reachable" if r.reachable else f"http_{r.http_status}"
        b.last_verified_at = utcnow()
    db.add(BusinessVerification(organization_id=ctx.organization_id, business_id=b.id, method="website_audit",
                                result=result, details={"score": r.score, "http_status": r.http_status},
                                actor_user_id=ctx.user.id))
    db.flush()
    _audit(db, ctx, "business.audit", "business", b.id, request, {"score": r.score, "result": result})
    db.commit()
    return a


@router.post("/businesses/{business_id}/convert-to-lead", response_model=ConvertOut, status_code=201)
def convert_to_lead(business_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    ctx.require("leads:write")
    b = svc.get_business(db, ctx, business_id)
    if b.lead_id is not None:
        existing = db.get(Lead, b.lead_id)
        if existing is not None and existing.deleted_at is None:
            raise AppError(409, "already_converted", "This business has already been converted to a lead",
                           {"existing_lead_id": str(b.lead_id)})
    billing.enforce_limit(db, ctx.organization_id, "leads")
    if not b.name:
        raise AppError(422, "missing_name", "Business name is unavailable (expired provider data); refresh first")
    lead = Lead(organization_id=ctx.organization_id, business_name=b.name, industry=b.industry,
                country=b.country, city=b.city, phone=b.phone, email=b.email, website=b.website,
                source="simulated" if b.is_simulated else f"discovery:{b.source}", status="discovered",
                custom_fields={"business_id": str(b.id), "is_simulated": b.is_simulated,
                               "google_place_id": b.google_place_id})
    crm.apply_contact_fields(lead)
    crm.check_duplicates(db, lead)
    db.add(lead)
    db.flush()
    b.lead_id = lead.id
    crm.record_activity(db, ctx, lead, "lead.created", {"source": lead.source, "business_id": str(b.id)})
    _audit(db, ctx, "business.convert_to_lead", "business", b.id, request, {"lead_id": str(lead.id)})
    emit_event(db, ctx.organization_id, "lead_created", {"lead_id": str(lead.id)}, event_id=str(lead.id))
    db.commit()
    return ConvertOut(business_id=b.id, lead_id=lead.id)
