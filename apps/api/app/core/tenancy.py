import uuid
from dataclasses import dataclass, field

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_actor, set_tenant
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.modules.identity.models import AuditLog, OrganizationMembership, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise AppError(401, "unauthenticated", "Authentication required")
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise AppError(401, "unauthenticated", "Invalid or expired token")
    set_actor(db, user.id)
    return user


@dataclass
class TenantContext:
    organization_id: uuid.UUID
    user: User
    role_name: str
    permissions: set[str] = field(default_factory=set)

    def require(self, perm: str) -> None:
        if perm not in self.permissions:
            raise AppError(403, "forbidden", f"Missing permission: {perm}")


def resolve_membership(db: Session, user: User, org_id: uuid.UUID) -> OrganizationMembership:
    m = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active",
        )
    )
    # 404 rather than 403 so tenant existence is not disclosed.
    if m is None or m.organization.deleted_at is not None:
        raise AppError(404, "not_found", "Organization not found")
    if m.organization.status == "suspended" and not user.is_superadmin:
        raise AppError(403, "organization_suspended", "This organization is suspended. Contact support.")
    return m


def build_context(db: Session, user: User, org_id: uuid.UUID) -> TenantContext:
    set_tenant(db, org_id)
    m = resolve_membership(db, user, org_id)
    return TenantContext(org_id, user, m.role.name, {p.code for p in m.role.permissions})


def get_tenant(
    x_organization_id: uuid.UUID | None = Header(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    if x_organization_id is None:
        raise AppError(400, "tenant_required", "X-Organization-Id header is required")
    return build_context(db, user, x_organization_id)


def require_permission(perm: str):
    def dep(ctx: TenantContext = Depends(get_tenant)) -> TenantContext:
        ctx.require(perm)
        return ctx

    return dep


def audit(
    db: Session,
    action: str,
    *,
    org_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    entity_type: str | None = None,
    entity_id=None,
    data: dict | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=org_id,
            actor_user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            data=data,
            ip_address=request.client.host if request and request.client else None,
        )
    )
