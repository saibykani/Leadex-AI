"""Campaign orchestration. Every recipient send passes the OutreachGate (via communication.service)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.campaigns.models import Campaign, CampaignEvent, CampaignRecipient
from app.modules.communication import service as comm
from app.modules.communication.models import (
    EmailAccount,
    EmailCampaign,
    EmailTemplate,
    WhatsAppAccount,
    WhatsAppTemplate,
)
from app.modules.compliance.gate import check_outreach
from app.modules.crm.models import Lead

ACTIVE = {"approved", "running", "paused"}
OPEN_RECIPIENT = {"pending", "sent", "simulated"}


def event(db: Session, c: Campaign, type_: str, data: dict | None = None, actor: uuid.UUID | None = None) -> None:
    db.add(CampaignEvent(organization_id=c.organization_id, campaign_id=c.id, actor_user_id=actor, type=type_,
                         data=data))


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


def _stop_lead(db: Session, org_id: uuid.UUID, lead_id: uuid.UUID, status: str, source: str) -> None:
    rows = db.execute(select(CampaignRecipient, Campaign).join(Campaign, Campaign.id == CampaignRecipient.campaign_id)
                      .where(CampaignRecipient.organization_id == org_id, CampaignRecipient.lead_id == lead_id,
                             Campaign.status.in_(ACTIVE | {"draft", "pending_approval"}))).all()
    for r, c in rows:
        if r.status in {"unsubscribed", "replied"} and status == "replied":
            continue
        r.status, r.next_due_at = status, None
        event(db, c, f"recipient.{status}", {"lead_id": str(lead_id), "source": source})


def mark_lead_unsubscribed(db: Session, org_id: uuid.UUID, lead_id: uuid.UUID, source: str) -> None:
    _stop_lead(db, org_id, lead_id, "unsubscribed", source)


def mark_lead_replied(db: Session, org_id: uuid.UUID, lead_id: uuid.UUID) -> None:
    """A reply stops the follow-up sequence for that lead."""
    _stop_lead(db, org_id, lead_id, "replied", "inbound_reply")


def in_window(c: Campaign, now: datetime) -> bool:
    w = c.send_window or {}
    if "start_hour" not in w or "end_hour" not in w:
        return True
    s, e, h = int(w["start_hour"]), int(w["end_hour"]), now.hour
    return s <= h < e if s <= e else (h >= s or h < e)


def _preview_url(cfg: EmailCampaign | None, lead: Lead) -> str:
    custom = (lead.custom_fields or {}).get("website_preview_url") if isinstance(lead.custom_fields, dict) else None
    if custom:
        return str(custom)
    if cfg and cfg.website_preview_base_url:
        return cfg.website_preview_base_url.replace("{lead_id}", str(lead.id))
    return ""


def _dispatch(db: Session, c: Campaign, r: CampaignRecipient, lead: Lead, cfg: EmailCampaign | None) -> str:
    decision = check_outreach(db, c.organization_id, lead.id, c.channel)
    r.gate_allowed, r.gate_simulated, r.gate_reasons = decision.allowed, decision.simulated, list(decision.reasons)
    if c.channel == "email":
        step = cfg.steps[r.current_step]
        tpl = db.scalar(select(EmailTemplate).where(EmailTemplate.organization_id == c.organization_id,
                                                    EmailTemplate.id == uuid.UUID(str(step["template_id"]))))
        if tpl is None:
            r.status, r.gate_reasons = "failed", ["template_missing"]
            return r.status
        values = comm.lead_values(lead, {"website_preview_url": _preview_url(cfg, lead)})
        text = comm.render(tpl.text or "", values, escape=False)
        if cfg.personalize_with_ai and decision.allowed:
            text = comm.personalize(text, lead)
        account = db.get(EmailAccount, cfg.account_id) if cfg.account_id else None
        res = comm.send_email(db, org_id=c.organization_id, lead=lead, account=account,
                              subject=comm.render(tpl.subject, values, escape=False),
                              body_html=comm.render(tpl.html, values, escape=True), body_text=text,
                              physical_address=cfg.physical_address, campaign_id=c.id, step_index=r.current_step,
                              decision=decision)
        status, reasons = res.status, res.reasons
    elif c.channel == "whatsapp":
        tpl = db.get(WhatsAppTemplate, c.whatsapp_template_id) if c.whatsapp_template_id else None
        account = db.scalar(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == c.organization_id)
                            .order_by(WhatsAppAccount.created_at).limit(1))
        if not lead.phone_normalized:
            status, reasons = "blocked", list(decision.reasons) or ["no_phone_number"]
        else:
            conv = comm.get_conversation(db, c.organization_id, lead.phone_normalized, account, lead)
            if conv.lead_id is None:
                conv.lead_id = lead.id
            msg = comm.send_whatsapp(db, org_id=c.organization_id, conv=conv, account=account, template=tpl,
                                     variables=[lead.business_name], campaign_id=c.id, decision=decision)
            status, reasons = msg.status, list(msg.gate_reasons or [])
    else:  # voice: a call through the voice module, which re-runs every compliance check itself
        status, reasons = _dispatch_call(db, c, r, lead)
    r.gate_reasons = reasons
    r.status = status
    r.last_sent_at = utcnow()
    if status == "sent" and c.cost_per_message:
        c.spent = Decimal(c.spent or 0) + Decimal(c.cost_per_message)
    return status


ACTIVE_CALL = ("queued", "initiated", "ringing", "in_progress")
CALL_STATUS_MAP = {"initiated": "sent", "ringing": "sent", "in_progress": "sent",
                   "simulated_completed": "simulated", "blocked": "blocked"}


def active_calls(db: Session, c: Campaign) -> int:
    from app.modules.voice.models import CallSession

    return db.scalar(select(func.count()).select_from(CallSession).where(
        CallSession.organization_id == c.organization_id, CallSession.campaign_id == c.id,
        CallSession.status.in_(ACTIVE_CALL))) or 0


def _dispatch_call(db: Session, c: Campaign, r: CampaignRecipient, lead: Lead) -> tuple[str, list]:
    from types import SimpleNamespace

    from app.modules.agents.models import AIAgent
    from app.modules.voice import service as voice
    from app.modules.voice.schemas import CallCreate

    agent = db.get(AIAgent, c.voice_agent_id) if c.voice_agent_id else None
    if agent is None or agent.organization_id != c.organization_id:
        return "failed", ["voice_agent_missing"]
    ctx = SimpleNamespace(organization_id=c.organization_id, user=SimpleNamespace(id=c.created_by_user_id))
    call = voice.place_call(db, ctx, CallCreate(lead_id=lead.id, agent_id=agent.id), agent,
                            f"campaign:{c.id}:{r.id}:{r.current_step}")
    call.campaign_id = c.id
    return CALL_STATUS_MAP.get(call.status, "failed"), list(call.gate_reasons or []) + [f"call:{call.id}"]


def process_due(db: Session, c: Campaign, actor: uuid.UUID | None, now: datetime | None = None) -> dict:
    """Send every due step (initial sends and follow-ups). Synchronous stand-in for the Celery worker."""
    now = now or utcnow()
    counts: dict[str, int] = {}
    if c.status != "running":
        return counts
    if not in_window(c, now):
        event(db, c, "tick.outside_send_window", {"at": now.isoformat()}, actor)
        return counts
    cfg = db.scalar(select(EmailCampaign).where(EmailCampaign.campaign_id == c.id)) if c.channel == "email" else None
    rows = db.scalars(select(CampaignRecipient).where(
        CampaignRecipient.organization_id == c.organization_id, CampaignRecipient.campaign_id == c.id,
        CampaignRecipient.status.in_(OPEN_RECIPIENT)).order_by(CampaignRecipient.created_at, CampaignRecipient.id)
    ).all()
    call_slots = max(0, (c.max_concurrent_calls or 1) - active_calls(db, c)) if c.channel == "voice" else None
    for r in rows:
        if r.status != "pending" and (r.next_due_at is None or _aware(r.next_due_at) > now):
            continue
        if call_slots is not None:
            if call_slots <= 0:  # concurrency cap reached: the rest wait for the next tick
                event(db, c, "tick.concurrency_limit", {"max_concurrent_calls": c.max_concurrent_calls}, actor)
                break
            call_slots -= 1
        if c.spend_limit is not None and c.cost_per_message and \
                Decimal(c.spent or 0) + Decimal(c.cost_per_message) > Decimal(c.spend_limit):
            c.status = "paused"
            event(db, c, "campaign.paused_spend_limit", {"spent": str(c.spent), "limit": str(c.spend_limit)}, actor)
            break
        lead = db.get(Lead, r.lead_id)
        if lead is None or lead.deleted_at is not None:
            r.status, r.gate_reasons, r.next_due_at = "blocked", ["lead_not_found"], None
            continue
        status = _dispatch(db, c, r, lead, cfg)
        counts[status] = counts.get(status, 0) + 1
        steps = cfg.steps if cfg else [{}]
        if status in {"sent", "simulated"} and r.current_step + 1 < len(steps):
            r.current_step += 1
            r.next_due_at = now + timedelta(hours=int(steps[r.current_step].get("delay_hours", 24)))
        else:
            r.next_due_at = None
        event(db, c, "recipient.dispatched", {"lead_id": str(r.lead_id), "status": status,
                                              "step": r.current_step, "reasons": r.gate_reasons}, actor)
    db.flush()
    remaining = db.scalar(select(func.count()).select_from(CampaignRecipient).where(
        CampaignRecipient.campaign_id == c.id, CampaignRecipient.organization_id == c.organization_id,
        (CampaignRecipient.status == "pending") | CampaignRecipient.next_due_at.is_not(None))) or 0
    if c.status == "running" and remaining == 0:
        c.status, c.completed_at = "completed", now
        event(db, c, "campaign.completed", {"counts": counts}, actor)
    return counts
