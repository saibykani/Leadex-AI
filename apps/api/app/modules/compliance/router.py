import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.compliance import checks  # noqa: F401  (registers OutreachGate checks)
from app.modules.compliance.gate import check_outreach
from app.modules.compliance.jurisdictions import DEFAULT_PROFILES, jurisdiction_code
from app.modules.compliance.models import (
    CommunicationPreference,
    ConsentRecord,
    DataSubjectRequest,
    JurisdictionProfile,
    KillSwitch,
    SuppressionRecord,
)
from app.modules.compliance.schemas import (
    CheckRequest,
    CheckResponse,
    ConsentCreate,
    ConsentOut,
    ConsentUpdate,
    DsrCreate,
    DsrOut,
    DsrUpdate,
    JurisdictionOut,
    KillSwitchCreate,
    KillSwitchOut,
    PreferenceOut,
    PreferenceSet,
    SuppressionCreate,
    SuppressionOut,
    WithdrawRequest,
)
from app.modules.crm import service as crm
from app.modules.identity.schemas import Page

router = APIRouter(prefix="/compliance", tags=["compliance"])

READ = require_permission("leads:read")
WRITE = require_permission("leads:write")
ORG_ADMIN = require_permission("org:write")  # Owner/Admin only
ADMIN_ROLES = {"Owner", "Admin"}
DSR_DUE_DAYS = 30


def _audit(db, ctx: TenantContext, action: str, entity_type: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=entity_type,
          entity_id=entity_id, data=data, request=request)


def _page(db, base, order, page: int, page_size: int):
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def _get(db, model, ctx: TenantContext, obj_id: uuid.UUID, label: str):
    obj = db.scalar(select(model).where(model.id == obj_id, model.organization_id == ctx.organization_id))
    if obj is None:
        raise AppError(404, "not_found", f"{label} not found")
    return obj


# ---------------------------------------------------------------- consents
@router.get("/consents", response_model=Page[ConsentOut])
def list_consents(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                  lead_id: uuid.UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(25, ge=1, le=200)):
    base = select(ConsentRecord).where(ConsentRecord.organization_id == ctx.organization_id)
    if lead_id:
        base = base.where(ConsentRecord.lead_id == lead_id)
    rows, total = _page(db, base, ConsentRecord.created_at.desc(), page, page_size)
    return Page[ConsentOut](items=[ConsentOut.model_validate(r) for r in rows], total=total, page=page,
                            page_size=page_size)


@router.post("/consents", response_model=ConsentOut, status_code=201)
def create_consent(body: ConsentCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                   db: Session = Depends(get_db)):
    lead = crm.get_lead(db, ctx, body.lead_id)
    rec = ConsentRecord(organization_id=ctx.organization_id, lead_id=lead.id, channel=body.channel,
                        basis=body.basis, evidence_text=body.evidence_text, evidence_url=body.evidence_url,
                        captured_at=body.captured_at or utcnow(), created_by_user_id=ctx.user.id)
    db.add(rec)
    db.flush()
    _audit(db, ctx, "consent.create", "consent_record", rec.id, request,
           {"lead_id": str(lead.id), "channel": rec.channel, "basis": rec.basis})
    db.commit()
    return rec


@router.get("/consents/{consent_id}", response_model=ConsentOut)
def get_consent(consent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _get(db, ConsentRecord, ctx, consent_id, "Consent record")


@router.patch("/consents/{consent_id}", response_model=ConsentOut)
def update_consent(consent_id: uuid.UUID, body: ConsentUpdate, request: Request,
                   ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    rec = _get(db, ConsentRecord, ctx, consent_id, "Consent record")
    if rec.withdrawn_at is not None:
        raise AppError(409, "consent_withdrawn", "A withdrawn consent cannot be edited; record a new one")
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    for k, v in changes.items():
        setattr(rec, k, v)
    _audit(db, ctx, "consent.update", "consent_record", rec.id, request, {"fields": sorted(changes)})
    db.commit()
    return rec


@router.post("/consents/{consent_id}/withdraw", response_model=ConsentOut)
def withdraw_consent(consent_id: uuid.UUID, body: WithdrawRequest, request: Request,
                     ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    rec = _get(db, ConsentRecord, ctx, consent_id, "Consent record")
    if rec.withdrawn_at is None:
        rec.withdrawn_at = utcnow()
        rec.withdrawn_reason = body.reason
        _audit(db, ctx, "consent.withdraw", "consent_record", rec.id, request,
               {"lead_id": str(rec.lead_id), "channel": rec.channel})
        db.commit()
    return rec


# ---------------------------------------------------------------- suppressions
@router.get("/suppressions", response_model=Page[SuppressionOut])
def list_suppressions(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                      page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(SuppressionRecord).where(SuppressionRecord.organization_id == ctx.organization_id)
    rows, total = _page(db, base, SuppressionRecord.created_at.desc(), page, page_size)
    return Page[SuppressionOut](items=[SuppressionOut.model_validate(r) for r in rows], total=total, page=page,
                                page_size=page_size)


@router.post("/suppressions", response_model=SuppressionOut, status_code=201)
def create_suppression(body: SuppressionCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                       db: Session = Depends(get_db)):
    email, phone = crm.normalize_email(body.email), crm.normalize_phone(body.phone)
    if not email and not phone:
        raise AppError(422, "validation_error", "email or phone is required")
    rec = SuppressionRecord(organization_id=ctx.organization_id, channel=body.channel, email_normalized=email,
                            phone_normalized=phone, reason=body.reason, created_by_user_id=ctx.user.id)
    db.add(rec)
    db.flush()
    _audit(db, ctx, "suppression.create", "suppression_record", rec.id, request, {"channel": rec.channel})
    db.commit()
    return rec


@router.delete("/suppressions/{suppression_id}", status_code=204)
def delete_suppression(suppression_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
                       db: Session = Depends(get_db)):
    rec = _get(db, SuppressionRecord, ctx, suppression_id, "Suppression record")
    _audit(db, ctx, "suppression.delete", "suppression_record", rec.id, request,
           {"channel": rec.channel, "reason": rec.reason})
    db.delete(rec)
    db.commit()


# ---------------------------------------------------------------- communication preferences
@router.get("/preferences/{lead_id}", response_model=list[PreferenceOut])
def list_preferences(lead_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    crm.get_lead(db, ctx, lead_id)
    return db.scalars(select(CommunicationPreference).where(
        CommunicationPreference.organization_id == ctx.organization_id,
        CommunicationPreference.lead_id == lead_id)).all()


@router.put("/preferences/{lead_id}", response_model=PreferenceOut)
def set_preference(lead_id: uuid.UUID, body: PreferenceSet, request: Request, ctx: TenantContext = Depends(WRITE),
                   db: Session = Depends(get_db)):
    lead = crm.get_lead(db, ctx, lead_id)
    pref = db.scalar(select(CommunicationPreference).where(
        CommunicationPreference.organization_id == ctx.organization_id,
        CommunicationPreference.lead_id == lead.id, CommunicationPreference.channel == body.channel))
    if pref is None:
        pref = CommunicationPreference(organization_id=ctx.organization_id, lead_id=lead.id, channel=body.channel)
        db.add(pref)
    pref.allowed, pref.notes = body.allowed, body.notes
    db.flush()
    _audit(db, ctx, "preference.set", "communication_preference", pref.id, request,
           {"lead_id": str(lead.id), "channel": body.channel, "allowed": body.allowed})
    db.commit()
    return pref


# ---------------------------------------------------------------- kill switches (organization scope)
@router.get("/kill-switches", response_model=list[KillSwitchOut])
def list_kill_switches(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    """Organization switches plus global switches (read-only here)."""
    return db.scalars(select(KillSwitch).where(
        (KillSwitch.organization_id == ctx.organization_id) | KillSwitch.organization_id.is_(None))
        .order_by(KillSwitch.created_at.desc())).all()


@router.post("/kill-switches", response_model=KillSwitchOut, status_code=201)
def create_kill_switch(body: KillSwitchCreate, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
                       db: Session = Depends(get_db)):
    if ctx.role_name not in ADMIN_ROLES:
        raise AppError(403, "forbidden", "Only Owners and Admins can set kill switches")
    if body.scope != "organization":
        raise AppError(403, "forbidden", "Global kill switches are managed via /admin/kill-switches")
    ks = KillSwitch(organization_id=ctx.organization_id, scope="organization", channel=body.channel, active=True,
                    reason=body.reason, set_by_user_id=ctx.user.id)
    db.add(ks)
    db.flush()
    _audit(db, ctx, "kill_switch.activate", "kill_switch", ks.id, request, {"channel": ks.channel})
    db.commit()
    return ks


@router.post("/kill-switches/{switch_id}/deactivate", response_model=KillSwitchOut)
def deactivate_kill_switch(switch_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
                           db: Session = Depends(get_db)):
    if ctx.role_name not in ADMIN_ROLES:
        raise AppError(403, "forbidden", "Only Owners and Admins can change kill switches")
    ks = _get(db, KillSwitch, ctx, switch_id, "Kill switch")
    if ks.active:
        ks.active = False
        _audit(db, ctx, "kill_switch.deactivate", "kill_switch", ks.id, request, {"channel": ks.channel})
        db.commit()
    return ks


# ---------------------------------------------------------------- gate checker
@router.post("/check", response_model=CheckResponse)
def check(body: CheckRequest, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    lead = crm.get_lead(db, ctx, body.lead_id)  # 404 for other tenants' leads
    d = check_outreach(db, ctx.organization_id, lead.id, body.channel, body.country_code)
    country = body.country_code or lead.country
    return CheckResponse(allowed=d.allowed, simulated=d.simulated, reasons=d.reasons,
                         jurisdiction=jurisdiction_code(country))


@router.get("/jurisdictions", response_model=list[JurisdictionOut])
def list_jurisdictions(_: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    rows = db.scalars(select(JurisdictionProfile).order_by(JurisdictionProfile.code)).all()
    if rows:
        return rows
    return [JurisdictionOut(code=c, name=p["name"], rules=p["rules"]) for c, p in DEFAULT_PROFILES.items()]


# ---------------------------------------------------------------- data subject requests
@router.get("/dsr", response_model=Page[DsrOut])
def list_dsr(ctx: TenantContext = Depends(ORG_ADMIN), db: Session = Depends(get_db),
             status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(DataSubjectRequest).where(DataSubjectRequest.organization_id == ctx.organization_id)
    if status:
        base = base.where(DataSubjectRequest.status == status)
    rows, total = _page(db, base, DataSubjectRequest.due_at.asc(), page, page_size)
    return Page[DsrOut](items=[DsrOut.model_validate(r) for r in rows], total=total, page=page,
                        page_size=page_size)


@router.post("/dsr", response_model=DsrOut, status_code=201)
def create_dsr(body: DsrCreate, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
               db: Session = Depends(get_db)):
    if body.lead_id:
        crm.get_lead(db, ctx, body.lead_id)
    dsr = DataSubjectRequest(organization_id=ctx.organization_id, type=body.type, status="open",
                             subject_email=crm.normalize_email(body.subject_email), subject_phone=body.subject_phone,
                             lead_id=body.lead_id, details=body.details,
                             due_at=utcnow() + timedelta(days=DSR_DUE_DAYS), created_by_user_id=ctx.user.id)
    db.add(dsr)
    db.flush()
    _audit(db, ctx, "dsr.create", "data_subject_request", dsr.id, request, {"type": dsr.type})
    db.commit()
    return dsr


@router.patch("/dsr/{dsr_id}", response_model=DsrOut)
def update_dsr(dsr_id: uuid.UUID, body: DsrUpdate, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
               db: Session = Depends(get_db)):
    dsr = _get(db, DataSubjectRequest, ctx, dsr_id, "Data subject request")
    if dsr.status in {"completed", "rejected"}:
        raise AppError(409, "dsr_closed", "This request is already closed")
    if body.status in {"completed", "rejected"} and not (body.resolution or "").strip():
        raise AppError(422, "resolution_required", "A resolution note is required to close a request")
    old = dsr.status
    dsr.status = body.status
    if body.resolution is not None:
        dsr.resolution = body.resolution
    if body.status in {"completed", "rejected"}:
        dsr.completed_at = utcnow()
    _audit(db, ctx, "dsr.update", "data_subject_request", dsr.id, request, {"from": old, "to": dsr.status})
    db.commit()
    return dsr


@router.post("/dsr/{dsr_id}/export")
def export_dsr(dsr_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
               db: Session = Depends(get_db)):
    """Machine-readable copy of everything held about the subject (access / portability)."""
    from app.modules.compliance import dsr_engine

    dsr = _get(db, DataSubjectRequest, ctx, dsr_id, "Data subject request")
    bundle = dsr_engine.export_bundle(db, ctx.organization_id, dsr)
    if dsr.status == "open":
        dsr.status = "in_progress"
    _audit(db, ctx, "dsr.export", "data_subject_request", dsr.id, request, {"records": len(bundle["records"])})
    db.commit()
    return bundle


@router.post("/dsr/{dsr_id}/erase", response_model=DsrOut)
def erase_dsr(dsr_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(ORG_ADMIN),
              db: Session = Depends(get_db)):
    """Erase the subject's personal data and close the request. Irreversible."""
    from app.modules.compliance import dsr_engine

    dsr = _get(db, DataSubjectRequest, ctx, dsr_id, "Data subject request")
    if dsr.type != "deletion":
        raise AppError(422, "wrong_request_type", "Only deletion requests can erase data")
    if dsr.status in {"completed", "rejected"}:
        raise AppError(409, "dsr_closed", "This request is already closed")
    result = dsr_engine.erase(db, ctx.organization_id, dsr, ctx.user.id)
    dsr.status, dsr.completed_at = "completed", utcnow()
    dsr.resolution = ("Erased automatically: " + ", ".join(f"{k}={v}" for k, v in result.items()) +
                      ". Kept: suppression entry (do-not-contact), consent records (evidence redacted), billing and "
                      "audit records required by law.")
    _audit(db, ctx, "dsr.erase", "data_subject_request", dsr.id, request, result)
    db.commit()
    return dsr
