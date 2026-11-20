import hmac
import secrets
import uuid

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.automation import engine
from app.modules.automation.models import (
    AutomationSettings,
    Workflow,
    WorkflowApproval,
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowNode,
    WorkflowVersion,
    WorkflowWebhook,
)
from app.modules.automation.schemas import (
    Analytics,
    ApprovalOut,
    Decision,
    EventOut,
    ExecuteBody,
    ExecutionOut,
    Graph,
    SettingsBody,
    ValidationResult,
    VersionOut,
    WorkflowCreate,
    WorkflowCreated,
    WorkflowOut,
    WorkflowUpdate,
)
from app.modules.identity.schemas import Page

router = APIRouter(prefix="/workflows", tags=["workflows"])
hooks = APIRouter(tags=["workflows-public"])
extra_routers = [hooks]

READ = require_permission("org:read")
WRITE = require_permission("workflows:write")


def _audit(db, ctx: TenantContext, action, entity_id, request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="workflow",
          entity_id=entity_id, data=data, request=request)


def _wf(db, ctx: TenantContext, wid: uuid.UUID) -> Workflow:
    wf = db.scalar(select(Workflow).where(Workflow.id == wid, Workflow.organization_id == ctx.organization_id,
                                          Workflow.deleted_at.is_(None)))
    if wf is None:
        raise AppError(404, "not_found", "Workflow not found")
    return wf


def _ex(db, ctx: TenantContext, eid: uuid.UUID) -> WorkflowExecution:
    ex = db.scalar(select(WorkflowExecution).where(WorkflowExecution.id == eid,
                                                   WorkflowExecution.organization_id == ctx.organization_id))
    if ex is None:
        raise AppError(404, "not_found", "Execution not found")
    return ex


def _new_secret(db, wf: Workflow) -> str:
    secret = secrets.token_urlsafe(32)
    hook = db.get(WorkflowWebhook, wf.id)
    if hook is None:
        db.add(WorkflowWebhook(workflow_id=wf.id, organization_id=wf.organization_id,
                               secret_hash=engine.hash_secret(secret)))
    else:
        hook.secret_hash = engine.hash_secret(secret)
    return secret


# ---------------------------------------------------------------- static paths (before /{workflow_id})
@router.post("/validate", response_model=ValidationResult)
def validate(graph: Graph, ctx: TenantContext = Depends(READ)):
    errors = engine.validate_graph(graph.model_dump())
    return ValidationResult(valid=not errors, errors=errors)


@router.get("/settings", response_model=SettingsBody)
def get_settings_(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return SettingsBody(allowed_hosts=engine.allowed_hosts(db, ctx.organization_id))


@router.put("/settings", response_model=SettingsBody)
def put_settings(body: SettingsBody, request: Request, ctx: TenantContext = Depends(WRITE),
                 db: Session = Depends(get_db)):
    hosts = sorted({h.strip().lower() for h in body.allowed_hosts if h.strip()})
    for h in hosts:
        if "/" in h or ":" in h or " " in h:
            raise AppError(422, "invalid_host", f"'{h}' must be a bare hostname")
    s = db.scalar(select(AutomationSettings).where(AutomationSettings.organization_id == ctx.organization_id))
    if s is None:
        s = AutomationSettings(organization_id=ctx.organization_id)
        db.add(s)
    s.allowed_hosts = hosts
    _audit(db, ctx, "workflow_settings.update", None, request, {"allowed_hosts": hosts})
    db.commit()
    return SettingsBody(allowed_hosts=hosts)


def _analytics(db, org_id, workflow_id=None) -> Analytics:
    q = select(WorkflowExecution.status, func.count()).where(WorkflowExecution.organization_id == org_id)
    fq = select(WorkflowExecutionEvent.node_type, func.count()).where(
        WorkflowExecutionEvent.organization_id == org_id, WorkflowExecutionEvent.event == "failed")
    if workflow_id:
        q = q.where(WorkflowExecution.workflow_id == workflow_id)
        fq = fq.join(WorkflowExecution, WorkflowExecution.id == WorkflowExecutionEvent.execution_id).where(
            WorkflowExecution.workflow_id == workflow_id)
    by = {s: n for s, n in db.execute(q.group_by(WorkflowExecution.status)).all()}
    done = by.get("succeeded", 0) + by.get("failed", 0)
    failed_nodes = {t or "unknown": n for t, n in db.execute(fq.group_by(WorkflowExecutionEvent.node_type)).all()}
    return Analytics(total=sum(by.values()), by_status=by,
                     success_rate=round(by.get("succeeded", 0) / done, 4) if done else None,
                     failed_nodes=failed_nodes)


@router.get("/analytics", response_model=Analytics)
def org_analytics(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _analytics(db, ctx.organization_id)


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(status: str = Query("pending"), ctx: TenantContext = Depends(READ),
                   db: Session = Depends(get_db)):
    return db.scalars(select(WorkflowApproval).where(WorkflowApproval.organization_id == ctx.organization_id,
                                                     WorkflowApproval.status == status)
                      .order_by(WorkflowApproval.created_at.desc()).limit(200)).all()


def _decide(db, ctx, approval_id, approve: bool, body: Decision, request) -> ExecutionOut:
    ap = db.scalar(select(WorkflowApproval).where(WorkflowApproval.id == approval_id,
                                                  WorkflowApproval.organization_id == ctx.organization_id))
    if ap is None:
        raise AppError(404, "not_found", "Approval not found")
    if ap.status != "pending":
        raise AppError(409, "already_decided", f"Approval already {ap.status}")
    ap.status = "approved" if approve else "rejected"
    ap.decided_by_user_id, ap.decided_at, ap.comment = ctx.user.id, utcnow(), body.comment
    ex = db.get(WorkflowExecution, ap.execution_id)
    out = {"branch": ap.status, "decided_by": str(ctx.user.id), "comment": body.comment,
           "halt_unlabelled": not approve}
    _audit(db, ctx, f"workflow_approval.{ap.status}", ex.workflow_id, request,
           {"execution_id": str(ex.id), "node": ap.node_key})
    if ex.status == "waiting" and (ex.state or {}).get("waiting_on") == ap.node_key:
        engine.run_execution(db, ex.id, resume_output=out)
    db.commit()
    return ex


@router.post("/approvals/{approval_id}/approve", response_model=ExecutionOut)
def approve(approval_id: uuid.UUID, request: Request, body: Decision = Body(default_factory=Decision),
            ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    return _decide(db, ctx, approval_id, True, body, request)


@router.post("/approvals/{approval_id}/reject", response_model=ExecutionOut)
def reject(approval_id: uuid.UUID, request: Request, body: Decision = Body(default_factory=Decision),
           ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    return _decide(db, ctx, approval_id, False, body, request)


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
def get_execution(execution_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _ex(db, ctx, execution_id)


@router.get("/executions/{execution_id}/events", response_model=list[EventOut])
def execution_events(execution_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    ex = _ex(db, ctx, execution_id)
    return db.scalars(select(WorkflowExecutionEvent).where(
        WorkflowExecutionEvent.execution_id == ex.id,
        WorkflowExecutionEvent.organization_id == ctx.organization_id).order_by(WorkflowExecutionEvent.seq)).all()


def _resume_delay(db, ex: WorkflowExecution) -> bool:
    if ex.status != "waiting" or ex.resume_at is None:
        return False
    resume_at = ex.resume_at if ex.resume_at.tzinfo else ex.resume_at.replace(tzinfo=utcnow().tzinfo)
    if resume_at > utcnow():
        return False
    engine.run_execution(db, ex.id, resume_output={"resumed_at": utcnow().isoformat()})
    return True


@router.post("/executions/resume-due", response_model=list[ExecutionOut])
def resume_due(ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    """Process this tenant's due delays (call from a scheduler; a Celery beat / Temporal timer replaces it)."""
    due = db.scalars(select(WorkflowExecution).where(
        WorkflowExecution.organization_id == ctx.organization_id, WorkflowExecution.status == "waiting",
        WorkflowExecution.resume_at.is_not(None), WorkflowExecution.resume_at <= utcnow()).limit(100)).all()
    done = [ex for ex in due if _resume_delay(db, ex)]
    db.commit()
    return done


@router.post("/executions/{execution_id}/resume", response_model=ExecutionOut)
def resume(execution_id: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    ex = _ex(db, ctx, execution_id)
    if ex.status != "waiting" or ex.resume_at is None:
        raise AppError(409, "not_resumable", "Execution is not waiting on a delay")
    if not _resume_delay(db, ex):
        raise AppError(409, "not_due", "Delay has not elapsed yet", {"resume_at": ex.resume_at.isoformat()})
    db.commit()
    return ex


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionOut)
def cancel(execution_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
           db: Session = Depends(get_db)):
    ex = _ex(db, ctx, execution_id)
    if ex.status in {"succeeded", "failed", "cancelled"}:
        raise AppError(409, "finished", f"Execution already {ex.status}")
    ex.status, ex.finished_at, ex.resume_at = "cancelled", utcnow(), None
    _audit(db, ctx, "workflow_execution.cancel", ex.workflow_id, request, {"execution_id": str(ex.id)})
    db.commit()
    return ex


# ---------------------------------------------------------------- workflows CRUD
@router.get("", response_model=Page[WorkflowOut])
def list_workflows(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    base = select(Workflow).where(Workflow.organization_id == ctx.organization_id, Workflow.deleted_at.is_(None))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Workflow.updated_at.desc(), Workflow.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[WorkflowOut](items=[WorkflowOut.model_validate(r) for r in rows], total=total, page=page,
                             page_size=page_size)


@router.post("", response_model=WorkflowCreated, status_code=201)
def create_workflow(body: WorkflowCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    from app.modules.billing.service import enforce_limit

    enforce_limit(db, ctx.organization_id, "workflows")
    wf = Workflow(organization_id=ctx.organization_id, name=body.name.strip(), description=body.description,
                  draft_graph=body.graph.model_dump() if body.graph else {"nodes": [], "edges": []},
                  created_by_user_id=ctx.user.id, status="draft")
    db.add(wf)
    db.flush()
    secret = _new_secret(db, wf)
    _audit(db, ctx, "workflow.create", wf.id, request, {"name": wf.name})
    db.commit()
    return WorkflowCreated(**WorkflowOut.model_validate(wf).model_dump(), webhook_secret=secret)


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _wf(db, ctx, workflow_id)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(workflow_id: uuid.UUID, body: WorkflowUpdate, request: Request,
                    ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("status") == "active" and wf.current_version_id is None:
        raise AppError(409, "not_published", "Publish a version before activating")
    for k, v in changes.items():
        if v is None and k in {"name", "status"}:
            continue
        setattr(wf, "draft_graph" if k == "graph" else k, v)
    _audit(db, ctx, "workflow.update", wf.id, request, {"fields": sorted(changes)})
    db.commit()
    return wf


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    wf.deleted_at, wf.status = utcnow(), "archived"
    _audit(db, ctx, "workflow.delete", wf.id, request)
    db.commit()
    return Response(status_code=204)


@router.post("/{workflow_id}/webhook-secret", response_model=WorkflowCreated)
def rotate_secret(workflow_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    secret = _new_secret(db, wf)
    _audit(db, ctx, "workflow.webhook_secret_rotate", wf.id, request)
    db.commit()
    return WorkflowCreated(**WorkflowOut.model_validate(wf).model_dump(), webhook_secret=secret)


@router.get("/{workflow_id}/versions", response_model=list[VersionOut])
def list_versions(workflow_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    return db.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf.id,
                                                    WorkflowVersion.organization_id == ctx.organization_id)
                      .order_by(WorkflowVersion.version.desc())).all()


@router.post("/{workflow_id}/versions", response_model=VersionOut, status_code=201)
def publish(workflow_id: uuid.UUID, request: Request, body: Graph | None = Body(None),
            ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    """Publish an immutable version (from the body graph, or the saved draft) and activate the workflow."""
    wf = _wf(db, ctx, workflow_id)
    graph = body.model_dump() if body is not None and body.nodes else (wf.draft_graph or {})
    errors = engine.validate_graph(graph)
    if errors:
        raise AppError(422, "invalid_graph", "Workflow graph is invalid", errors)
    graph = {"nodes": [{"id": n["id"], "type": n["type"], "config": n.get("config") or {},
                        **({"position": n["position"]} if "position" in n else {})} for n in graph["nodes"]],
             "edges": [{"source": e["source"], "target": e["target"],
                        **({"label": e["label"]} if e.get("label") else {})} for e in graph.get("edges") or []]}
    last = db.scalar(select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id == wf.id)) or 0
    v = WorkflowVersion(organization_id=wf.organization_id, workflow_id=wf.id, version=last + 1, graph=graph,
                        created_by_user_id=ctx.user.id)
    db.add(v)
    db.flush()
    for n in graph["nodes"]:
        db.add(WorkflowNode(organization_id=wf.organization_id, version_id=v.id, node_key=n["id"], type=n["type"],
                            config=n["config"]))
    wf.current_version_id, wf.trigger_type, wf.draft_graph = v.id, engine.trigger_type_of(graph), graph
    if wf.status in {"draft", "paused"}:
        wf.status = "active"
    _audit(db, ctx, "workflow.publish", wf.id, request, {"version": v.version})
    db.commit()
    return v


@router.post("/{workflow_id}/execute", response_model=ExecutionOut, status_code=201)
def execute(workflow_id: uuid.UUID, request: Request, response: Response,
            body: ExecuteBody = Body(default_factory=ExecuteBody),
            idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
            ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    ex, created = engine.start_execution(db, workflow=wf, trigger_type="manual", payload=body.payload,
                                         idempotency_key=idempotency_key, user_id=ctx.user.id)
    if created:
        _audit(db, ctx, "workflow.execute", wf.id, request, {"execution_id": str(ex.id)})
    else:
        response.status_code = 200
    db.commit()
    return ex


@router.get("/{workflow_id}/executions", response_model=Page[ExecutionOut])
def list_executions(workflow_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                    status: str | None = None):
    wf = _wf(db, ctx, workflow_id)
    base = select(WorkflowExecution).where(WorkflowExecution.workflow_id == wf.id,
                                           WorkflowExecution.organization_id == ctx.organization_id)
    if status:
        base = base.where(WorkflowExecution.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(WorkflowExecution.created_at.desc(), WorkflowExecution.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ExecutionOut](items=[ExecutionOut.model_validate(r) for r in rows], total=total, page=page,
                              page_size=page_size)


@router.get("/{workflow_id}/analytics", response_model=Analytics)
def wf_analytics(workflow_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    wf = _wf(db, ctx, workflow_id)
    return _analytics(db, ctx.organization_id, wf.id)


# ---------------------------------------------------------------- public webhook trigger
@hooks.post("/hooks/workflows/{workflow_id}/{secret}", status_code=202)
def webhook_trigger(workflow_id: uuid.UUID, secret: str, request: Request,
                    payload: dict = Body(default_factory=dict),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
                    db: Session = Depends(get_db)):
    if not limiter.hit(f"wfhook:{workflow_id}", 120):
        raise AppError(429, "rate_limited", "Too many requests, try again later")
    hook = db.get(WorkflowWebhook, workflow_id)
    # Same 404 for unknown workflow and wrong secret (no existence oracle); constant-time compare.
    if hook is None or not hmac.compare_digest(hook.secret_hash, engine.hash_secret(secret)):
        raise AppError(404, "not_found", "Not found")
    set_tenant(db, hook.organization_id)
    wf = db.scalar(select(Workflow).where(Workflow.id == workflow_id,
                                          Workflow.organization_id == hook.organization_id,
                                          Workflow.deleted_at.is_(None)))
    if wf is None or wf.trigger_type != "webhook":
        raise AppError(404, "not_found", "Not found")
    if len(str(payload)) > 64_000:
        raise AppError(413, "payload_too_large", "Webhook payload too large")
    ex, _ = engine.start_execution(db, workflow=wf, trigger_type="webhook", payload=payload,
                                   idempotency_key=f"hook:{idempotency_key}" if idempotency_key else None,
                                   user_id=None)
    audit(db, "workflow.webhook_trigger", org_id=wf.organization_id, user_id=None, entity_type="workflow",
          entity_id=wf.id, data={"execution_id": str(ex.id)}, request=request)
    db.commit()
    return {"execution_id": str(ex.id), "status": ex.status}
