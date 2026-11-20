"""Sales: public pricing, inbound contact / demo forms, demo slot booking, internal inquiry inbox.

Tenancy: inbound inquiries are stored in the PLATFORM OWNER organization (organizations.is_platform_owner). Public
routes resolve that organization through the narrow SECURITY DEFINER function `sales_platform_owner_org()`
(migration 0017) and then bind RLS to it. If no platform owner exists, inquiries go to the non-RLS
`sales_inquiries_inbox` (superadmin-only, no CRM lead) and /sales/settings reports a setup warning.

Consent: an inbound request records an email consent row with basis 'inbound_request', scoped (evidence text) to
answering that inquiry. lead.consent_reference - which the outreach gate requires before any automated outreach -
is set ONLY when the visitor ticked the separate marketing opt-in.

Calendar: bookings are local only (slot table + CRM task + .ics download). Google / Microsoft calendar sync is
future work.
"""
import secrets
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.tenancy import TenantContext, audit, get_tenant
from app.modules.administration.router import notify
from app.modules.billing import service as billing
from app.modules.billing.models import Plan
from app.modules.compliance.models import ConsentRecord
from app.modules.crm.models import Lead, LeadActivity, LeadContact, LeadNote, LeadTask
from app.modules.crm.service import ADMIN_ROLES, apply_contact_fields, check_duplicates, ensure_member
from app.modules.identity.models import Organization, OrganizationMembership
from app.modules.identity.schemas import Page
from app.modules.sales.models import PlanDisplay, SalesBookedSlot, SalesInquiry, SalesInquiryInbox, SalesSettings
from app.modules.sales.schemas import (
    BookIn,
    ContactIn,
    ContactOut,
    InquiryOut,
    InquiryPatch,
    PlanDisplayBulk,
    SettingsIn,
)

router = APIRouter(tags=["sales"])
public_router = APIRouter(tags=["sales-public"])
extra_routers = [public_router]

FORM_LIMIT = 5  # submissions / minute / IP
READ_LIMIT = 60
MAX_BODY = 16 * 1024
MIN_FILL_MS = 3000
MAX_FORM_AGE_MS = 24 * 3600 * 1000
DEDUPE_WINDOW = timedelta(minutes=10)
RESOURCE_LABELS = {
    "users": "team members", "leads": "leads", "searches": "discovery searches / month",
    "ai_tokens": "AI actions / month", "voice_minutes": "voice minutes / month", "email_accounts": "email inboxes",
    "websites": "websites", "workflows": "workflows", "agents": "AI agents", "storage_mb": "MB storage",
}


# ---------------------------------------------------------------- helpers
def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _limit(request: Request, bucket: str, n: int) -> None:
    if not limiter.hit(f"sales:{bucket}:{_ip(request)}", n):
        raise AppError(429, "rate_limited", "Too many requests, try again later")


def platform_owner_org(db: Session) -> uuid.UUID | None:
    if db.get_bind().dialect.name == "postgresql":
        return db.scalar(text("SELECT sales_platform_owner_org()"))
    return db.scalar(select(Organization.id).where(Organization.is_platform_owner.is_(True),
                                                   Organization.deleted_at.is_(None))
                     .order_by(Organization.created_at).limit(1))


def sales_admin(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)) -> TenantContext:
    """Superadmins, or Owners/Admins of the platform-owner organization."""
    owner_admin = ctx.role_name in ADMIN_ROLES and platform_owner_org(db) == ctx.organization_id
    if not (ctx.user.is_superadmin or owner_admin):
        raise AppError(403, "forbidden", "Only platform-owner admins can manage sales settings")
    return ctx


def inbox_admin(ctx: TenantContext = Depends(sales_admin), db: Session = Depends(get_db)) -> TenantContext:
    if platform_owner_org(db) != ctx.organization_id:
        raise AppError(403, "forbidden", "Switch to the platform-owner organization to see sales inquiries")
    return ctx


def _settings(db: Session) -> SalesSettings:
    s = db.scalar(select(SalesSettings).where(SalesSettings.key == "default"))
    if s is None:
        s = SalesSettings(key="default", timezone="UTC", weekdays=[0, 1, 2, 3, 4], day_start="09:00",
                          day_end="17:00", slot_minutes=30, buffer_minutes=15, min_notice_hours=12,
                          horizon_days=30, booking_enabled=True)
        db.add(s)
        db.flush()
    return s


def _settings_dict(s: SalesSettings) -> dict:
    return {k: getattr(s, k) for k in ("timezone", "weekdays", "day_start", "day_end", "slot_minutes",
                                       "buffer_minutes", "min_notice_hours", "horizon_days", "booking_enabled")}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _reference() -> str:
    return "LX-" + secrets.token_hex(4).upper()


def _guard_form(request: Request, body: ContactIn) -> None:
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        raise AppError(413, "payload_too_large", "Submission is too large")
    if body.website:
        raise AppError(400, "spam_rejected", "Submission rejected")
    age = int(time.time() * 1000) - body.form_started_at
    if age < MIN_FILL_MS:
        raise AppError(422, "too_fast", "Please take a moment to complete the form and try again")
    if age > MAX_FORM_AGE_MS:
        raise AppError(422, "form_expired", "This form has expired; please reload the page")
    if not body.privacy_ack:
        raise AppError(422, "privacy_ack_required", "Please acknowledge the privacy notice")


def _fields(body: ContactIn, request: Request) -> dict:
    return dict(type=body.type, name=body.name, email=str(body.email).lower(), company=body.company,
                role=body.role, team_size=body.team_size, country=body.country.upper() if body.country else None,
                phone=body.phone, interests=body.interests, message=body.message, preferred_time=body.preferred_time,
                timezone=body.timezone, marketing_consent=body.marketing_consent, privacy_ack_at=utcnow(),
                ip_address=_ip(request))


def _recent(db: Session, model, email: str, type_: str, org: uuid.UUID | None):
    q = select(model).where(model.email == email, model.type == type_,
                            model.created_at >= utcnow() - DEDUPE_WINDOW)
    if org is not None:
        q = q.where(model.organization_id == org)
    return db.scalars(q.order_by(model.created_at.desc()).limit(1)).first()


def _admins(db: Session, org: uuid.UUID) -> list[OrganizationMembership]:
    ms = db.scalars(select(OrganizationMembership).where(OrganizationMembership.organization_id == org,
                                                         OrganizationMembership.status == "active")).all()
    return [m for m in ms if m.role.name in ADMIN_ROLES]


def _attach_lead(db: Session, org: uuid.UUID, inq: SalesInquiry) -> Lead:
    """Create (or reuse, via CRM duplicate detection) a lead. Inbound contact is self-initiated, so a new lead
    starts at 'interested'."""
    lead = Lead(organization_id=org, business_name=inq.company, email=inq.email, phone=inq.phone,
                country=inq.country, source=f"website:{inq.type}"[:60], status="interested",
                custom_fields={"inquiry_reference": inq.reference})
    apply_contact_fields(lead)
    try:
        check_duplicates(db, lead)
        db.add(lead)
        db.flush()
        created = True
    except AppError as e:
        lead = db.get(Lead, uuid.UUID(e.details["existing_lead_id"]))
        created = False
    if inq.marketing_consent and not lead.consent_reference:
        lead.consent_reference = f"website-marketing-opt-in:{inq.reference}"
    db.add(LeadContact(organization_id=org, lead_id=lead.id, full_name=inq.name, title=inq.role, email=inq.email,
                       phone=inq.phone))
    note = f"[{inq.reference}] {inq.type.replace('_', ' ')} from {inq.name}"
    if inq.message:
        note += f":\n\n{inq.message}"
    db.add(LeadNote(organization_id=org, lead_id=lead.id, body=note))
    db.add(LeadActivity(organization_id=org, lead_id=lead.id, type="inbound_inquiry",
                        data={"reference": inq.reference, "type": inq.type, "interests": inq.interests,
                              "lead_created": created}))
    db.add(ConsentRecord(organization_id=org, lead_id=lead.id, channel="email", basis="inbound_request",
                         evidence_text=f"Website form {inq.reference} ({inq.type}). Scope: responding to this "
                                       "inquiry only - NOT marketing consent.", captured_at=utcnow()))
    if inq.marketing_consent:
        db.add(ConsentRecord(organization_id=org, lead_id=lead.id, channel="email", basis="express_consent",
                             evidence_text=f"Website form {inq.reference}: visitor ticked the separate, "
                                           "unticked-by-default marketing opt-in.", captured_at=utcnow()))
    inq.lead_id = lead.id
    return lead


def _submit(db: Session, request: Request, body: ContactIn, booking: SalesBookedSlot | None = None) -> ContactOut:
    data = _fields(body, request)
    org = platform_owner_org(db)
    if org is None:
        prev = _recent(db, SalesInquiryInbox, data["email"], body.type, None)
        if prev is not None:
            return ContactOut(reference=prev.reference, duplicate=True)
        inq = SalesInquiryInbox(reference=booking.reference if booking else _reference(), **data)
        if booking is not None:
            inq.booking_start = booking.slot_start
        db.add(inq)
        db.flush()
        return ContactOut(reference=inq.reference)
    set_tenant(db, org)
    prev = _recent(db, SalesInquiry, data["email"], body.type, org)
    if prev is not None:
        return ContactOut(reference=prev.reference, duplicate=True)
    inq = SalesInquiry(organization_id=org, reference=booking.reference if booking else _reference(), **data)
    if booking is not None:
        inq.booking_start = booking.slot_start
    db.add(inq)
    db.flush()
    admins = _admins(db, org)
    owner = next((m.user_id for m in admins if m.role.name == "Owner"), admins[0].user_id if admins else None)
    lead = _attach_lead(db, org, inq)
    if booking is not None:
        db.add(LeadTask(organization_id=org, lead_id=lead.id, due_at=booking.slot_start, assignee_user_id=owner,
                        title=f"Demo call with {inq.name} ({inq.company}) - {inq.reference}"[:300]))
    title = f"New {body.type.replace('_', ' ')}: {inq.company}"
    detail = f"{inq.name} <{inq.email}> - ref {inq.reference}"
    if booking is not None:
        detail += f" - demo at {booking.slot_start.isoformat()}"
    for m in admins:
        notify(db, org, m.user_id, "sales_inquiry", title, detail)
    audit(db, "sales.inquiry_received", org_id=org, user_id=None, entity_type="sales_inquiry", entity_id=inq.id,
          data={"type": body.type, "reference": inq.reference}, request=request)
    db.flush()
    return ContactOut(reference=inq.reference)


# ---------------------------------------------------------------- public: pricing
def _plan_out(p: Plan, d: PlanDisplay | None) -> dict:
    limits = p.limits or {}
    show = d is not None and not d.contact_sales
    return {
        "code": p.code, "name": p.name, "trial_days": p.trial_days,
        # Catalog list prices are placeholders and are never published: only explicit display prices are.
        "price_monthly": str(d.price_monthly) if show and d.price_monthly is not None else None,
        "price_annual": str(d.price_annual) if show and d.price_annual is not None else None,
        "currency": d.currency if d else "USD",
        "contact_sales": bool(d.contact_sales) if d else False,
        "highlight": bool(d.highlight) if d else False,
        "badge": d.badge if d else None, "tagline": d.tagline if d else None,
        "bullets": (d.bullets or []) if d else [],
        "limits": limits,
        "features": [("Unlimited " if v is None else f"{v:,} ") + RESOURCE_LABELS.get(k, k)
                     for k, v in limits.items()],
    }


def _plans(db: Session, public_only: bool) -> list[dict]:
    billing.ensure_plans(db)
    q = select(Plan).order_by(Plan.sort_order)
    if public_only:
        q = q.where(Plan.is_public.is_(True))
    disp = {d.plan_code: d for d in db.scalars(select(PlanDisplay))}
    return [_plan_out(p, disp.get(p.code)) for p in db.scalars(q)]


@public_router.get("/public/pricing")
def public_pricing(request: Request, db: Session = Depends(get_db)):
    _limit(request, "read", READ_LIMIT)
    return {"plans": _plans(db, True), "note": "Plan limits are enforced by the product. A null price means the "
                                                "price is not published yet - contact sales."}


# ---------------------------------------------------------------- public: forms
@public_router.post("/public/sales/contact", response_model=ContactOut, status_code=201)
def public_contact(body: ContactIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "form", FORM_LIMIT)
    _guard_form(request, body)
    out = _submit(db, request, body)
    db.commit()
    return out


def _day_slots(db: Session, s: SalesSettings, day: date, now: datetime) -> list[dict]:
    tz = _tz(s.timezone)
    if day.weekday() not in (s.weekdays or []) or not s.booking_enabled:
        return []
    if day > now.astimezone(tz).date() + timedelta(days=s.horizon_days):
        return []
    sh, sm = map(int, s.day_start.split(":"))
    eh, em = map(int, s.day_end.split(":"))
    cur = datetime(day.year, day.month, day.day, sh, sm, tzinfo=tz)
    end = datetime(day.year, day.month, day.day, eh, em, tzinfo=tz)
    step = timedelta(minutes=s.slot_minutes + s.buffer_minutes)
    length = timedelta(minutes=s.slot_minutes)
    pad = timedelta(minutes=s.buffer_minutes)
    earliest = now + timedelta(hours=s.min_notice_hours)
    lo, hi = cur.astimezone(UTC) - timedelta(days=1), end.astimezone(UTC) + timedelta(days=1)
    booked = [(_aware(b.slot_start), _aware(b.slot_end)) for b in db.scalars(
        select(SalesBookedSlot).where(SalesBookedSlot.cancelled.is_(False), SalesBookedSlot.slot_start >= lo,
                                      SalesBookedSlot.slot_start <= hi))]
    out = []
    while cur + length <= end:
        st, en = cur.astimezone(UTC), (cur + length).astimezone(UTC)
        clash = any(st < be + pad and bs < en + pad for bs, be in booked)
        if st >= earliest and not clash:
            out.append({"start": st.isoformat(), "end": en.isoformat(), "label": cur.strftime("%H:%M")})
        cur += step
    return out


@public_router.get("/public/sales/slots")
def public_slots(request: Request, date_: date = Query(alias="date"), db: Session = Depends(get_db)):
    _limit(request, "read", READ_LIMIT)
    s = _settings(db)
    db.commit()
    return {"date": date_.isoformat(), "timezone": s.timezone, "slot_minutes": s.slot_minutes,
            "booking_enabled": s.booking_enabled, "weekdays": s.weekdays, "horizon_days": s.horizon_days,
            "slots": _day_slots(db, s, date_, utcnow())}


@public_router.post("/public/sales/book", response_model=ContactOut, status_code=201)
def public_book(body: BookIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "form", FORM_LIMIT)
    _guard_form(request, body)
    s = _settings(db)
    start = _aware(body.slot_start).astimezone(UTC)
    valid = {x["start"] for x in _day_slots(db, s, start.astimezone(_tz(s.timezone)).date(), utcnow())}
    if start.isoformat() not in valid:
        raise AppError(409, "slot_unavailable", "That time is no longer available - please pick another slot")
    slot = SalesBookedSlot(slot_start=start, slot_end=start + timedelta(minutes=s.slot_minutes),
                           reference=_reference(), ics_token=secrets.token_urlsafe(24))
    db.add(slot)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "slot_unavailable", "That time was just booked - please pick another slot") from None
    out = _submit(db, request, body, slot)
    if out.duplicate:  # same person already requested a demo within 10 minutes: don't hold a second slot
        db.rollback()
        return out
    db.commit()
    return ContactOut(reference=out.reference, ics_url=f"/api/v1/public/sales/bookings/{slot.ics_token}.ics",
                      slot_start=start)


def _ics_dt(dt: datetime) -> str:
    return _aware(dt).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


@public_router.get("/public/sales/bookings/{token}.ics")
def public_ics(token: str, request: Request, db: Session = Depends(get_db)):
    _limit(request, "read", READ_LIMIT)
    if not (16 <= len(token) <= 64):
        raise AppError(404, "not_found", "Booking not found")
    b = db.scalar(select(SalesBookedSlot).where(SalesBookedSlot.ics_token == token,
                                                SalesBookedSlot.cancelled.is_(False)))
    if b is None:
        raise AppError(404, "not_found", "Booking not found")
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Leadex AI//Sales//EN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{b.reference}@leadex.ai", f"DTSTAMP:{_ics_dt(utcnow())}", f"DTSTART:{_ics_dt(b.slot_start)}",
        f"DTEND:{_ics_dt(b.slot_end)}", "SUMMARY:Leadex AI demo",
        f"DESCRIPTION:Your Leadex AI demo (ref {b.reference}). We will email the meeting link before the call.",
        "END:VEVENT", "END:VCALENDAR", ""])
    return Response(body, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="leadex-demo-{b.reference}.ics"'})


# ---------------------------------------------------------------- internal
@router.get("/sales/plan-display")
def get_plan_display(_: TenantContext = Depends(sales_admin), db: Session = Depends(get_db)):
    return {"plans": _plans(db, False)}


@router.put("/sales/plan-display")
def put_plan_display(body: PlanDisplayBulk, request: Request, ctx: TenantContext = Depends(sales_admin),
                     db: Session = Depends(get_db)):
    billing.ensure_plans(db)
    codes = set(db.scalars(select(Plan.code)))
    for item in body.items:
        if item.plan_code not in codes:
            raise AppError(422, "unknown_plan", f"Unknown plan '{item.plan_code}'")
        d = db.scalar(select(PlanDisplay).where(PlanDisplay.plan_code == item.plan_code))
        if d is None:
            d = PlanDisplay(plan_code=item.plan_code)
            db.add(d)
        for k, v in item.model_dump().items():
            setattr(d, k, Decimal(v) if isinstance(v, Decimal) else v)
    audit(db, "sales.plan_display_updated", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="plan_display", data={"plans": [i.plan_code for i in body.items]}, request=request)
    db.commit()
    return {"plans": _plans(db, False)}


@router.get("/sales/settings")
def get_sales_settings(ctx: TenantContext = Depends(sales_admin), db: Session = Depends(get_db)):
    s = _settings(db)
    db.commit()
    owner = platform_owner_org(db)
    warnings = []
    if owner is None:
        n = db.scalar(select(func.count()).select_from(SalesInquiryInbox)) or 0
        warnings.append(f"No platform-owner organization is configured: {n} inquiries are waiting in the "
                        "unassigned inbox and no CRM leads are created. Mark your company organization as the "
                        "platform owner.")
    return {"settings": _settings_dict(s), "warnings": warnings,
            "platform_owner_org_id": str(owner) if owner else None,
            "is_platform_owner_context": owner == ctx.organization_id}


@router.put("/sales/settings")
def put_sales_settings(body: SettingsIn, request: Request, ctx: TenantContext = Depends(sales_admin),
                       db: Session = Depends(get_db)):
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise AppError(422, "invalid_timezone", "Unknown timezone") from None
    if body.day_start >= body.day_end:
        raise AppError(422, "invalid_hours", "day_end must be after day_start")
    if any(d not in range(7) for d in body.weekdays):
        raise AppError(422, "invalid_weekdays", "weekdays must be 0 (Mon) - 6 (Sun)")
    s = _settings(db)
    for k, v in body.model_dump().items():
        setattr(s, k, sorted(set(v)) if k == "weekdays" else v)
    audit(db, "sales.settings_updated", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="sales_settings", request=request)
    db.commit()
    return {"settings": _settings_dict(s)}


@router.get("/sales/inquiries", response_model=Page[InquiryOut])
def list_inquiries(ctx: TenantContext = Depends(inbox_admin), db: Session = Depends(get_db),
                   status: str | None = None, type: str | None = None, q: str | None = Query(None, max_length=100),
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    base = select(SalesInquiry).where(SalesInquiry.organization_id == ctx.organization_id)
    if status:
        base = base.where(SalesInquiry.status == status)
    if type:
        base = base.where(SalesInquiry.type == type)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(func.lower(SalesInquiry.company).like(like) | SalesInquiry.email.like(like)
                          | func.lower(SalesInquiry.name).like(like))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(SalesInquiry.created_at.desc()).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    return Page[InquiryOut](items=[InquiryOut.model_validate(r) for r in rows], total=total, page=page,
                            page_size=page_size)


@router.patch("/sales/inquiries/{inquiry_id}", response_model=InquiryOut)
def patch_inquiry(inquiry_id: uuid.UUID, body: InquiryPatch, request: Request,
                  ctx: TenantContext = Depends(inbox_admin), db: Session = Depends(get_db)):
    inq = db.scalar(select(SalesInquiry).where(SalesInquiry.id == inquiry_id,
                                               SalesInquiry.organization_id == ctx.organization_id))
    if inq is None:
        raise AppError(404, "not_found", "Inquiry not found")
    if body.status:
        inq.status = body.status
    if body.clear_assignee:
        inq.assignee_user_id = None
    elif body.assignee_user_id:
        ensure_member(db, ctx.organization_id, body.assignee_user_id, "assignee_user_id")
        inq.assignee_user_id = body.assignee_user_id
    audit(db, "sales.inquiry_updated", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="sales_inquiry",
          entity_id=inq.id, data=body.model_dump(mode="json", exclude_none=True), request=request)
    db.commit()
    db.refresh(inq)
    return InquiryOut.model_validate(inq)
