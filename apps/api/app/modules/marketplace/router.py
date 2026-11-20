"""Marketplace HTTP API.

Staff endpoints require `marketplace:write` (requirements, providers, matching, referrals) or
`commissions:manage` (agreements, ledger). Portal endpoints only require org membership; access is
then narrowed to records linked to the caller (provider.portal_user_id == user, or
customer.email == user email). Portal users are ordinary org members (typically Viewer role).
"""
import hashlib
import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, get_tenant, require_permission
from app.modules.identity.models import IdempotencyKey
from app.modules.identity.schemas import Page
from app.modules.marketplace import engine
from app.modules.marketplace import service as svc
from app.modules.marketplace.models import (
    CommissionAgreement,
    CommissionDispute,
    CommissionTransaction,
    Customer,
    CustomerRequirement,
    MatchingSettings,
    ProviderDocument,
    ProviderMatch,
    ProviderVerification,
    Referral,
    ReferralEvent,
    ServiceCategory,
    ServiceProvider,
)
from app.modules.marketplace.schemas import (
    AccrueIn,
    AgreementIn,
    AgreementOut,
    AgreementUpdate,
    AmountIn,
    Balance,
    CategoryCreate,
    CategoryOut,
    CommissionSummary,
    CustomerOut,
    DisputeIn,
    DisputeOut,
    DisputeResolve,
    DocumentOut,
    EventOut,
    MatchOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    ReferralCommission,
    ReferralCreate,
    ReferralOut,
    RequirementCreate,
    RequirementOut,
    StatusIn,
    TxOut,
    VerificationOut,
    VerifyIn,
    Weights,
)

router = APIRouter(tags=["marketplace"])

MKT = require_permission("marketplace:write")
COM = require_permission("commissions:manage")

MAX_DOC_BYTES = 5 * 1024 * 1024
DOC_TYPES = {"application/pdf": b"%PDF", "image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
DOCUMENT_KINDS = {"rera", "license", "registration", "insurance", "certificate", "portfolio", "other"}

# Official registry lookups (e.g. state RERA portals) are not integrated. The adapter interface exists so a
# real client can be plugged in later; until then every registry reports `not_configured` and verification
# must be recorded manually with evidence.
REGISTRY_ADAPTERS: dict[str, object | None] = {"rera": None, "mca": None, "gst": None}

def _audit(db, ctx: TenantContext, action: str, entity_type: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=entity_type,
          entity_id=entity_id, data=data, request=request)

# ================================================================ categories & settings
@router.get("/marketplace/categories", response_model=list[CategoryOut])
def list_categories(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    svc.ensure_categories(db, ctx.organization_id)
    db.commit()
    return db.scalars(select(ServiceCategory).where(ServiceCategory.organization_id == ctx.organization_id)
                      .order_by(ServiceCategory.name)).all()

@router.post("/marketplace/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    slug = body.slug or re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    if db.scalar(select(ServiceCategory.id).where(ServiceCategory.organization_id == ctx.organization_id,
                                                  ServiceCategory.slug == slug)):
        raise AppError(409, "duplicate_category", "A category with this slug already exists")
    c = ServiceCategory(organization_id=ctx.organization_id, slug=slug, name=body.name.strip(), is_system=False)
    db.add(c)
    db.flush()
    _audit(db, ctx, "marketplace.category.create", "service_category", c.id, request, {"slug": slug})
    db.commit()
    return c

@router.get("/marketplace/matching-weights", response_model=Weights)
def get_weights(ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    return svc.weights_for(db, ctx.organization_id)

@router.put("/marketplace/matching-weights", response_model=Weights)
def put_weights(body: Weights, request: Request, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    row = db.scalar(select(MatchingSettings).where(MatchingSettings.organization_id == ctx.organization_id))
    if row is None:
        row = MatchingSettings(organization_id=ctx.organization_id, weights={})
        db.add(row)
    row.weights = body.model_dump()
    _audit(db, ctx, "marketplace.weights.update", "matching_settings", None, request, row.weights)
    db.commit()
    return row.weights

@router.get("/marketplace/registries")
def list_registries(ctx: TenantContext = Depends(MKT)):
    return [{"name": n, "status": "configured" if a else "not_configured"} for n, a in REGISTRY_ADAPTERS.items()]

# ================================================================ requirements
@router.post("/marketplace/requirements", response_model=RequirementOut, status_code=201)
def create_requirement(body: RequirementCreate, request: Request, ctx: TenantContext = Depends(MKT),
                       db: Session = Depends(get_db)):
    svc.ensure_categories(db, ctx.organization_id)
    svc.get_in_org(db, ctx, ServiceCategory, body.category_id, "Category")
    email = str(body.customer.email).strip().lower()
    cust = db.scalar(select(Customer).where(Customer.organization_id == ctx.organization_id, Customer.email == email))
    if cust is None:
        cust = Customer(organization_id=ctx.organization_id, email=email, full_name=body.customer.full_name,
                        phone=body.customer.phone)
        db.add(cust)
        db.flush()
    data = body.model_dump(exclude={"customer"})
    data["currency"] = data["currency"].upper()
    if data.get("country"):
        data["country"] = data["country"].upper()
    if not body.contact_permission:
        data["consent_reference"] = None
    req = CustomerRequirement(organization_id=ctx.organization_id, customer_id=cust.id, status="open", **data)
    db.add(req)
    db.flush()
    _audit(db, ctx, "marketplace.requirement.create", "customer_requirement", req.id, request,
           {"contact_permission": req.contact_permission})
    db.commit()
    return req

@router.get("/marketplace/requirements", response_model=Page[RequirementOut])
def list_requirements(ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db),
                      status: str | None = None, page: int = Query(1, ge=1),
                      page_size: int = Query(25, ge=1, le=200)):
    base = select(CustomerRequirement).where(CustomerRequirement.organization_id == ctx.organization_id)
    if status:
        base = base.where(CustomerRequirement.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(CustomerRequirement.created_at.desc(), CustomerRequirement.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[RequirementOut](items=rows, total=total, page=page, page_size=page_size)

@router.get("/marketplace/requirements/{req_id}", response_model=RequirementOut)
def get_requirement(req_id: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    return svc.get_in_org(db, ctx, CustomerRequirement, req_id, "Requirement")

@router.get("/marketplace/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    return svc.get_in_org(db, ctx, Customer, customer_id, "Customer")

def _match_out(db: Session, m: ProviderMatch) -> MatchOut:
    out = MatchOut.model_validate(m)
    out.provider_name = (m.explanation or {}).get("provider_name")
    return out

@router.post("/marketplace/requirements/{req_id}/match", response_model=list[MatchOut])
def match_requirement(req_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(MKT),
                      db: Session = Depends(get_db)):
    req = svc.get_in_org(db, ctx, CustomerRequirement, req_id, "Requirement")
    matches = svc.run_matching(db, ctx, req)
    _audit(db, ctx, "marketplace.requirement.match", "customer_requirement", req.id, request,
           {"matches": len(matches)})
    db.commit()
    return [_match_out(db, m) for m in matches]

@router.get("/marketplace/requirements/{req_id}/matches", response_model=list[MatchOut])
def list_matches(req_id: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    svc.get_in_org(db, ctx, CustomerRequirement, req_id, "Requirement")
    rows = db.scalars(select(ProviderMatch).where(ProviderMatch.requirement_id == req_id)
                      .order_by(ProviderMatch.score.desc())).all()
    return [_match_out(db, m) for m in rows]

# ================================================================ providers
def _provider_out(db: Session, p: ServiceProvider) -> ProviderOut:
    out = ProviderOut.model_validate(p)
    out.category_ids = svc.provider_category_ids(db, p.id)
    return out

@router.get("/marketplace/providers", response_model=Page[ProviderOut])
def list_providers(ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db),
                   verification_status: str | None = None, q: str | None = Query(None, max_length=200),
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(ServiceProvider).where(ServiceProvider.organization_id == ctx.organization_id)
    if verification_status:
        base = base.where(ServiceProvider.verification_status == verification_status)
    if q and q.strip():
        base = base.where(func.lower(ServiceProvider.business_name).like(f"%{q.strip().lower()}%"))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(ServiceProvider.business_name, ServiceProvider.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ProviderOut](items=[_provider_out(db, p) for p in rows], total=total, page=page, page_size=page_size)

def _apply_provider(db, ctx, p: ServiceProvider, changes: dict) -> None:
    cats = changes.pop("category_ids", None)
    if "portal_user_id" in changes:
        svc.ensure_member(db, ctx.organization_id, changes["portal_user_id"])
    if changes.get("currency"):
        changes["currency"] = changes["currency"].upper()
    if changes.get("email"):
        changes["email"] = str(changes["email"]).lower()
    for k, v in changes.items():
        if v is None and k in ("business_name", "availability", "currency"):
            continue
        setattr(p, k, v)
    if p.price_min is not None and p.price_max is not None and p.price_min > p.price_max:
        raise AppError(422, "validation_error", "price_min must be <= price_max")
    if cats is not None:
        db.flush()
        svc.set_provider_categories(db, ctx, p, cats)

@router.post("/marketplace/providers", response_model=ProviderOut, status_code=201)
def create_provider(body: ProviderCreate, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    p = ServiceProvider(organization_id=ctx.organization_id, business_name=body.business_name.strip(),
                        verification_status="unverified", availability="available", currency="INR")
    db.add(p)
    _apply_provider(db, ctx, p, body.model_dump(exclude={"business_name"}, exclude_unset=True))
    db.flush()
    _audit(db, ctx, "marketplace.provider.create", "service_provider", p.id, request,
           {"business_name": p.business_name})
    db.commit()
    return _provider_out(db, p)

@router.get("/marketplace/providers/{pid}", response_model=ProviderOut)
def get_provider(pid: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    return _provider_out(db, svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider"))

@router.patch("/marketplace/providers/{pid}", response_model=ProviderOut)
def update_provider(pid: uuid.UUID, body: ProviderUpdate, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    p = svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    changes = body.model_dump(exclude_unset=True)
    _apply_provider(db, ctx, p, dict(changes))
    _audit(db, ctx, "marketplace.provider.update", "service_provider", p.id, request, {"fields": sorted(changes)})
    db.commit()
    db.refresh(p)
    return _provider_out(db, p)

@router.post("/marketplace/providers/{pid}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(pid: uuid.UUID, request: Request, document_type: str = Form(...),
                          file: UploadFile = File(...), ctx: TenantContext = Depends(MKT),
                          db: Session = Depends(get_db)):
    p = svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    kind = document_type.strip().lower()
    if kind not in DOCUMENT_KINDS:
        raise AppError(422, "invalid_document_type", "Unsupported document type", {"allowed": sorted(DOCUMENT_KINDS)})
    ctype = (file.content_type or "").lower()
    if ctype == "image/jpg":
        ctype = "image/jpeg"
    if ctype not in DOC_TYPES:
        raise AppError(415, "unsupported_media_type", "Only PDF, PNG and JPEG files are accepted")
    content = await file.read(MAX_DOC_BYTES + 1)
    if len(content) > MAX_DOC_BYTES:
        raise AppError(413, "file_too_large", "Documents must be 5 MB or smaller")
    if not content.startswith(DOC_TYPES[ctype]):
        raise AppError(415, "unsupported_media_type", "File content does not match its declared type")
    from app.core.scanning import scan_bytes

    scan_bytes(content, file.filename or "document")
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", (file.filename or "document"))[:255]
    doc = ProviderDocument(organization_id=ctx.organization_id, provider_id=p.id, document_type=kind, filename=name,
                           content_type=ctype, size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
                           content=content, uploaded_by=ctx.user.id)
    db.add(doc)
    db.flush()
    _audit(db, ctx, "marketplace.provider.document_upload", "provider_document", doc.id, request,
           {"provider_id": str(p.id), "document_type": kind, "sha256": doc.sha256})
    db.commit()
    return doc

@router.get("/marketplace/providers/{pid}/documents", response_model=list[DocumentOut])
def list_documents(pid: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    return db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == pid)
                      .order_by(ProviderDocument.created_at.desc())).all()

@router.get("/marketplace/providers/{pid}/documents/{doc_id}/download")
def download_document(pid: uuid.UUID, doc_id: uuid.UUID, ctx: TenantContext = Depends(MKT),
                      db: Session = Depends(get_db)):
    doc = svc.get_in_org(db, ctx, ProviderDocument, doc_id, "Document")
    if doc.provider_id != pid:
        raise AppError(404, "not_found", "Document not found")
    return Response(doc.content, media_type=doc.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{doc.filename}"',
                             "X-Content-Type-Options": "nosniff"})

@router.post("/marketplace/providers/{pid}/verify", response_model=VerificationOut, status_code=201)
def verify_provider(pid: uuid.UUID, body: VerifyIn, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    p = svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    if body.method == "registry":
        name = (body.registry_name or "").lower()
        if REGISTRY_ADAPTERS.get(name) is None:
            raise AppError(501, "registry_not_configured",
                           f"No registry integration is configured for '{body.registry_name}'. "
                           "Record a manual verification with evidence instead.", {"status": "not_configured"})
    docs = [str(d) for d in body.document_ids]
    for d in body.document_ids:
        doc = svc.get_in_org(db, ctx, ProviderDocument, d, "Document")
        if doc.provider_id != p.id:
            raise AppError(422, "invalid_document", "Document does not belong to this provider")
    if body.decision in ("verified", "rejected") and not ((body.evidence or "").strip() or docs):
        raise AppError(422, "evidence_required",
                       "Manual verification requires written evidence or at least one supporting document")
    v = ProviderVerification(organization_id=ctx.organization_id, provider_id=p.id, method=body.method,
                             registry_name=body.registry_name, reference=body.reference, decision=body.decision,
                             evidence=body.evidence, document_ids=docs, verified_by=ctx.user.id)
    db.add(v)
    old = p.verification_status
    p.verification_status = body.decision
    db.flush()
    _audit(db, ctx, "marketplace.provider.verify", "service_provider", p.id, request,
           {"from": old, "to": body.decision, "method": body.method, "reference": body.reference})
    db.commit()
    return v

@router.get("/marketplace/providers/{pid}/verifications", response_model=list[VerificationOut])
def list_verifications(pid: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    return db.scalars(select(ProviderVerification).where(ProviderVerification.provider_id == pid)
                      .order_by(ProviderVerification.created_at.desc())).all()

# ================================================================ referrals
def _ref_out(db: Session, r: Referral) -> ReferralOut:
    out = ReferralOut.model_validate(r)
    out.provider_name = db.scalar(select(ServiceProvider.business_name).where(ServiceProvider.id == r.provider_id))
    out.requirement_title = db.scalar(select(CustomerRequirement.title)
                                      .where(CustomerRequirement.id == r.requirement_id))
    return out

@router.post("/referrals", response_model=ReferralOut, status_code=201)
def create_referral(body: ReferralCreate, request: Request, response: Response,
                    idempotency_key: str | None = Header(default=None, max_length=128),
                    ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    req_hash = hashlib.sha256(("referral:" + body.model_dump_json()).encode()).hexdigest()
    if idempotency_key:
        prior = db.scalar(select(IdempotencyKey).where(IdempotencyKey.organization_id == ctx.organization_id,
                                                       IdempotencyKey.key == idempotency_key))
        if prior is not None:
            if prior.request_hash != req_hash:
                raise AppError(409, "idempotency_conflict", "Idempotency-Key was reused with a different request")
            response.headers["Idempotent-Replayed"] = "true"
            return prior.response
    req = svc.get_in_org(db, ctx, CustomerRequirement, body.requirement_id, "Requirement")
    prov = svc.get_in_org(db, ctx, ServiceProvider, body.provider_id, "Provider")
    if not req.contact_permission:
        raise AppError(422, "consent_required",
                       "The customer has not granted permission to share their requirement with providers")
    if prov.verification_status == "rejected":
        raise AppError(422, "provider_rejected", "Cannot refer to a provider whose verification was rejected")
    if db.scalar(select(Referral.id).where(Referral.requirement_id == req.id, Referral.provider_id == prov.id)):
        raise AppError(409, "duplicate_referral", "This requirement has already been referred to this provider")
    matched = db.scalar(select(ProviderMatch.id).where(ProviderMatch.requirement_id == req.id,
                                                       ProviderMatch.provider_id == prov.id))
    ref = Referral(organization_id=ctx.organization_id, requirement_id=req.id, provider_id=prov.id,
                   status="matched" if matched else "requirement_received", currency=req.currency,
                   created_by=ctx.user.id)
    db.add(ref)
    db.flush()
    svc.add_event(db, ctx.organization_id, ctx.user.id, ref, "referral.created", None, ref.status, body.note)
    req.status = "referred"
    _audit(db, ctx, "marketplace.referral.create", "referral", ref.id, request,
           {"requirement_id": str(req.id), "provider_id": str(prov.id), "unverified_provider":
            prov.verification_status != "verified"})
    out = _ref_out(db, ref)
    if idempotency_key:
        db.add(IdempotencyKey(organization_id=ctx.organization_id, key=idempotency_key, request_hash=req_hash,
                              response=out.model_dump(mode="json")))
    db.commit()
    return out

@router.get("/referrals", response_model=Page[ReferralOut])
def list_referrals(ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db),
                   status: list[str] | None = Query(None), provider_id: uuid.UUID | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
    base = select(Referral).where(Referral.organization_id == ctx.organization_id)
    if status:
        base = base.where(Referral.status.in_(status))
    if provider_id:
        base = base.where(Referral.provider_id == provider_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Referral.updated_at.desc(), Referral.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ReferralOut](items=[_ref_out(db, r) for r in rows], total=total, page=page, page_size=page_size)

@router.get("/referrals/{rid}", response_model=ReferralOut)
def get_referral(rid: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    return _ref_out(db, svc.get_in_org(db, ctx, Referral, rid, "Referral"))

@router.get("/referrals/{rid}/events", response_model=list[EventOut])
def referral_events(rid: uuid.UUID, ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    svc.get_in_org(db, ctx, Referral, rid, "Referral")
    return db.scalars(select(ReferralEvent).where(ReferralEvent.referral_id == rid)
                      .order_by(ReferralEvent.created_at, ReferralEvent.id)).all()

@router.post("/referrals/{rid}/status", response_model=ReferralOut)
def change_referral_status(rid: uuid.UUID, body: StatusIn, request: Request, ctx: TenantContext = Depends(MKT),
                           db: Session = Depends(get_db)):
    ref = svc.get_in_org(db, ctx, Referral, rid, "Referral")
    old = ref.status
    svc.transition(db, ctx.organization_id, ctx.user.id, ref, body.status, body.note, body.deal_value)
    _audit(db, ctx, "marketplace.referral.status_change", "referral", ref.id, request,
           {"from": old, "to": body.status})
    db.commit()
    db.refresh(ref)
    return _ref_out(db, ref)

# ================================================================ commissions
@router.get("/commissions/agreements", response_model=list[AgreementOut])
def list_agreements(ctx: TenantContext = Depends(COM), db: Session = Depends(get_db),
                    provider_id: uuid.UUID | None = None):
    q = select(CommissionAgreement).where(CommissionAgreement.organization_id == ctx.organization_id)
    if provider_id:
        q = q.where(CommissionAgreement.provider_id == provider_id)
    return db.scalars(q.order_by(CommissionAgreement.created_at.desc())).all()

@router.post("/commissions/agreements", response_model=AgreementOut, status_code=201)
def create_agreement(body: AgreementIn, request: Request, ctx: TenantContext = Depends(COM),
                     db: Session = Depends(get_db)):
    svc.get_in_org(db, ctx, ServiceProvider, body.provider_id, "Provider")
    splits = engine.validate_splits([s.model_dump() for s in body.splits])
    a = CommissionAgreement(organization_id=ctx.organization_id, provider_id=body.provider_id, type=body.type,
                            value=body.value, currency=body.currency.upper(), splits=splits,
                            settlement_conditions=body.settlement_conditions.model_dump(), notes=body.notes,
                            active=True)
    db.add(a)
    db.flush()
    _audit(db, ctx, "commission.agreement.create", "commission_agreement", a.id, request,
           {"type": a.type, "value": str(a.value) if a.value is not None else None, "currency": a.currency})
    db.commit()
    return a

@router.get("/commissions/agreements/{aid}", response_model=AgreementOut)
def get_agreement(aid: uuid.UUID, ctx: TenantContext = Depends(COM), db: Session = Depends(get_db)):
    return svc.get_in_org(db, ctx, CommissionAgreement, aid, "Agreement")

@router.patch("/commissions/agreements/{aid}", response_model=AgreementOut)
def update_agreement(aid: uuid.UUID, body: AgreementUpdate, request: Request, ctx: TenantContext = Depends(COM),
                     db: Session = Depends(get_db)):
    a = svc.get_in_org(db, ctx, CommissionAgreement, aid, "Agreement")
    ch = body.model_dump(exclude_unset=True)
    if "splits" in ch:
        a.splits = engine.validate_splits(ch.pop("splits") or [])
    if "settlement_conditions" in ch:
        a.settlement_conditions = ch.pop("settlement_conditions")
    if ch.get("value") is not None and a.type == "percentage" and ch["value"] > 100:
        raise AppError(422, "validation_error", "percentage value must be <= 100")
    for k, v in ch.items():
        if v is not None or k == "notes":
            setattr(a, k, v)
    _audit(db, ctx, "commission.agreement.update", "commission_agreement", a.id, request,
           {"fields": sorted(body.model_dump(exclude_unset=True))})
    db.commit()
    db.refresh(a)
    return a

@router.delete("/commissions/agreements/{aid}", status_code=204)
def deactivate_agreement(aid: uuid.UUID, request: Request, ctx: TenantContext = Depends(COM),
                         db: Session = Depends(get_db)):
    """Agreements referenced by the ledger are never deleted; they are deactivated."""
    a = svc.get_in_org(db, ctx, CommissionAgreement, aid, "Agreement")
    a.active = False
    _audit(db, ctx, "commission.agreement.deactivate", "commission_agreement", a.id, request)
    db.commit()

def _tx(db, ctx, ref: Referral, kind: str, amount: Decimal, currency: str, agreement_id=None, reference=None,
        data=None) -> CommissionTransaction:
    t = CommissionTransaction(organization_id=ctx.organization_id, referral_id=ref.id, agreement_id=agreement_id,
                              kind=kind, amount=engine.money(amount), currency=currency, reference=reference,
                              data=data, created_by=ctx.user.id)
    db.add(t)
    db.flush()
    return t

def _ledger_action(db, ctx, request, ref, kind, amount, currency, **kw) -> TxOut:
    t = _tx(db, ctx, ref, kind, amount, currency, **kw)
    _audit(db, ctx, f"commission.{kind}", "referral", ref.id, request,
           {"transaction_id": str(t.id), "amount": str(t.amount), "currency": t.currency})
    db.commit()
    return TxOut.model_validate(t)

@router.post("/referrals/{rid}/commission/accrue", response_model=TxOut, status_code=201)
def accrue(rid: uuid.UUID, body: AccrueIn, request: Request, ctx: TenantContext = Depends(COM),
           db: Session = Depends(get_db)):
    ref = svc.get_in_org(db, ctx, Referral, rid, "Referral")
    if ref.status != "converted":
        raise AppError(409, "not_converted", "Commission can only be accrued on a converted referral")
    if svc.referral_position(db, ctx.organization_id, ref)["net"] > 0:
        raise AppError(409, "already_accrued", "Commission has already been accrued for this referral")
    if body.agreement_id:
        a = svc.get_in_org(db, ctx, CommissionAgreement, body.agreement_id, "Agreement")
        if a.provider_id != ref.provider_id:
            raise AppError(422, "agreement_mismatch", "Agreement belongs to a different provider")
    else:
        a = db.scalar(select(CommissionAgreement).where(
            CommissionAgreement.organization_id == ctx.organization_id,
            CommissionAgreement.provider_id == ref.provider_id, CommissionAgreement.active.is_(True))
            .order_by(CommissionAgreement.created_at.desc()).limit(1))
        if a is None:
            raise AppError(422, "no_agreement", "No active commission agreement exists for this provider")
    if not a.active:
        raise AppError(422, "agreement_inactive", "Agreement is inactive")
    deal = body.deal_value or ref.deal_value
    if a.type == "percentage" and deal is not None and ref.currency != a.currency:
        raise AppError(422, "currency_mismatch", "Deal currency differs from the agreement currency")
    amount = engine.compute_commission(a.type, a.value, deal, body.amount)
    if body.deal_value is not None:
        ref.deal_value = body.deal_value
    return _ledger_action(db, ctx, request, ref, "accrual", amount, a.currency, agreement_id=a.id,
                          data={"type": a.type, "value": str(a.value) if a.value is not None else None,
                                "deal_value": str(deal) if deal is not None else None})

def _ref_and_pos(db, ctx, rid):
    ref = svc.get_in_org(db, ctx, Referral, rid, "Referral")
    pos = svc.referral_position(db, ctx.organization_id, ref)
    if pos["net"] <= 0:
        raise AppError(409, "not_accrued", "No commission has been accrued for this referral")
    return ref, pos

def _amount(requested: Decimal | None, limit: Decimal, what: str) -> Decimal:
    if limit <= 0:
        raise AppError(409, "nothing_to_" + what, f"Nothing left to {what}")
    amt = engine.money(requested) if requested is not None else limit
    if amt > limit:
        raise AppError(422, "amount_exceeds_balance", f"Amount exceeds the {limit} available to {what}")
    return amt

@router.post("/referrals/{rid}/commission/invoice", response_model=TxOut, status_code=201)
def invoice(rid: uuid.UUID, body: AmountIn, request: Request, ctx: TenantContext = Depends(COM),
            db: Session = Depends(get_db)):
    ref, pos = _ref_and_pos(db, ctx, rid)
    amt = _amount(body.amount, pos["net"] - pos["invoiced"], "invoice")
    return _ledger_action(db, ctx, request, ref, "invoice", amt, pos["currency"], reference=body.reference,
                          agreement_id=pos["agreement_id"])

@router.post("/referrals/{rid}/commission/payment", response_model=TxOut, status_code=201)
def payment(rid: uuid.UUID, body: AmountIn, request: Request, ctx: TenantContext = Depends(COM),
            db: Session = Depends(get_db)):
    ref, pos = _ref_and_pos(db, ctx, rid)
    amt = _amount(body.amount, pos["invoiced"] - pos["paid"], "pay")
    return _ledger_action(db, ctx, request, ref, "payment", amt, pos["currency"], reference=body.reference,
                          agreement_id=pos["agreement_id"])

@router.post("/referrals/{rid}/commission/refund", response_model=TxOut, status_code=201)
def refund(rid: uuid.UUID, body: AmountIn, request: Request, ctx: TenantContext = Depends(COM),
           db: Session = Depends(get_db)):
    ref, pos = _ref_and_pos(db, ctx, rid)
    if pos["settled"] > 0:
        raise AppError(409, "already_settled", "Settled commissions cannot be refunded; raise a dispute instead")
    amt = _amount(body.amount, pos["paid"], "refund")
    return _ledger_action(db, ctx, request, ref, "refund", amt, pos["currency"], reference=body.reference,
                          agreement_id=pos["agreement_id"])

@router.post("/referrals/{rid}/commission/settle", response_model=TxOut, status_code=201)
def settle(rid: uuid.UUID, request: Request, ctx: TenantContext = Depends(COM), db: Session = Depends(get_db)):
    ref, pos = _ref_and_pos(db, ctx, rid)
    a = db.get(CommissionAgreement, pos["agreement_id"]) if pos["agreement_id"] else None
    blockers = svc.settlement_blockers(db, ctx.organization_id, ref, a.settlement_conditions if a else None)
    if blockers:
        raise AppError(409, "settlement_conditions_unmet", "Settlement conditions are not met",
                       {"blockers": blockers})
    amt = pos["net"] - pos["settled"]
    allocation = engine.split_amount(amt, (a.splits if a else None) or [])
    return _ledger_action(db, ctx, request, ref, "settlement", amt, pos["currency"],
                          agreement_id=pos["agreement_id"], data={"allocation": allocation})

@router.post("/referrals/{rid}/commission/disputes", response_model=DisputeOut, status_code=201)
def raise_dispute(rid: uuid.UUID, body: DisputeIn, request: Request, ctx: TenantContext = Depends(COM),
                  db: Session = Depends(get_db)):
    ref, pos = _ref_and_pos(db, ctx, rid)
    amt = _amount(body.amount, pos["net"], "dispute")
    d = CommissionDispute(organization_id=ctx.organization_id, referral_id=ref.id, raised_by=ctx.user.id,
                          reason=body.reason, amount=amt, status="open")
    db.add(d)
    db.flush()
    _tx(db, ctx, ref, "dispute", amt, pos["currency"], agreement_id=pos["agreement_id"],
        data={"dispute_id": str(d.id)})
    _audit(db, ctx, "commission.dispute.open", "commission_dispute", d.id, request, {"referral_id": str(ref.id)})
    db.commit()
    return d

@router.post("/commissions/disputes/{did}/resolve", response_model=DisputeOut)
def resolve_dispute(did: uuid.UUID, body: DisputeResolve, request: Request, ctx: TenantContext = Depends(COM),
                    db: Session = Depends(get_db)):
    d = svc.get_in_org(db, ctx, CommissionDispute, did, "Dispute")
    if d.status != "open":
        raise AppError(409, "dispute_closed", "Dispute is already closed")
    ref = svc.get_in_org(db, ctx, Referral, d.referral_id, "Referral")
    if body.reversal_amount is not None:
        if body.status != "resolved":
            raise AppError(422, "validation_error", "A reversal can only accompany a resolved dispute")
        pos = svc.referral_position(db, ctx.organization_id, ref)
        amt = _amount(body.reversal_amount, pos["net"] - pos["settled"], "reverse")
        _tx(db, ctx, ref, "reversal", amt, pos["currency"], agreement_id=pos["agreement_id"],
            data={"dispute_id": str(d.id)})
    d.status, d.resolution = body.status, body.resolution
    _audit(db, ctx, f"commission.dispute.{body.status}", "commission_dispute", d.id, request,
           {"reversal": str(body.reversal_amount) if body.reversal_amount else None})
    db.commit()
    db.refresh(d)
    return d

@router.get("/referrals/{rid}/commission", response_model=ReferralCommission)
def referral_commission(rid: uuid.UUID, ctx: TenantContext = Depends(COM), db: Session = Depends(get_db)):
    ref = svc.get_in_org(db, ctx, Referral, rid, "Referral")
    txs = svc.ledger(db, ctx.organization_id, [ref.id])
    pos = svc.referral_position(db, ctx.organization_id, ref)
    a = db.get(CommissionAgreement, pos["agreement_id"]) if pos["agreement_id"] else None
    blockers = svc.settlement_blockers(db, ctx.organization_id, ref, a.settlement_conditions if a else None)
    disputes = db.scalars(select(CommissionDispute).where(CommissionDispute.referral_id == ref.id)
                          .order_by(CommissionDispute.created_at)).all()
    return ReferralCommission(referral_id=ref.id, balances=[Balance(**b) for b in svc.balances(txs)],
                              transactions=[TxOut.model_validate(t) for t in txs],
                              disputes=[DisputeOut.model_validate(x) for x in disputes],
                              settleable=not blockers, blockers=blockers)

@router.get("/commissions", response_model=CommissionSummary)
def commission_summary(ctx: TenantContext = Depends(COM), db: Session = Depends(get_db),
                       limit: int = Query(100, ge=1, le=500)):
    txs = svc.ledger(db, ctx.organization_id)
    open_d = db.scalar(select(func.count()).select_from(CommissionDispute).where(
        CommissionDispute.organization_id == ctx.organization_id, CommissionDispute.status == "open")) or 0
    return CommissionSummary(balances=[Balance(**b) for b in svc.balances(txs)], open_disputes=open_d,
                             transactions=[TxOut.model_validate(t) for t in reversed(txs[-limit:])])

@router.get("/commissions/disputes", response_model=list[DisputeOut])
def list_disputes(ctx: TenantContext = Depends(COM), db: Session = Depends(get_db), status: str | None = None):
    q = select(CommissionDispute).where(CommissionDispute.organization_id == ctx.organization_id)
    if status:
        q = q.where(CommissionDispute.status == status)
    return db.scalars(q.order_by(CommissionDispute.created_at.desc())).all()

# ================================================================ provider portal
def _my_provider_ids(db: Session, ctx: TenantContext) -> list[uuid.UUID]:
    return list(db.scalars(select(ServiceProvider.id).where(ServiceProvider.organization_id == ctx.organization_id,
                                                            ServiceProvider.portal_user_id == ctx.user.id)))

def _portal_ref(db: Session, r: Referral) -> dict:
    req = db.get(CustomerRequirement, r.requirement_id)
    out = _ref_out(db, r).model_dump(mode="json")
    out["requirement"] = {"title": req.title, "city": req.city, "country": req.country,
                          "budget_min": str(req.budget_min) if req.budget_min is not None else None,
                          "budget_max": str(req.budget_max) if req.budget_max is not None else None,
                          "currency": req.currency, "timeline": req.timeline, "description": req.description}
    # Customer contact details are only released once the provider accepted AND the customer consented.
    if req.contact_permission and r.status not in ("requirement_received", "matched", "invited", "declined"):
        c = db.get(Customer, req.customer_id)
        out["customer"] = {"full_name": c.full_name, "email": c.email, "phone": c.phone}
    else:
        out["customer"] = None
    return out

def _my_referral(db, ctx, rid) -> Referral:
    ids = _my_provider_ids(db, ctx)
    r = db.scalar(select(Referral).where(Referral.id == rid, Referral.organization_id == ctx.organization_id,
                                         Referral.provider_id.in_(ids)))
    if r is None:
        raise AppError(404, "not_found", "Referral not found")
    return r

@router.get("/portal/provider/profile", response_model=list[ProviderOut])
def portal_provider_profile(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    rows = db.scalars(select(ServiceProvider).where(ServiceProvider.organization_id == ctx.organization_id,
                                                    ServiceProvider.portal_user_id == ctx.user.id)).all()
    return [_provider_out(db, p) for p in rows]

@router.get("/portal/provider/referrals")
def portal_provider_referrals(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    ids = _my_provider_ids(db, ctx)
    rows = db.scalars(select(Referral).where(Referral.organization_id == ctx.organization_id,
                                             Referral.provider_id.in_(ids))
                      .order_by(Referral.updated_at.desc())).all() if ids else []
    return [_portal_ref(db, r) for r in rows]

def _portal_move(db, ctx, request, rid, new, note=None, deal_value=None):
    r = _my_referral(db, ctx, rid)
    if new not in engine.PROVIDER_ALLOWED:
        raise AppError(403, "forbidden", f"Providers may not set status '{new}'")
    old = r.status
    svc.transition(db, ctx.organization_id, ctx.user.id, r, new, note, deal_value)
    _audit(db, ctx, "marketplace.referral.portal_status", "referral", r.id, request, {"from": old, "to": new})
    db.commit()
    db.refresh(r)
    return _portal_ref(db, r)

@router.post("/portal/provider/referrals/{rid}/accept")
def portal_accept(rid: uuid.UUID, request: Request, ctx: TenantContext = Depends(get_tenant),
                  db: Session = Depends(get_db)):
    return _portal_move(db, ctx, request, rid, "accepted")

@router.post("/portal/provider/referrals/{rid}/decline")
def portal_decline(rid: uuid.UUID, request: Request, ctx: TenantContext = Depends(get_tenant),
                   db: Session = Depends(get_db)):
    return _portal_move(db, ctx, request, rid, "declined")

@router.post("/portal/provider/referrals/{rid}/status")
def portal_status(rid: uuid.UUID, body: StatusIn, request: Request, ctx: TenantContext = Depends(get_tenant),
                  db: Session = Depends(get_db)):
    return _portal_move(db, ctx, request, rid, body.status, body.note, body.deal_value)

@router.get("/portal/provider/earnings", response_model=list[Balance])
def portal_earnings(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    ids = _my_provider_ids(db, ctx)
    if not ids:
        return []
    rids = list(db.scalars(select(Referral.id).where(Referral.provider_id.in_(ids))))
    return [Balance(**b) for b in svc.balances(svc.ledger(db, ctx.organization_id, rids))]

# ================================================================ customer portal
def _my_customer_ids(db, ctx) -> list[uuid.UUID]:
    return list(db.scalars(select(Customer.id).where(Customer.organization_id == ctx.organization_id,
                                                     Customer.email == ctx.user.email.lower())))

@router.get("/portal/customer/requirements", response_model=list[RequirementOut])
def portal_customer_requirements(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    ids = _my_customer_ids(db, ctx)
    if not ids:
        return []
    return db.scalars(select(CustomerRequirement).where(CustomerRequirement.customer_id.in_(ids))
                      .order_by(CustomerRequirement.created_at.desc())).all()

@router.get("/portal/customer/requirements/{req_id}")
def portal_customer_requirement(req_id: uuid.UUID, ctx: TenantContext = Depends(get_tenant),
                                db: Session = Depends(get_db)):
    ids = _my_customer_ids(db, ctx)
    req = db.scalar(select(CustomerRequirement).where(CustomerRequirement.id == req_id,
                                                      CustomerRequirement.organization_id == ctx.organization_id,
                                                      CustomerRequirement.customer_id.in_(ids)))
    if req is None:
        raise AppError(404, "not_found", "Requirement not found")
    matches = db.scalars(select(ProviderMatch).where(ProviderMatch.requirement_id == req.id)
                         .order_by(ProviderMatch.score.desc()).limit(10)).all()
    refs = db.scalars(select(Referral).where(Referral.requirement_id == req.id)).all()
    return {
        "requirement": RequirementOut.model_validate(req).model_dump(mode="json"),
        "matches": [{"provider_name": (m.explanation or {}).get("provider_name"), "score": m.score,
                     "unverified": (m.explanation or {}).get("unverified_flag", True),
                     "factors": {k: v.get("reason") for k, v in (m.explanation or {}).get("factors", {}).items()}}
                    for m in matches],
        "referrals": [{"id": str(r.id), "status": r.status, "updated_at": r.updated_at.isoformat(),
                       "provider_name": db.scalar(select(ServiceProvider.business_name)
                                                  .where(ServiceProvider.id == r.provider_id))} for r in refs],
    }
