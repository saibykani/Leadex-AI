import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.tenancy import (
    TenantContext,
    audit,
    build_context,
    get_current_user,
    get_tenant,
)
from app.modules.billing.service import enforce_limit
from app.modules.identity.models import Organization, OrganizationMembership, Role, User
from app.modules.identity.router import create_organization, memberships_for
from app.modules.identity.schemas import (
    MemberAdd,
    MemberOut,
    OrganizationCreate,
    OrganizationOut,
    RoleOut,
)

router = APIRouter(tags=["organizations"])


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [m.organization for m in memberships_for(db, user)]


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
def create_org(
    body: OrganizationCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    org = create_organization(db, user, body.name.strip(), body.country_code)
    audit(db, "organization.create", org_id=org.id, user_id=user.id, entity_type="organization", entity_id=org.id,
          request=request)
    db.commit()
    return org


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_org(org_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = build_context(db, user, org_id)
    ctx.require("org:read")
    return db.get(Organization, org_id)


def _member_out(m: OrganizationMembership) -> MemberOut:
    return MemberOut(id=m.id, user_id=m.user_id, email=m.user.email, full_name=m.user.full_name,
                     role=m.role.name, status=m.status)


@router.get("/organizations/{org_id}/members", response_model=list[MemberOut])
def list_members(org_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = build_context(db, user, org_id)
    ctx.require("members:read")
    rows = db.scalars(select(OrganizationMembership).where(OrganizationMembership.organization_id == org_id))
    return [_member_out(m) for m in rows]


@router.post("/organizations/{org_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    org_id: uuid.UUID,
    body: MemberAdd,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ctx = build_context(db, user, org_id)
    ctx.require("members:write")
    role = db.scalar(
        select(Role).where(Role.name == body.role, or_(Role.organization_id.is_(None), Role.organization_id == org_id))
    )
    if role is None:
        raise AppError(422, "unknown_role", f"Role '{body.role}' does not exist")
    if role.name == "Owner" and ctx.role_name != "Owner":
        raise AppError(403, "forbidden", "Only owners can grant the Owner role")
    invitee = db.scalar(select(User).where(User.email == body.email.lower()))
    if invitee is None:
        # Email invitations arrive with the communication module (Phase 7).
        raise AppError(404, "user_not_found", "No registered user with that email")
    exists = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == invitee.id
        )
    )
    if exists:
        raise AppError(409, "already_member", "User is already a member")
    enforce_limit(db, org_id, "users")
    m = OrganizationMembership(organization_id=org_id, user_id=invitee.id, role_id=role.id)
    db.add(m)
    db.flush()
    audit(db, "member.add", org_id=org_id, user_id=user.id, entity_type="membership", entity_id=m.id,
          data={"email": invitee.email, "role": role.name}, request=request)
    db.commit()
    db.refresh(m)
    return _member_out(m)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Role).where(or_(Role.organization_id.is_(None), Role.organization_id == ctx.organization_id))
        .order_by(Role.name)
    )
    return [
        RoleOut(id=r.id, name=r.name, description=r.description, is_system=r.organization_id is None,
                permissions=sorted(p.code for p in r.permissions))
        for r in rows
    ]
