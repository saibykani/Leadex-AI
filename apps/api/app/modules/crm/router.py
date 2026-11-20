import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.automation.events import emit_event
from app.modules.billing.service import enforce_limit
from app.modules.crm import service as svc
from app.modules.crm.models import Lead, LeadActivity, LeadNote, LeadTask
from app.modules.crm.schemas import (
    ActivityOut,
    DashboardSummary,
    LeadCreate,
    LeadOut,
    LeadUpdate,
    NoteCreate,
    NoteOut,
    StatusChange,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.modules.identity.schemas import Page

router = APIRouter(tags=["crm"])

READ = require_permission("leads:read")
WRITE = require_permission("leads:write")
SORTABLE = {"created_at", "updated_at", "business_name", "score", "status"}


def _audit(db, ctx: TenantContext, action: str, entity_type: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=entity_type,
          entity_id=entity_id, data=data, request=request)


# ---------------------------------------------------------------- leads
@router.get("/leads", response_model=Page[LeadOut])
def list_leads(
    ctx: TenantContext = Depends(READ),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    status: list[str] | None = Query(None),
    q: str | None = Query(None, max_length=200),
    owner: uuid.UUID | None = None,
    sort: str = Query("-created_at"),
):
    field = sort.lstrip("-")
    if field not in SORTABLE:
        raise AppError(422, "invalid_sort", f"Sort must be one of {sorted(SORTABLE)}")
    base = select(Lead).where(Lead.organization_id == ctx.organization_id, Lead.deleted_at.is_(None))
    if status:
        base = base.where(Lead.status.in_(status))
    if owner:
        base = base.where(Lead.owner_user_id == owner)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        base = base.where(or_(func.lower(Lead.business_name).like(like), Lead.email_normalized.like(like),
                              func.lower(Lead.city).like(like), Lead.website_domain.like(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    col = getattr(Lead, field)
    order = col.desc() if sort.startswith("-") else col.asc()
    rows = db.scalars(base.order_by(order, Lead.id).offset((page - 1) * page_size).limit(page_size)).all()
    return Page[LeadOut](items=[LeadOut.model_validate(r) for r in rows], total=total, page=page,
                         page_size=page_size)


@router.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(body: LeadCreate, request: Request, ctx: TenantContext = Depends(WRITE),
                db: Session = Depends(get_db)):
    enforce_limit(db, ctx.organization_id, "leads")
    svc.ensure_member(db, ctx.organization_id, body.owner_user_id, "owner_user_id")
    lead = Lead(organization_id=ctx.organization_id, status="discovered",
                **body.model_dump(exclude={"business_name"}), business_name=body.business_name.strip())
    if lead.country:
        lead.country = lead.country.upper()
    svc.apply_contact_fields(lead)
    svc.check_duplicates(db, lead)
    db.add(lead)
    db.flush()
    svc.record_activity(db, ctx, lead, "lead.created", {"source": lead.source, "status": lead.status})
    _audit(db, ctx, "lead.create", "lead", lead.id, request, {"business_name": lead.business_name})
    emit_event(db, ctx.organization_id, "lead_created", {"lead_id": str(lead.id)}, event_id=str(lead.id))
    db.commit()
    return lead


@router.patch("/leads/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, body: TaskUpdate, request: Request, ctx: TenantContext = Depends(WRITE),
                db: Session = Depends(get_db)):
    task = db.scalar(select(LeadTask).where(LeadTask.id == task_id,
                                            LeadTask.organization_id == ctx.organization_id))
    if task is None:
        raise AppError(404, "not_found", "Task not found")
    lead = svc.get_lead(db, ctx, task.lead_id)
    changes = body.model_dump(exclude_unset=True)
    if "assignee_user_id" in changes:
        svc.ensure_member(db, ctx.organization_id, changes["assignee_user_id"], "assignee_user_id")
    completed = changes.pop("completed", None)
    for k, v in changes.items():
        if k == "title" and v is None:
            continue
        setattr(task, k, v)
    if completed is True and task.completed_at is None:
        task.completed_at = utcnow()
    elif completed is False:
        task.completed_at = None
    data = {"task_id": str(task.id), "fields": sorted(body.model_dump(exclude_unset=True))}
    svc.record_activity(db, ctx, lead, "task.completed" if completed else "task.updated", data)
    _audit(db, ctx, "lead_task.update", "lead_task", task.id, request, data)
    db.commit()
    return task


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return svc.get_lead(db, ctx, lead_id)


@router.patch("/leads/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: uuid.UUID, body: LeadUpdate, request: Request, ctx: TenantContext = Depends(WRITE),
                db: Session = Depends(get_db)):
    lead = svc.get_lead(db, ctx, lead_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("business_name", "") is None or changes.get("source", "") is None:
        raise AppError(422, "validation_error", "business_name and source cannot be null")
    if "owner_user_id" in changes:
        svc.ensure_member(db, ctx.organization_id, changes["owner_user_id"], "owner_user_id")
    if changes.get("country"):
        changes["country"] = changes["country"].upper()
    old = {k: getattr(lead, k) for k in changes}
    for k, v in changes.items():
        setattr(lead, k, v)
    svc.apply_contact_fields(lead)
    if changes.keys() & {"email", "phone", "website"}:
        svc.check_duplicates(db, lead)
    diff = {k: {"from": _j(old[k]), "to": _j(v)} for k, v in changes.items() if old[k] != v}
    if diff:
        svc.record_activity(db, ctx, lead, "lead.updated", {"changes": diff})
        _audit(db, ctx, "lead.update", "lead", lead.id, request, {"fields": sorted(diff)})
    db.commit()
    db.refresh(lead)
    return lead


def _j(v):
    return str(v) if isinstance(v, uuid.UUID) else v


@router.delete("/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                db: Session = Depends(get_db)):
    lead = svc.get_lead(db, ctx, lead_id)
    lead.deleted_at = utcnow()
    svc.record_activity(db, ctx, lead, "lead.deleted")
    _audit(db, ctx, "lead.delete", "lead", lead.id, request)
    db.commit()


@router.post("/leads/{lead_id}/status", response_model=LeadOut)
def change_status(lead_id: uuid.UUID, body: StatusChange, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    lead = svc.get_lead(db, ctx, lead_id)
    data = svc.change_status(ctx, lead, body.status, body.consent_reference, body.reason, body.admin_override)
    svc.record_activity(db, ctx, lead, "status.changed", data)
    _audit(db, ctx, "lead.status_change", "lead", lead.id, request, data)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------- notes
@router.get("/leads/{lead_id}/notes", response_model=list[NoteOut])
def list_notes(lead_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.get_lead(db, ctx, lead_id)
    return db.scalars(select(LeadNote).where(LeadNote.organization_id == ctx.organization_id,
                                             LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())).all()


@router.post("/leads/{lead_id}/notes", response_model=NoteOut, status_code=201)
def add_note(lead_id: uuid.UUID, body: NoteCreate, request: Request, ctx: TenantContext = Depends(WRITE),
             db: Session = Depends(get_db)):
    lead = svc.get_lead(db, ctx, lead_id)
    note = LeadNote(organization_id=ctx.organization_id, lead_id=lead.id, author_user_id=ctx.user.id,
                    body=body.body)
    db.add(note)
    db.flush()
    svc.record_activity(db, ctx, lead, "note.added", {"note_id": str(note.id)})
    _audit(db, ctx, "lead_note.create", "lead_note", note.id, request, {"lead_id": str(lead.id)})
    db.commit()
    return note


# ---------------------------------------------------------------- tasks
@router.get("/leads/{lead_id}/tasks", response_model=list[TaskOut])
def list_tasks(lead_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.get_lead(db, ctx, lead_id)
    return db.scalars(select(LeadTask).where(LeadTask.organization_id == ctx.organization_id,
                                             LeadTask.lead_id == lead_id).order_by(LeadTask.created_at)).all()


@router.post("/leads/{lead_id}/tasks", response_model=TaskOut, status_code=201)
def add_task(lead_id: uuid.UUID, body: TaskCreate, request: Request, ctx: TenantContext = Depends(WRITE),
             db: Session = Depends(get_db)):
    lead = svc.get_lead(db, ctx, lead_id)
    svc.ensure_member(db, ctx.organization_id, body.assignee_user_id, "assignee_user_id")
    task = LeadTask(organization_id=ctx.organization_id, lead_id=lead.id, title=body.title, due_at=body.due_at,
                    assignee_user_id=body.assignee_user_id, created_by_user_id=ctx.user.id)
    db.add(task)
    db.flush()
    svc.record_activity(db, ctx, lead, "task.created", {"task_id": str(task.id), "title": task.title})
    _audit(db, ctx, "lead_task.create", "lead_task", task.id, request, {"lead_id": str(lead.id)})
    db.commit()
    return task


# ---------------------------------------------------------------- activities
@router.get("/leads/{lead_id}/activities", response_model=Page[ActivityOut])
def list_activities(lead_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    svc.get_lead(db, ctx, lead_id)
    base = select(LeadActivity).where(LeadActivity.organization_id == ctx.organization_id,
                                      LeadActivity.lead_id == lead_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(LeadActivity.created_at.desc(), LeadActivity.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ActivityOut](items=[ActivityOut.model_validate(r) for r in rows], total=total, page=page,
                             page_size=page_size)


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Lead.status, func.count()).where(Lead.organization_id == ctx.organization_id,
                                                Lead.deleted_at.is_(None)).group_by(Lead.status)
    ).all()
    by_status = dict.fromkeys(svc.STATUSES, 0)
    for status, n in rows:
        by_status[status] = n
    open_q = (select(func.count()).select_from(LeadTask).join(Lead, Lead.id == LeadTask.lead_id)
              .where(LeadTask.organization_id == ctx.organization_id, LeadTask.completed_at.is_(None),
                     Lead.deleted_at.is_(None)))
    open_tasks = db.scalar(open_q) or 0
    overdue = db.scalar(open_q.where(LeadTask.due_at.is_not(None), LeadTask.due_at < utcnow())) or 0
    return DashboardSummary(total_leads=sum(by_status.values()), by_status=by_status, open_tasks=open_tasks,
                            overdue_tasks=overdue)
