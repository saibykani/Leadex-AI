"""Investor demo mode: create / inspect / reset / delete a separate demo organization with fictional data."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.tenancy import TenantContext, audit, get_current_user, get_tenant
from app.modules.demo import service as svc
from app.modules.identity.models import User

router = APIRouter(tags=["demo"])


def _throttle(user: User) -> None:
    if not limiter.hit(f"demo:{user.id}", 5):
        raise AppError(429, "rate_limited", "Too many demo workspace requests; try again in a minute")


def _out(d) -> dict:
    if d is None:
        return {"exists": False, "organization_id": None, "summary": None}
    return {"exists": True, "organization_id": str(d.organization_id), "summary": d.summary,
            "created_at": d.created_at, "name": svc.DEMO_NAME}


@router.get("/demo")
def get_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(svc.find_demo(db, user))


@router.get("/demo/current")
def current_is_demo(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    """Whether the organization in X-Organization-Id is a demo workspace (drives the banner)."""
    return {"is_demo": svc.is_demo_org(db, ctx.organization_id), "organization_id": str(ctx.organization_id)}


@router.post("/demo", status_code=201)
def create_demo(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _throttle(user)
    existing = svc.find_demo(db, user)
    if existing is not None:
        raise AppError(409, "demo_exists", "You already have a demo workspace. Reset or delete it first.",
                       {"organization_id": str(existing.organization_id)})
    d = svc.create_demo(db, user)
    audit(db, "demo.create", org_id=d.organization_id, user_id=user.id, entity_type="organization",
          entity_id=d.organization_id, data={"fictional": True}, request=request)
    db.commit()
    return _out(d)


@router.post("/demo/reset")
def reset_demo(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _throttle(user)
    existing = svc.find_demo(db, user)
    if existing is not None:
        svc.delete_demo(db, user, existing)
        db.flush()
    set_tenant(db, None)
    d = svc.create_demo(db, user)
    audit(db, "demo.reset", org_id=d.organization_id, user_id=user.id, entity_type="organization",
          entity_id=d.organization_id, request=request)
    db.commit()
    return _out(d)


@router.delete("/demo", status_code=204)
def delete_demo(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = svc.find_demo(db, user)
    if d is None:
        raise AppError(404, "not_found", "No demo workspace")
    org_id = d.organization_id
    svc.delete_demo(db, user, d)
    audit(db, "demo.delete", org_id=org_id, user_id=user.id, entity_type="organization", entity_id=org_id,
          request=request)
    db.commit()
