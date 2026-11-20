import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.agents import llm, rag
from app.modules.agents import service as svc
from app.modules.agents.models import (
    AgentEvaluation,
    AgentKnowledge,
    AgentLog,
    AgentRun,
    AgentVersion,
    AIAgent,
    KnowledgeChunk,
    ModelConfiguration,
)
from app.modules.agents.orchestrator import build_turn_graph
from app.modules.agents.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    EvaluationIn,
    EvaluationOut,
    FromTemplate,
    KnowledgeIn,
    KnowledgeOut,
    ModelConfigIn,
    ModelConfigOut,
    RunOut,
    TestRequest,
    TestResponse,
    VersionOut,
)
from app.modules.agents.templates import TEMPLATES, TEMPLATES_BY_KEY
from app.modules.agents.tools import TOOLS, ToolEnv
from app.modules.billing import service as billing
from app.modules.identity.schemas import Page

router = APIRouter(tags=["agents"])
READ = require_permission("agents:read")
WRITE = require_permission("agents:write")


def _audit(db, ctx: TenantContext, action: str, entity_type: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=entity_type,
          entity_id=entity_id, data=data, request=request)


# ------------------------------------------------------------------ catalog / providers
@router.get("/ai/providers")
def providers(_: TenantContext = Depends(READ)):
    return {"providers": llm.provider_status()}


@router.get("/ai/model-configs", response_model=list[ModelConfigOut])
def list_model_configs(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(ModelConfiguration).where(ModelConfiguration.organization_id == ctx.organization_id)
                      .order_by(ModelConfiguration.created_at)).all()


@router.post("/ai/model-configs", response_model=ModelConfigOut, status_code=201)
def create_model_config(body: ModelConfigIn, request: Request, ctx: TenantContext = Depends(WRITE),
                        db: Session = Depends(get_db)):
    mc = ModelConfiguration(organization_id=ctx.organization_id, **body.model_dump())
    db.add(mc)
    db.flush()
    _audit(db, ctx, "model_config.create", "model_configuration", mc.id, request, {"provider": mc.provider})
    db.commit()
    return mc


@router.get("/agents/templates")
def list_templates(_: TenantContext = Depends(READ)):
    return {"items": TEMPLATES}


@router.get("/agents/tools")
def list_tools(_: TenantContext = Depends(READ)):
    return {"items": [{"key": t.key, "name": t.name, "description": t.description,
                       "required_permission": t.required_permission, "side_effect": t.side_effect,
                       "contacts_person": t.contacts_person, "parameters": t.parameters} for t in TOOLS.values()]}


@router.get("/agents/languages")
def list_languages(_: TenantContext = Depends(READ)):
    return {"items": [{"code": k, **v} for k, v in svc.LANGUAGES.items()]}


# ------------------------------------------------------------------ CRUD
@router.get("/agents", response_model=Page[AgentOut])
def list_agents(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db), page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=100), status: str | None = Query(None, max_length=20)):
    base = select(AIAgent).where(AIAgent.organization_id == ctx.organization_id, AIAgent.deleted_at.is_(None))
    if status:
        base = base.where(AIAgent.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(AIAgent.created_at.desc(), AIAgent.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[AgentOut](items=[AgentOut.model_validate(r) for r in rows], total=total, page=page,
                          page_size=page_size)


def _create(db, ctx, data: dict, request, template_key=None) -> AIAgent:
    svc.validate_fields(db, ctx, data)
    data = {k: v for k, v in data.items() if v is not None}
    agent = AIAgent(organization_id=ctx.organization_id, status="draft", template_key=template_key,
                    created_by_user_id=ctx.user.id, **data)
    db.add(agent)
    db.flush()
    _audit(db, ctx, "agent.create", "ai_agent", agent.id, request, {"template_key": template_key})
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(body: AgentCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                 db: Session = Depends(get_db)):
    return _create(db, ctx, body.model_dump(), request)


@router.post("/agents/from-template", response_model=AgentOut, status_code=201)
def create_from_template(body: FromTemplate, request: Request, ctx: TenantContext = Depends(WRITE),
                         db: Session = Depends(get_db)):
    tpl = TEMPLATES_BY_KEY.get(body.template_key)
    if tpl is None:
        raise AppError(404, "not_found", "Template not found")
    data = {k: v for k, v in tpl.items() if k != "key"}
    data["compliance_disclosure"] = data["compliance_disclosure"].format(
        business=body.business_name or "our business")
    if body.name:
        data["name"] = body.name
    return _create(db, ctx, data, request, template_key=tpl["key"])


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return svc.get_agent(db, ctx, agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: uuid.UUID, body: AgentUpdate, request: Request, ctx: TenantContext = Depends(WRITE),
                 db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    changes = body.model_dump(exclude_unset=True)
    for k in ("name", "compliance_disclosure", "language", "speaking_rate", "max_call_seconds"):
        if k in changes and changes[k] is None:
            raise AppError(422, "validation_error", f"{k} cannot be null")
    svc.validate_fields(db, ctx, changes)
    for k, v in changes.items():
        setattr(agent, k, v)
    if changes and agent.status == "published":
        agent.status = "draft"  # edits must be re-published (new immutable version)
    _audit(db, ctx, "agent.update", "ai_agent", agent.id, request, {"fields": sorted(changes)})
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                 db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    agent.deleted_at = utcnow()
    _audit(db, ctx, "agent.delete", "ai_agent", agent.id, request)
    db.commit()


@router.post("/agents/{agent_id}/publish", response_model=VersionOut, status_code=201)
def publish_agent(agent_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    if agent.status != "published":  # re-publishing a live agent does not add an active agent
        billing.enforce_limit(db, ctx.organization_id, "active_agents")
    v = svc.publish(db, ctx, agent)
    db.flush()
    _audit(db, ctx, "agent.publish", "ai_agent", agent.id, request, {"version": v.version})
    db.commit()
    return v


@router.post("/agents/{agent_id}/kill", response_model=AgentOut)
def kill_agent(agent_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
               db: Session = Depends(get_db)):
    """Per-agent kill switch: immediately blocks all new calls and test runs for this agent."""
    agent = svc.get_agent(db, ctx, agent_id)
    agent.status = "killed"
    _audit(db, ctx, "agent.kill", "ai_agent", agent.id, request)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/agents/{agent_id}/reactivate", response_model=AgentOut)
def reactivate_agent(agent_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                     db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    if agent.status != "killed":
        raise AppError(409, "not_killed", "Agent is not killed")
    agent.status = "draft"  # must be re-published deliberately
    _audit(db, ctx, "agent.reactivate", "ai_agent", agent.id, request)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents/{agent_id}/versions", response_model=list[VersionOut])
def list_versions(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.get_agent(db, ctx, agent_id)
    return db.scalars(select(AgentVersion).where(AgentVersion.organization_id == ctx.organization_id,
                                                 AgentVersion.agent_id == agent_id)
                      .order_by(AgentVersion.version.desc())).all()


# ------------------------------------------------------------------ evaluations
@router.get("/agents/{agent_id}/evaluations", response_model=list[EvaluationOut])
def list_evaluations(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.get_agent(db, ctx, agent_id)
    return db.scalars(select(AgentEvaluation).where(AgentEvaluation.organization_id == ctx.organization_id,
                                                    AgentEvaluation.agent_id == agent_id)
                      .order_by(AgentEvaluation.created_at.desc())).all()


@router.post("/agents/{agent_id}/evaluations", response_model=EvaluationOut, status_code=201)
def add_evaluation(agent_id: uuid.UUID, body: EvaluationIn, request: Request, ctx: TenantContext = Depends(WRITE),
                   db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    if ctx.role_name not in svc.EVALUATOR_ROLES:
        raise AppError(403, "forbidden", "Only Owners and Admins may record evaluations")
    if body.kind == "language" and body.language not in svc.LANGUAGES:
        raise AppError(422, "unsupported_language", f"language must be one of {sorted(svc.LANGUAGES)}")
    ev = AgentEvaluation(organization_id=ctx.organization_id, agent_id=agent.id, evaluated_by_user_id=ctx.user.id,
                         **body.model_dump())
    db.add(ev)
    db.flush()
    _audit(db, ctx, "agent.evaluation", "ai_agent", agent.id, request,
           {"kind": ev.kind, "language": ev.language, "passed": ev.passed})
    db.commit()
    return ev


# ------------------------------------------------------------------ knowledge
@router.get("/agents/{agent_id}/knowledge", response_model=list[KnowledgeOut])
def list_knowledge(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.get_agent(db, ctx, agent_id)
    return db.scalars(select(AgentKnowledge).where(AgentKnowledge.organization_id == ctx.organization_id,
                                                   AgentKnowledge.agent_id == agent_id)
                      .order_by(AgentKnowledge.created_at.desc())).all()


@router.post("/agents/{agent_id}/knowledge", response_model=KnowledgeOut, status_code=201)
def add_knowledge(agent_id: uuid.UUID, body: KnowledgeIn, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    prev = db.scalar(select(func.max(AgentKnowledge.version)).where(
        AgentKnowledge.organization_id == ctx.organization_id, AgentKnowledge.agent_id == agent.id,
        AgentKnowledge.title == body.title.strip())) or 0
    doc = AgentKnowledge(organization_id=ctx.organization_id, agent_id=agent.id, title=body.title.strip(),
                         content=body.content, version=prev + 1)
    db.add(doc)
    db.flush()
    rag.ingest(db, doc)
    _audit(db, ctx, "agent_knowledge.create", "agent_knowledge", doc.id, request,
           {"agent_id": str(agent.id), "chunks": doc.chunk_count, "embedding_status": doc.embedding_status})
    db.commit()
    return doc


@router.delete("/agents/{agent_id}/knowledge/{knowledge_id}", status_code=204)
def delete_knowledge(agent_id: uuid.UUID, knowledge_id: uuid.UUID, request: Request,
                     ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    svc.get_agent(db, ctx, agent_id)
    doc = db.scalar(select(AgentKnowledge).where(AgentKnowledge.id == knowledge_id,
                                                 AgentKnowledge.organization_id == ctx.organization_id,
                                                 AgentKnowledge.agent_id == agent_id))
    if doc is None:
        raise AppError(404, "not_found", "Knowledge document not found")
    vectors_removed = rag.delete_vectors(ctx.organization_id, doc.id)
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_id == doc.id,
                                            KnowledgeChunk.organization_id == ctx.organization_id))
    db.delete(doc)
    _audit(db, ctx, "agent_knowledge.delete", "agent_knowledge", knowledge_id, request,
           {"vectors_removed": vectors_removed})
    db.commit()


# ------------------------------------------------------------------ test lab
@router.post("/agents/{agent_id}/test", response_model=TestResponse)
def test_agent(agent_id: uuid.UUID, body: TestRequest, request: Request, ctx: TenantContext = Depends(WRITE),
               db: Session = Depends(get_db)):
    agent = svc.get_agent(db, ctx, agent_id)
    if agent.status == "killed":
        raise AppError(409, "agent_killed", "Agent is killed; reactivate it to test")
    billing.enforce_limit(db, ctx.organization_id, "ai_conversations")
    spec = svc.model_spec(db, agent, body.provider)
    t0 = time.perf_counter()
    state = build_turn_graph().run({
        "agent": agent, "env": ToolEnv(db, ctx, agent, dry_run=body.dry_run), "spec": spec,
        "messages": [m.model_dump() for m in body.messages], "use_knowledge": body.use_knowledge,
        "requested_tools": [t.model_dump() for t in body.invoke_tools], "tool_calls": [], "logs": [],
    })
    latency = int((time.perf_counter() - t0) * 1000)
    err = state.get("error")
    run = AgentRun(organization_id=ctx.organization_id, agent_id=agent.id, kind="test",
                   input={"messages": [m.model_dump() for m in body.messages], "provider": spec.provider,
                          "invoke_tools": [t.model_dump() for t in body.invoke_tools], "dry_run": body.dry_run},
                   output=state.get("reply") or None, latency_ms=latency, tool_calls=state.get("tool_calls", []),
                   citations=state.get("citations", []), retrieval_mode=state.get("retrieval_mode"),
                   provider=spec.provider, model=state.get("model") or spec.model, error=err,
                   simulated=bool(state.get("simulated")), actor_user_id=ctx.user.id)
    db.add(run)
    db.flush()
    for step in state.get("logs", []):
        db.add(AgentLog(organization_id=ctx.organization_id, run_id=run.id, step=step["step"],
                        level="error" if (step.get("data") or {}).get("error") else "info",
                        data=step.get("data"), latency_ms=step["latency_ms"]))
    billing.record_usage(db, ctx.organization_id, "ai_conversations", 1, 0,
                         meta={"agent_id": str(agent.id), "run_id": str(run.id), "kind": "test",
                               "simulated": run.simulated})
    _audit(db, ctx, "agent.test", "ai_agent", agent.id, request, {"run_id": str(run.id), "provider": spec.provider})
    db.commit()
    status = "ok" if not err else ("not_configured" if state.get("error_status") == "not_configured" else "error")
    return TestResponse(run_id=run.id, status=status, reply=state.get("reply") or "", simulated=run.simulated,
                        provider=spec.provider, model=run.model, latency_ms=latency, tool_calls=run.tool_calls or [],
                        citations=run.citations or [], retrieval_mode=run.retrieval_mode or "none", error=err,
                        steps=state.get("logs", []))


@router.get("/agents/{agent_id}/runs", response_model=Page[RunOut])
def list_runs(agent_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
              page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    svc.get_agent(db, ctx, agent_id)
    base = select(AgentRun).where(AgentRun.organization_id == ctx.organization_id, AgentRun.agent_id == agent_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(AgentRun.created_at.desc(), AgentRun.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[RunOut](items=[RunOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
