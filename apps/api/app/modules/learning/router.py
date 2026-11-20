import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.agents.models import AIAgent
from app.modules.learning import service as svc
from app.modules.learning.models import ScriptVariant
from app.modules.voice.models import CallSession

router = APIRouter(tags=["learning"])
READ = require_permission("agents:read")
WRITE = require_permission("agents:write")


class VariantIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    opening: str = Field(min_length=5, max_length=600)


class VariantPatch(BaseModel):
    active: bool


class Feedback(BaseModel):
    good: bool
    note: str | None = Field(default=None, max_length=1000)


def _agent(db: Session, ctx: TenantContext, agent_id: uuid.UUID) -> AIAgent:
    a = db.scalar(select(AIAgent).where(AIAgent.id == agent_id, AIAgent.organization_id == ctx.organization_id))
    if a is None:
        raise AppError(404, "not_found", "Agent not found")
    return a


@router.get("/agents/{agent_id}/learning")
def learning_stats(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    _agent(db, ctx, agent_id)
    return svc.stats(db, ctx.organization_id, agent_id)


@router.post("/agents/{agent_id}/variants", status_code=201)
def add_variant(agent_id: uuid.UUID, body: VariantIn, request: Request, ctx: TenantContext = Depends(WRITE),
                db: Session = Depends(get_db)):
    _agent(db, ctx, agent_id)
    v = ScriptVariant(organization_id=ctx.organization_id, agent_id=agent_id, name=body.name.strip(),
                      opening=body.opening.strip(), created_by_user_id=ctx.user.id)
    db.add(v)
    db.flush()
    audit(db, "agent.variant_create", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="script_variant",
          entity_id=v.id, request=request)
    db.commit()
    return {"id": v.id}


@router.patch("/agents/{agent_id}/variants/{variant_id}")
def toggle_variant(agent_id: uuid.UUID, variant_id: uuid.UUID, body: VariantPatch, request: Request,
                   ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    v = db.scalar(select(ScriptVariant).where(ScriptVariant.id == variant_id, ScriptVariant.agent_id == agent_id,
                                              ScriptVariant.organization_id == ctx.organization_id))
    if v is None:
        raise AppError(404, "not_found", "Variant not found")
    v.active = body.active
    audit(db, "agent.variant_toggle", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="script_variant",
          entity_id=v.id, data={"active": body.active}, request=request)
    db.commit()
    return {"id": v.id, "active": v.active}


@router.post("/calls/{call_id}/feedback")
def call_feedback(call_id: uuid.UUID, body: Feedback, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    call = db.scalar(select(CallSession).where(CallSession.id == call_id,
                                               CallSession.organization_id == ctx.organization_id))
    if call is None:
        raise AppError(404, "not_found", "Call not found")
    row = svc.human_feedback(db, ctx.organization_id, call, body.good, body.note)
    audit(db, "call.feedback", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="call",
          entity_id=call.id, data={"good": body.good}, request=request)
    db.commit()
    return {"reward": row.reward, "label": row.label}
