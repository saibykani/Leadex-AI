"""Pipeline orchestration and outcome persistence.

`run_pipeline` is idempotent: one PipelineRun per (org, business). Re-running reuses the lead, website project and
call already created; each step records `status` (done | skipped | blocked | failed | not_requested) and a message.
Nothing is faked: a blocked call returns the exact compliance reasons plus how to fix them.
"""
import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit
from app.modules.crm import service as crm
from app.modules.crm.models import Lead, LeadNote
from app.modules.discovery import service as discovery
from app.modules.pipeline import extraction, photos
from app.modules.pipeline.models import BusinessImage, ConversationOutcome, PipelineRun, PipelineSettings

FIX_HINTS = {
    "no_consent_reference": "Record the prospect's consent (consent reference) on the lead before calling.",
    "lead_status_not_eligible": "Move the lead to 'approved_for_outreach' (requires a consent reference).",
    "jurisdiction_unknown": "Set the lead's country so calling rules for that jurisdiction can be checked.",
    "agent_not_published": "Publish the agent (Agents → your agent → Publish).",
    "agent_killed": "Reactivate the agent; it was stopped with the kill switch.",
    "global_kill_switch": "An administrator has enabled the global voice kill switch (VOICE_KILL_SWITCH).",
    "language_evaluation_pending": "Record a passing language evaluation for the agent's language.",
    "language_unsupported": "Choose a supported agent language.",
    "telephony_not_configured": "Configure a telephony provider (e.g. LiveKit SIP + carrier). None is "
                                "integrated yet, so real phone calls cannot be placed.",
    "suppressed": "This number/email is on the suppression list; it must not be contacted.",
}


def hint(reason: str) -> str:
    key = reason.split(":", 1)[0]
    for k, v in FIX_HINTS.items():
        if key == k or key.startswith(k):
            return v
    return "See Compliance settings for this rule."


# ------------------------------------------------------------------ settings / packages
def get_settings_row(db: Session, org_id: uuid.UUID) -> PipelineSettings | None:
    return db.scalar(select(PipelineSettings).where(PipelineSettings.organization_id == org_id))


def packages_text(packages: list[dict]) -> str:
    if not packages:
        from app.modules.agents.templates import BUDGET_DISCOVERY_NO_PRICES

        return BUDGET_DISCOVERY_NO_PRICES
    rows = [f"- {p['name']}: {p.get('currency', '')} {p['min']:,.0f}–{p['max']:,.0f}"
            + (f" ({p['description']})" if p.get("description") else "") for p in packages]
    return ("Website packages configured by our team (quote ONLY these ranges; never invent other prices; final "
            "price is confirmed by a specialist):\n" + "\n".join(rows))


# ------------------------------------------------------------------ outcomes
def save_outcome(db: Session, ctx: TenantContext, o: extraction.Outcome, *, transcript: list[dict], source: str,
                 lead: Lead | None, agent_id=None, call_id=None, simulated=False) -> ConversationOutcome:
    row = ConversationOutcome(
        organization_id=ctx.organization_id, lead_id=lead.id if lead else None, agent_id=agent_id, call_id=call_id,
        source=source, extraction_mode=o.extraction_mode, model=o.model, interest=o.interest,
        budget_min=o.budget_min, budget_max=o.budget_max, budget_currency=o.budget_currency,
        budget_evidence=o.budget_evidence, timeline=o.timeline, timeline_evidence=o.timeline_evidence,
        decision_maker=o.decision_maker, decision_maker_evidence=o.decision_maker_evidence,
        objections=o.objections, next_step=o.next_step, summary=o.summary or "", transcript=transcript[:200],
        simulated=simulated, created_by=ctx.user.id)
    db.add(row)
    db.flush()
    if call_id is not None:
        from app.modules.voice.models import CallSummary

        db.add(CallSummary(organization_id=ctx.organization_id, call_id=call_id, simulated=simulated,
                           summary=f"[{o.extraction_mode}] {o.summary}"))
    if lead is not None:
        write_to_lead(db, ctx, lead, row)
    return row


def write_to_lead(db: Session, ctx: TenantContext, lead: Lead, row: ConversationOutcome) -> None:
    data = {"outcome_id": str(row.id), "interest": row.interest, "extraction_mode": row.extraction_mode,
            "budget_min": float(row.budget_min) if row.budget_min is not None else None,
            "budget_max": float(row.budget_max) if row.budget_max is not None else None,
            "budget_currency": row.budget_currency, "timeline": row.timeline, "next_step": row.next_step,
            "source": row.source}
    crm.record_activity(db, ctx, lead, "conversation.outcome", data)
    lines = [f"Conversation outcome ({row.source}, extraction: {row.extraction_mode})", row.summary]
    if row.budget_evidence:
        lines.append(f'Budget evidence: "{row.budget_evidence}"')
    if row.timeline_evidence:
        lines.append(f'Timeline evidence: "{row.timeline_evidence}"')
    db.add(LeadNote(organization_id=ctx.organization_id, lead_id=lead.id, author_user_id=ctx.user.id,
                    body="\n".join(lines)))
    cf = dict(lead.custom_fields or {})
    if data["budget_min"] is not None or data["budget_max"] is not None:
        cf["budget"] = {"min": data["budget_min"], "max": data["budget_max"], "currency": row.budget_currency,
                        "evidence": row.budget_evidence, "outcome_id": str(row.id)}
    if row.timeline:
        cf["timeline"] = row.timeline
    cf["last_interest"] = row.interest
    lead.custom_fields = cf  # reassign so the JSON change is persisted


# ------------------------------------------------------------------ pipeline run
def _step(run: PipelineRun, key: str, status: str, message: str = "", **data) -> None:
    steps = [s for s in (run.steps or []) if s.get("key") != key]
    steps.append({"key": key, "status": status, "message": message, "at": utcnow().isoformat(), **data})
    order = ["business", "photos", "lead", "website", "agent", "call"]
    run.steps = sorted(steps, key=lambda s: order.index(s["key"]) if s["key"] in order else 99)


def _app_error(e: AppError) -> dict:
    return {"code": e.code, "detail": e.message, "status_code": e.status_code}


def run_pipeline(db: Session, ctx: TenantContext, body, request: Request | None) -> PipelineRun:
    from app.modules.discovery.router import convert_to_lead
    from app.modules.websites.models import WebsiteProject
    from app.modules.websites.router import generate as generate_website
    from app.modules.websites.schemas import GenerateIn

    ctx.require("businesses:write")
    ctx.require("leads:write")
    biz = discovery.get_business(db, ctx, body.business_id)
    run = db.scalar(select(PipelineRun).where(PipelineRun.organization_id == ctx.organization_id,
                                              PipelineRun.business_id == biz.id))
    if run is None:
        run = PipelineRun(organization_id=ctx.organization_id, business_id=biz.id, steps=[], created_by=ctx.user.id)
        db.add(run)
        db.flush()
    run.status = "running"
    _step(run, "business", "done", biz.name or "(name expired)", simulated=biz.is_simulated)
    g = photos.list_photo_refs(db, ctx.organization_id, biz.id)
    approved = db.scalars(select(BusinessImage.id).where(
        BusinessImage.business_id == biz.id, BusinessImage.organization_id == ctx.organization_id,
        BusinessImage.status == "approved", BusinessImage.permission_confirmed.is_(True))).all()
    _step(run, "photos", "done", f"{len(g)} Google photo(s) for review only; {len(approved)} approved image(s) "
                                 "usable in the website", google=len(g), approved=len(approved))
    db.commit()

    # lead
    lead = db.get(Lead, biz.lead_id) if biz.lead_id else None
    if lead is not None and lead.deleted_at is None:
        run.lead_id = lead.id
        _step(run, "lead", "skipped", "Already converted", lead_id=str(lead.id))
    else:
        try:
            out = convert_to_lead(biz.id, request, ctx, db)
            run.lead_id = out.lead_id
            _step(run, "lead", "done", "Converted to lead", lead_id=str(out.lead_id))
        except AppError as e:
            db.rollback()
            _step(run, "lead", "failed", e.message, error=_app_error(e))
            run.status = "failed"
            db.commit()
            return run
    db.commit()

    # website
    proj = db.get(WebsiteProject, run.website_project_id) if run.website_project_id else None
    if not body.generate_website:
        _step(run, "website", "not_requested", "Website generation not requested")
    elif proj is not None:
        _step(run, "website", "skipped", "Website demo already generated", website_id=str(proj.id),
              preview_path=f"/api/v1/public/preview/{proj.preview_token}")
    else:
        try:
            ctx.require("websites:write")
            gi = GenerateIn(template_key=body.template_key, lead_id=run.lead_id, business_id=biz.id,
                            use_ai=body.use_ai, images=list(body.image_ids or []))
            detail = generate_website(gi, request, ctx, db)
            run.website_project_id = detail.id
            _step(run, "website", "done", f"Generated with {len(body.image_ids or [])} approved image(s)"
                  + ("" if body.image_ids else " (styled no-photo design)"), website_id=str(detail.id),
                  preview_path=detail.preview_path, generation_mode=detail.generation_mode)
        except AppError as e:
            db.rollback()
            _step(run, "website", "failed", e.message, error=_app_error(e))
    db.commit()

    # agent + call
    if body.agent_id:
        from app.modules.agents import service as agents

        try:
            agent = agents.get_agent(db, ctx, body.agent_id)
            run.agent_id = agent.id
            _step(run, "agent", "done", agent.name, agent_id=str(agent.id), agent_status=agent.status)
        except AppError as e:
            _step(run, "agent", "failed", e.message, error=_app_error(e))
            agent = None
    else:
        agent = None
        _step(run, "agent", "not_requested", "No agent chosen")
    if not body.place_call:
        _step(run, "call", "not_requested", "Call not requested. Use 'Talk to it yourself' for a browser test.")
    elif agent is None:
        _step(run, "call", "failed", "Choose an agent before calling")
    elif run.call_id is not None and _call_status(db, run.call_id) not in (None, "blocked", "not_configured"):
        _step(run, "call", "skipped", "A call was already placed for this pipeline", call_id=str(run.call_id),
              call_status=_call_status(db, run.call_id))
    else:
        _place_call(db, ctx, run, agent, request)
    statuses = {s["status"] for s in run.steps}
    run.status = "failed" if "failed" in statuses else ("needs_action" if "blocked" in statuses else "completed")
    audit(db, "pipeline.run", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="pipeline_run",
          entity_id=run.id, request=request, data={"status": run.status})
    db.commit()
    return run


def _call_status(db: Session, call_id) -> str | None:
    from app.modules.voice.models import CallSession

    c = db.get(CallSession, call_id)
    return c.status if c else None


def _place_call(db: Session, ctx: TenantContext, run: PipelineRun, agent, request) -> None:
    """Same path as POST /calls: agent blockers + compliance OutreachGate + billing; simulated outside production."""
    from app.modules.billing import service as billing
    from app.modules.voice import service as voice
    from app.modules.voice.schemas import CallCreate

    try:
        ctx.require("calls:initiate")
        billing.enforce_limit(db, ctx.organization_id, "voice_minutes", 1)
    except AppError as e:
        _step(run, "call", "blocked", e.message, error=_app_error(e), reasons=[e.code], fixes=[e.message])
        return
    # A blocked attempt may be retried after fixing; a placed/simulated call is never repeated (see run_pipeline).
    call = voice.place_call(db, ctx, CallCreate(lead_id=run.lead_id, agent_id=agent.id), agent,
                            f"pipeline-{run.id}-{uuid.uuid4().hex[:8]}")
    db.flush()
    run.call_id = call.id
    if call.status in ("blocked", "not_configured"):
        reasons = call.gate_reasons or []
        _step(run, "call", "blocked", "Call not placed: blocked by compliance / configuration checks",
              call_id=str(call.id), call_status=call.status, reasons=reasons, fixes=[hint(r) for r in reasons])
    else:
        billing.record_usage(db, ctx.organization_id, "voice_minutes", round((call.duration_s or 0) / 60, 2), 0,
                             lead_id=call.lead_id, meta={"call_id": str(call.id), "simulated": call.simulated,
                                                         "status": call.status, "via": "pipeline"})
        msg = ("SIMULATED: the compliance gate allowed the call, but no telephony provider is used outside "
               "production, so nobody was contacted and there is no conversation to analyse."
               if call.simulated else "Call placed")
        _step(run, "call", "done", msg, call_id=str(call.id), call_status=call.status, simulated=call.simulated)


def latest_outcome(db: Session, org_id: uuid.UUID, lead_id) -> ConversationOutcome | None:
    if lead_id is None:
        return None
    return db.scalars(select(ConversationOutcome).where(ConversationOutcome.organization_id == org_id,
                                                        ConversationOutcome.lead_id == lead_id)
                      .order_by(ConversationOutcome.created_at.desc()).limit(1)).first()


def require_lead(db: Session, ctx: TenantContext, lead_id) -> Lead:
    return crm.get_lead(db, ctx, lead_id)


def not_found(what: str) -> AppError:
    return AppError(404, "not_found", f"{what} not found")
