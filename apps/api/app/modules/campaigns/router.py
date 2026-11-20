"""Campaign lifecycle: draft -> pending_approval -> approved -> running <-> paused -> completed | cancelled.

Approval rule: the approver needs `campaigns:approve` and must be a different user from the creator,
unless the organization has exactly one active member (a solo workspace cannot have a second reviewer;
the self-approval is recorded as such in the approval row and the event log).
"""
import hashlib
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.billing import service as billing
from app.modules.campaigns import service as svc
from app.modules.campaigns.models import Campaign, CampaignApproval, CampaignEvent, CampaignRecipient
from app.modules.campaigns.schemas import (
    ApprovalIn,
    ApprovalOut,
    CampaignCreate,
    CampaignDetail,
    CampaignOut,
    CampaignPatch,
    EmailConfig,
    EventOut,
    RecipientOut,
    RecipientsAdd,
)
from app.modules.communication.models import EmailAccount, EmailCampaign, EmailTemplate, WhatsAppTemplate
from app.modules.compliance.gate import check_outreach
from app.modules.crm.models import Lead
from app.modules.identity.models import IdempotencyKey, OrganizationMembership
from app.modules.identity.schemas import Page

router = APIRouter(tags=["campaigns"])
READ = require_permission("leads:read")
WRITE = require_permission("campaigns:write")
APPROVE = require_permission("campaigns:approve")


def _audit(db, ctx, action, cid, request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="campaign", entity_id=cid,
          data=data, request=request)


def _campaign(db: Session, ctx: TenantContext, cid: uuid.UUID) -> Campaign:
    c = db.scalar(select(Campaign).where(Campaign.id == cid, Campaign.organization_id == ctx.organization_id))
    if c is None:
        raise AppError(404, "not_found", "Campaign not found")
    return c


def _require_status(c: Campaign, *allowed: str) -> None:
    if c.status not in allowed:
        raise AppError(409, "invalid_state", f"Campaign is {c.status}; expected one of {list(allowed)}")


def _email_cfg(db, c) -> EmailCampaign | None:
    return db.scalar(select(EmailCampaign).where(EmailCampaign.campaign_id == c.id,
                                                 EmailCampaign.organization_id == c.organization_id))


def _apply_email(db: Session, ctx: TenantContext, c: Campaign, cfg_in: EmailConfig) -> None:
    if cfg_in.account_id and not db.scalar(select(EmailAccount.id).where(
            EmailAccount.id == cfg_in.account_id, EmailAccount.organization_id == ctx.organization_id)):
        raise AppError(422, "invalid_account", "Email account not found in this workspace")
    for s in cfg_in.steps:
        if not db.scalar(select(EmailTemplate.id).where(EmailTemplate.id == s.template_id,
                                                        EmailTemplate.organization_id == ctx.organization_id)):
            raise AppError(422, "invalid_template", "Email template not found in this workspace")
    cfg = _email_cfg(db, c) or EmailCampaign(organization_id=ctx.organization_id, campaign_id=c.id, steps=[])
    cfg.account_id = cfg_in.account_id
    cfg.steps = [{"template_id": str(s.template_id), "delay_hours": s.delay_hours} for s in cfg_in.steps]
    cfg.physical_address = cfg_in.physical_address
    cfg.website_preview_base_url = cfg_in.website_preview_base_url
    cfg.personalize_with_ai = cfg_in.personalize_with_ai
    db.add(cfg)


def _check_agent(db: Session, ctx: TenantContext, agent_id: uuid.UUID | None) -> uuid.UUID | None:
    if agent_id is None:
        return None
    from app.modules.agents.models import AIAgent

    ag = db.get(AIAgent, agent_id)
    if ag is None or ag.organization_id != ctx.organization_id:
        raise AppError(422, "unknown_agent", "Voice agent not found")
    return agent_id


def _check_wa_template(db, ctx, tid):
    if tid and not db.scalar(select(WhatsAppTemplate.id).where(
            WhatsAppTemplate.id == tid, WhatsAppTemplate.organization_id == ctx.organization_id)):
        raise AppError(422, "invalid_template", "WhatsApp template not found in this workspace")


def _detail(db: Session, c: Campaign) -> CampaignDetail:
    d = CampaignDetail.model_validate(c)
    cfg = _email_cfg(db, c)
    if cfg:
        d.email = EmailConfig(account_id=cfg.account_id, steps=cfg.steps, physical_address=cfg.physical_address,
                              website_preview_base_url=cfg.website_preview_base_url,
                              personalize_with_ai=cfg.personalize_with_ai)
    rows = db.execute(select(CampaignRecipient.status, func.count()).where(
        CampaignRecipient.campaign_id == c.id, CampaignRecipient.organization_id == c.organization_id)
        .group_by(CampaignRecipient.status)).all()
    d.recipient_counts = {s: n for s, n in rows}
    return d


@router.get("/campaigns", response_model=Page[CampaignOut])
def list_campaigns(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                   status: str | None = Query(None, max_length=20), channel: str | None = Query(None, max_length=20),
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(Campaign).where(Campaign.organization_id == ctx.organization_id)
    if status:
        base = base.where(Campaign.status == status)
    if channel:
        base = base.where(Campaign.channel == channel)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Campaign.created_at.desc(), Campaign.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[CampaignOut](items=[CampaignOut.model_validate(r) for r in rows], total=total, page=page,
                             page_size=page_size)


@router.post("/campaigns", response_model=CampaignDetail, status_code=201)
def create_campaign(body: CampaignCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    _check_wa_template(db, ctx, body.whatsapp_template_id)
    c = Campaign(organization_id=ctx.organization_id, name=body.name.strip(), channel=body.channel, status="draft",
                 spend_limit=body.spend_limit, cost_per_message=body.cost_per_message, spent=0,
                 send_window=body.send_window.model_dump() if body.send_window else None,
                 whatsapp_template_id=body.whatsapp_template_id, created_by_user_id=ctx.user.id,
                 voice_agent_id=_check_agent(db, ctx, body.voice_agent_id),
                 max_concurrent_calls=body.max_concurrent_calls)
    db.add(c)
    db.flush()
    if body.channel == "email":
        _apply_email(db, ctx, c, body.email or EmailConfig())
    svc.event(db, c, "campaign.created", {"channel": c.channel}, ctx.user.id)
    _audit(db, ctx, "campaign.create", c.id, request, {"channel": c.channel})
    db.commit()
    return _detail(db, c)


@router.get("/campaigns/{cid}", response_model=CampaignDetail)
def get_campaign(cid: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _detail(db, _campaign(db, ctx, cid))


@router.patch("/campaigns/{cid}", response_model=CampaignDetail)
def update_campaign(cid: uuid.UUID, body: CampaignPatch, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "draft")  # approved content is frozen; reject back to draft to edit
    changes = body.model_dump(exclude_unset=True, exclude={"email"})
    if "whatsapp_template_id" in changes:
        _check_wa_template(db, ctx, changes["whatsapp_template_id"])
    if "voice_agent_id" in changes:
        _check_agent(db, ctx, changes["voice_agent_id"])
    for k, v in changes.items():
        if k in {"name", "cost_per_message", "max_concurrent_calls"} and v is None:
            continue
        setattr(c, k, v)
    if body.email is not None and c.channel == "email":
        _apply_email(db, ctx, c, body.email)
    svc.event(db, c, "campaign.updated", {"fields": sorted(body.model_dump(exclude_unset=True))}, ctx.user.id)
    _audit(db, ctx, "campaign.update", c.id, request)
    db.commit()
    db.refresh(c)
    return _detail(db, c)


# ---------------------------------------------------------------- recipients
@router.post("/campaigns/{cid}/recipients")
def add_recipients(cid: uuid.UUID, body: RecipientsAdd, request: Request, ctx: TenantContext = Depends(WRITE),
                   db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "draft")
    q = select(Lead).where(Lead.organization_id == ctx.organization_id, Lead.deleted_at.is_(None))
    if body.lead_ids:
        q = q.where(Lead.id.in_(body.lead_ids))
    elif any([body.filter_status, body.filter_city, body.filter_industry, body.filter_country]):
        if body.filter_status:
            q = q.where(Lead.status.in_(body.filter_status))
        if body.filter_city:
            q = q.where(func.lower(Lead.city) == body.filter_city.lower())
        if body.filter_industry:
            q = q.where(func.lower(Lead.industry) == body.filter_industry.lower())
        if body.filter_country:
            q = q.where(Lead.country == body.filter_country.upper())
    else:
        raise AppError(422, "validation_error", "Provide lead_ids or at least one filter")
    leads = db.scalars(q.limit(5000)).all()
    existing = set(db.scalars(select(CampaignRecipient.lead_id).where(CampaignRecipient.campaign_id == c.id)))
    added = 0
    for lead in leads:
        if lead.id in existing:
            continue
        d = check_outreach(db, ctx.organization_id, lead.id, c.channel)  # preflight only; re-checked at send
        db.add(CampaignRecipient(organization_id=ctx.organization_id, campaign_id=c.id, lead_id=lead.id,
                                 status="pending", gate_allowed=d.allowed, gate_simulated=d.simulated,
                                 gate_reasons=d.reasons))
        added += 1
    svc.event(db, c, "recipients.added", {"added": added}, ctx.user.id)
    _audit(db, ctx, "campaign.recipients_add", c.id, request, {"added": added})
    db.commit()
    return {"added": added, "skipped": len(leads) - added, "not_found": max(0, len(body.lead_ids) - len(leads))}


@router.get("/campaigns/{cid}/recipients", response_model=Page[RecipientOut])
def list_recipients(cid: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    c = _campaign(db, ctx, cid)
    base = select(CampaignRecipient, Lead.business_name).join(Lead, Lead.id == CampaignRecipient.lead_id).where(
        CampaignRecipient.campaign_id == c.id, CampaignRecipient.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(CampaignRecipient).where(
        CampaignRecipient.campaign_id == c.id, CampaignRecipient.organization_id == ctx.organization_id)) or 0
    items = []
    for r, name in db.execute(base.order_by(CampaignRecipient.created_at, CampaignRecipient.id)
                              .offset((page - 1) * page_size).limit(page_size)).all():
        o = RecipientOut.model_validate(r)
        o.business_name = name
        items.append(o)
    return Page[RecipientOut](items=items, total=total, page=page, page_size=page_size)


@router.delete("/campaigns/{cid}/recipients/{lead_id}", status_code=204)
def remove_recipient(cid: uuid.UUID, lead_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                     db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "draft")
    r = db.scalar(select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id,
                                                  CampaignRecipient.lead_id == lead_id,
                                                  CampaignRecipient.organization_id == ctx.organization_id))
    if r is None:
        raise AppError(404, "not_found", "Recipient not found")
    db.delete(r)
    svc.event(db, c, "recipient.removed", {"lead_id": str(lead_id)}, ctx.user.id)
    db.commit()


# ---------------------------------------------------------------- lifecycle
@router.post("/campaigns/{cid}/submit", response_model=CampaignDetail)
def submit(cid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "draft")
    problems = []
    if not db.scalar(select(func.count()).select_from(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id)):
        problems.append("no_recipients")
    if c.channel == "email":
        cfg = _email_cfg(db, c)
        if cfg is None or not cfg.steps:
            problems.append("no_email_steps")
        if cfg is None or not (cfg.physical_address or "").strip():
            problems.append("physical_address_required")  # CAN-SPAM
    if c.channel == "whatsapp":
        t = db.get(WhatsAppTemplate, c.whatsapp_template_id) if c.whatsapp_template_id else None
        if t is None or t.status != "approved":
            problems.append("approved_whatsapp_template_required")
    if c.channel == "voice":
        from app.modules.agents.models import AIAgent

        ag = db.get(AIAgent, c.voice_agent_id) if c.voice_agent_id else None
        if ag is None or ag.organization_id != c.organization_id:
            problems.append("voice_agent_required")
        elif ag.status != "published":
            problems.append("voice_agent_not_published")
    if problems:
        raise AppError(422, "campaign_incomplete", "Campaign cannot be submitted", problems)
    c.status = "pending_approval"
    svc.event(db, c, "campaign.submitted", None, ctx.user.id)
    _audit(db, ctx, "campaign.submit", c.id, request)
    db.commit()
    return _detail(db, c)


@router.post("/campaigns/{cid}/approval", response_model=CampaignDetail)
def decide(cid: uuid.UUID, body: ApprovalIn, request: Request, ctx: TenantContext = Depends(APPROVE),
           db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "pending_approval")
    members = db.scalar(select(func.count()).select_from(OrganizationMembership).where(
        OrganizationMembership.organization_id == ctx.organization_id, OrganizationMembership.status == "active")) or 0
    self_approval = c.created_by_user_id == ctx.user.id
    if body.decision == "approved" and self_approval and members > 1:
        raise AppError(403, "four_eyes_required", "A different member must approve this campaign")
    db.add(CampaignApproval(organization_id=ctx.organization_id, campaign_id=c.id, approver_user_id=ctx.user.id,
                            decision=body.decision, note=body.note))
    if body.decision == "approved":
        c.status, c.approved_by_user_id, c.approved_at = "approved", ctx.user.id, utcnow()
    else:
        c.status = "draft"
    data = {"note": body.note, "self_approval_single_member": self_approval and body.decision == "approved"}
    svc.event(db, c, f"campaign.{body.decision}", data, ctx.user.id)
    _audit(db, ctx, f"campaign.{body.decision}", c.id, request, data)
    db.commit()
    return _detail(db, c)


@router.get("/campaigns/{cid}/approvals", response_model=list[ApprovalOut])
def approvals(cid: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    return db.scalars(select(CampaignApproval).where(CampaignApproval.campaign_id == c.id,
                                                     CampaignApproval.organization_id == ctx.organization_id)
                      .order_by(CampaignApproval.created_at)).all()


@router.post("/campaigns/{cid}/start")
def start(cid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db),
          idempotency_key: str | None = Header(default=None, max_length=128)):
    if not idempotency_key or not idempotency_key.strip():
        raise AppError(400, "idempotency_key_required", "Idempotency-Key header is required")
    req_hash = hashlib.sha256(f"campaign.start:{cid}".encode()).hexdigest()
    prior = db.scalar(select(IdempotencyKey).where(IdempotencyKey.organization_id == ctx.organization_id,
                                                   IdempotencyKey.key == idempotency_key))
    if prior is not None:
        if prior.request_hash != req_hash:
            raise AppError(409, "idempotency_conflict", "Idempotency-Key was used for a different request")
        return {**(prior.response or {}), "replayed": True}
    c = _campaign(db, ctx, cid)
    _require_status(c, "approved", "paused")
    resumed = c.status == "paused"
    if not resumed:  # only the first start of a campaign counts against the monthly email_campaigns limit
        billing.enforce_limit(db, ctx.organization_id, "email_campaigns")
        billing.record_usage(db, ctx.organization_id, "email_campaigns", 1, 0, campaign_id=c.id,
                             meta={"campaign_id": str(c.id)})
    c.status = "running"
    c.started_at = c.started_at or utcnow()
    svc.event(db, c, "campaign.resumed" if resumed else "campaign.started", None, ctx.user.id)
    counts = svc.process_due(db, c, ctx.user.id)
    response = {"campaign_id": str(c.id), "status": c.status, "dispatched": counts}
    db.add(IdempotencyKey(organization_id=ctx.organization_id, key=idempotency_key, request_hash=req_hash,
                          response=response))
    _audit(db, ctx, "campaign.start", c.id, request, {"dispatched": counts})
    try:
        db.commit()
    except IntegrityError as e:  # concurrent duplicate request
        db.rollback()
        raise AppError(409, "idempotency_conflict", "Request already in progress") from e
    return {**response, "replayed": False}


@router.post("/campaigns/{cid}/tick")
def tick(cid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    """Process due follow-up steps synchronously (Celery beat will call the same service later)."""
    c = _campaign(db, ctx, cid)
    _require_status(c, "running")
    counts = svc.process_due(db, c, ctx.user.id)
    _audit(db, ctx, "campaign.tick", c.id, request, {"dispatched": counts})
    db.commit()
    return {"campaign_id": str(c.id), "status": c.status, "dispatched": counts}


@router.post("/campaigns/{cid}/pause", response_model=CampaignDetail)
def pause(cid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "running")
    c.status = "paused"
    svc.event(db, c, "campaign.paused", None, ctx.user.id)
    _audit(db, ctx, "campaign.pause", c.id, request)
    db.commit()
    return _detail(db, c)


@router.post("/campaigns/{cid}/cancel", response_model=CampaignDetail)
def cancel(cid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    c = _campaign(db, ctx, cid)
    _require_status(c, "draft", "pending_approval", "approved", "running", "paused")
    c.status = "cancelled"
    for r in db.scalars(select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id,
                                                        CampaignRecipient.next_due_at.is_not(None))):
        r.next_due_at = None
    svc.event(db, c, "campaign.cancelled", None, ctx.user.id)
    _audit(db, ctx, "campaign.cancel", c.id, request)
    db.commit()
    return _detail(db, c)


@router.get("/campaigns/{cid}/events", response_model=Page[EventOut])
def events(cid: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
           page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
    c = _campaign(db, ctx, cid)
    base = select(CampaignEvent).where(CampaignEvent.campaign_id == c.id,
                                       CampaignEvent.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(CampaignEvent.created_at.desc(), CampaignEvent.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[EventOut](items=[EventOut.model_validate(r) for r in rows], total=total, page=page,
                          page_size=page_size)
