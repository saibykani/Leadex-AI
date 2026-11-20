import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.agents import service as agents
from app.modules.billing import service as billing
from app.modules.crm import service as crm
from app.modules.identity.models import IdempotencyKey
from app.modules.identity.schemas import Page
from app.modules.voice import service as svc
from app.modules.voice import telephony
from app.modules.voice.models import (
    CallDisposition,
    CallEvent,
    CallRecording,
    CallSession,
    CallSummary,
    CallTranscript,
)
from app.modules.voice.schemas import CallCreate, CallDetail, CallOut, TelephonyStatusOut
from app.modules.voice.webhooks import public_router

router = APIRouter(tags=["voice"])
extra_routers = [public_router]
READ = require_permission("agents:read")
INITIATE = require_permission("calls:initiate")


@router.post("/calls", status_code=201, response_model=CallOut,
             responses={422: {"description": "Blocked by compliance gate (call_blocked)"}})
def create_call(body: CallCreate, request: Request, ctx: TenantContext = Depends(INITIATE),
                db: Session = Depends(get_db),
                idempotency_key: str | None = Header(default=None, max_length=128)):
    if not idempotency_key or not idempotency_key.strip():
        raise AppError(400, "idempotency_key_required", "Idempotency-Key header is required for calls")
    key = idempotency_key.strip()
    req_hash = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    prior = db.scalar(select(IdempotencyKey).where(IdempotencyKey.organization_id == ctx.organization_id,
                                                   IdempotencyKey.key == key))
    if prior is not None:
        if prior.request_hash != req_hash:
            raise AppError(409, "idempotency_key_reused", "Idempotency-Key was used with a different request")
        resp = prior.response or {}
        return JSONResponse(status_code=resp.get("status_code", 200), content=resp.get("body"),
                            headers={"Idempotent-Replay": "true"})
    crm.get_lead(db, ctx, body.lead_id)  # 404 across tenants
    agent = agents.get_agent(db, ctx, body.agent_id)
    billing.enforce_limit(db, ctx.organization_id, "voice_minutes", 1)  # need at least one minute of headroom
    call = svc.place_call(db, ctx, body, agent, key)
    db.flush()
    if call.status not in ("blocked", "not_configured") and call.provider == "simulated":
        # Real (Twilio) calls are billed from the provider status callback with actual minutes.
        # Simulated calls are recorded with 0 minutes so they are visible in usage without consuming quota.
        billing.record_usage(db, ctx.organization_id, "voice_minutes", round((call.duration_s or 0) / 60, 2), 0,
                             lead_id=call.lead_id, meta={"call_id": str(call.id), "simulated": call.simulated,
                                                         "status": call.status})
    out = CallOut.model_validate(call).model_dump(mode="json")
    if call.status == "blocked":
        status, content = 422, {"error": {"code": "call_blocked", "message": "Call blocked by compliance checks",
                                          "details": {"call_id": out["id"], "reasons": call.gate_reasons,
                                                      "call": out}}}
    else:
        status, content = 201, out
    db.add(IdempotencyKey(organization_id=ctx.organization_id, key=key, request_hash=req_hash,
                          response={"status_code": status, "body": content}))
    audit(db, "call.create", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="call_session",
          entity_id=call.id, request=request,
          data={"status": call.status, "reasons": call.gate_reasons, "simulated": call.simulated})
    db.commit()
    return JSONResponse(status_code=status, content=content)


@router.get("/calls", response_model=Page[CallOut])
def list_calls(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db), page: int = Query(1, ge=1),
               page_size: int = Query(25, ge=1, le=100), status: str | None = Query(None, max_length=30),
               lead_id: uuid.UUID | None = None, agent_id: uuid.UUID | None = None):
    base = select(CallSession).where(CallSession.organization_id == ctx.organization_id)
    if status:
        base = base.where(CallSession.status == status)
    if lead_id:
        base = base.where(CallSession.lead_id == lead_id)
    if agent_id:
        base = base.where(CallSession.agent_id == agent_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(CallSession.created_at.desc(), CallSession.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[CallOut](items=[CallOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/calls/{call_id}", response_model=CallDetail)
def get_call(call_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    org = ctx.organization_id
    call = db.scalar(select(CallSession).where(CallSession.id == call_id, CallSession.organization_id == org))
    if call is None:
        raise AppError(404, "not_found", "Call not found")

    def rows(model, order):
        return db.scalars(select(model).where(model.call_id == call.id, model.organization_id == org)
                          .order_by(order)).all()

    def last(model):
        return db.scalars(select(model).where(model.call_id == call.id, model.organization_id == org)
                          .order_by(model.created_at.desc()).limit(1)).first()

    from app.modules.pipeline.models import ConversationOutcome

    data = CallOut.model_validate(call).model_dump()
    return CallDetail.model_validate({
        **data, "events": rows(CallEvent, CallEvent.created_at), "transcript": rows(CallTranscript, CallTranscript.seq),
        "summary": last(CallSummary), "disposition": last(CallDisposition), "recording": last(CallRecording),
        "outcome": last(ConversationOutcome),
    }, from_attributes=True)


@router.get("/telephony/status", response_model=TelephonyStatusOut)
def telephony_status(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    from app.core.config import get_settings

    st = telephony.adapter_for(db, ctx.organization_id).status()
    ts = telephony.telephony_settings()
    prod = get_settings().is_production
    if st.status != "configured":
        mode = st.status
    elif prod:
        mode = "live"
    elif ts.allow_test_calls and ts.allowlist:
        mode = "test_allowlist"
    else:
        mode = "simulated"
    return TelephonyStatusOut(
        provider=st.provider, status=st.status, mode=mode, detail=st.detail, credential_source=st.credential_source,
        from_number=st.from_number, public_base_url=st.public_base_url, app_env=get_settings().app_env,
        allow_test_calls=ts.allow_test_calls, test_allowlist=sorted(ts.allowlist),
        voice_webhook_example=telephony.webhook_url("voice", uuid.UUID(int=0)) if st.public_base_url else None)



@router.get("/voices")
def list_voices(ctx: TenantContext = Depends(READ)):
    """Voices the phone agent can speak with. Female voices are the defaults for each language."""
    from app.modules.voice import telephony as tel

    return {"items": tel.VOICES, "defaults": tel._DEFAULT_VOICES}
