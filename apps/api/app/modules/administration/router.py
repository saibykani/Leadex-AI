"""MFA, super-admin console, integrations, notifications and support tickets."""
import re
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.security import verify_password
from app.core.tenancy import TenantContext, audit, get_current_user, require_permission
from app.modules.administration import mfa
from app.modules.administration.models import Integration, IntegrationCredential, Notification, SupportTicket
from app.modules.administration.schemas import (
    AdminAuditOut,
    AdminOrgOut,
    AdminUserOut,
    IntegrationOut,
    IntegrationUpdate,
    MfaCode,
    MfaDisable,
    MfaSetupOut,
    MfaStatus,
    NotificationOut,
    OrgUsage,
    SuspendRequest,
    TicketCreate,
    TicketOut,
    UsageSummary,
)
from app.modules.compliance.crypto import decrypt, encrypt
from app.modules.compliance.models import KillSwitch
from app.modules.compliance.schemas import KillSwitchCreate, KillSwitchOut
from app.modules.identity.models import AuditLog, Organization, OrganizationMembership, User
from app.modules.identity.schemas import Page

mfa_router = APIRouter(prefix="/auth/mfa", tags=["mfa"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])
router = APIRouter(tags=["integrations"])


def _is_pg(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


# ================================================================ MFA
@mfa_router.get("", response_model=MfaStatus)
def mfa_status(user: User = Depends(get_current_user)):
    return MfaStatus(mfa_enabled=user.mfa_enabled)


@mfa_router.post("/setup", response_model=MfaSetupOut)
def mfa_setup(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise AppError(409, "mfa_already_enabled", "Disable MFA before enrolling a new authenticator")
    secret, enc = mfa.new_secret()
    user.mfa_secret_enc = enc  # pending until verified
    audit(db, "auth.mfa_setup_started", org_id=None, user_id=user.id, request=request)
    db.commit()
    return MfaSetupOut(secret=secret, otpauth_uri=mfa.otpauth_uri(secret, user.email))


@mfa_router.post("/verify", response_model=MfaStatus)
def mfa_verify(body: MfaCode, request: Request, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise AppError(409, "mfa_already_enabled", "MFA is already enabled")
    if not user.mfa_secret_enc:
        raise AppError(409, "mfa_not_started", "Start MFA setup first")
    if not mfa.verify(user.mfa_secret_enc, body.code):
        raise AppError(422, "invalid_otp", "Invalid one-time code")
    user.mfa_enabled = True
    audit(db, "auth.mfa_enabled", org_id=None, user_id=user.id, request=request)
    db.commit()
    return MfaStatus(mfa_enabled=True)


@mfa_router.post("/disable", response_model=MfaStatus)
def mfa_disable(body: MfaDisable, request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not user.mfa_enabled:
        raise AppError(409, "mfa_not_enabled", "MFA is not enabled")
    if not verify_password(body.password, user.password_hash) or not mfa.verify(user.mfa_secret_enc, body.code):
        audit(db, "auth.mfa_disable_failed", org_id=None, user_id=user.id, request=request)
        db.commit()
        raise AppError(422, "invalid_credentials", "Invalid password or one-time code")
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    audit(db, "auth.mfa_disabled", org_id=None, user_id=user.id, request=request)
    db.commit()
    return MfaStatus(mfa_enabled=False)


# ================================================================ super admin
def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if not user.is_superadmin:
        raise AppError(403, "forbidden", "Super admin access required")
    return user


@admin_router.get("/organizations", response_model=Page[AdminOrgOut])
def admin_orgs(_: User = Depends(require_superadmin), db: Session = Depends(get_db),
               q: str | None = Query(None, max_length=200), page: int = Query(1, ge=1),
               page_size: int = Query(25, ge=1, le=200)):
    base = select(Organization)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        base = base.where(or_(func.lower(Organization.name).like(like), Organization.slug.like(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Organization.created_at.desc()).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    return Page[AdminOrgOut](items=[AdminOrgOut.model_validate(r) for r in rows], total=total, page=page,
                             page_size=page_size)


def _set_org_status(db: Session, user: User, org_id: uuid.UUID, status: str, reason: str | None,
                    request: Request) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise AppError(404, "not_found", "Organization not found")
    if org.is_platform_owner and status == "suspended":
        raise AppError(409, "platform_owner", "The platform owner organization cannot be suspended")
    old = org.status
    org.status = status
    # Platform-level event (organization_id NULL) so it is insertable without binding the tenant.
    audit(db, f"admin.organization_{'suspend' if status == 'suspended' else 'reactivate'}", org_id=None,
          user_id=user.id, entity_type="organization", entity_id=org.id,
          data={"from": old, "to": status, "reason": reason}, request=request)
    db.commit()
    return org


@admin_router.post("/organizations/{org_id}/suspend", response_model=AdminOrgOut)
def admin_suspend(org_id: uuid.UUID, body: SuspendRequest, request: Request,
                  user: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    return _set_org_status(db, user, org_id, "suspended", body.reason, request)


@admin_router.post("/organizations/{org_id}/reactivate", response_model=AdminOrgOut)
def admin_reactivate(org_id: uuid.UUID, request: Request, user: User = Depends(require_superadmin),
                     db: Session = Depends(get_db)):
    return _set_org_status(db, user, org_id, "active", None, request)


@admin_router.get("/users", response_model=Page[AdminUserOut])
def admin_users(_: User = Depends(require_superadmin), db: Session = Depends(get_db),
                q: str | None = Query(None, max_length=200), page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=200)):
    base = select(User)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        base = base.where(or_(User.email.like(like), func.lower(User.full_name).like(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page[AdminUserOut](items=[AdminUserOut.model_validate(r) for r in rows], total=total, page=page,
                              page_size=page_size)


def _usage_rows(db: Session) -> dict[uuid.UUID, tuple[int, int]]:
    """members/leads per org. On PostgreSQL these tables are RLS-protected, so we go through the
    SECURITY DEFINER function from migration 0005 (which itself re-checks users.is_superadmin)."""
    if _is_pg(db):
        rows = db.execute(text("SELECT organization_id, members, leads FROM leadex_admin_org_usage()")).all()
        return {r[0]: (int(r[1]), int(r[2])) for r in rows}
    from app.modules.crm.models import Lead

    members = dict(db.execute(select(OrganizationMembership.organization_id, func.count())
                              .where(OrganizationMembership.status == "active")
                              .group_by(OrganizationMembership.organization_id)).all())
    leads = dict(db.execute(select(Lead.organization_id, func.count()).where(Lead.deleted_at.is_(None))
                            .group_by(Lead.organization_id)).all())
    return {k: (members.get(k, 0), leads.get(k, 0)) for k in set(members) | set(leads)}


@admin_router.get("/usage", response_model=UsageSummary)
def admin_usage(_: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    orgs = db.scalars(select(Organization).where(Organization.deleted_at.is_(None))
                      .order_by(Organization.created_at.desc())).all()
    usage = _usage_rows(db)
    per = [OrgUsage(organization_id=o.id, name=o.name, status=o.status, members=usage.get(o.id, (0, 0))[0],
                    leads=usage.get(o.id, (0, 0))[1]) for o in orgs]
    return UsageSummary(organizations=len(orgs), active_organizations=sum(o.status == "active" for o in orgs),
                        users=db.scalar(select(func.count()).select_from(User)) or 0,
                        leads=sum(p.leads for p in per), per_organization=per)


@admin_router.get("/audit-logs", response_model=Page[AdminAuditOut])
def admin_audit_logs(_: User = Depends(require_superadmin), db: Session = Depends(get_db),
                     organization_id: uuid.UUID | None = None, page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=200)):
    off = (page - 1) * page_size
    if _is_pg(db):
        rows = db.execute(text("SELECT * FROM leadex_admin_audit_logs(:org, :lim, :off)"),
                          {"org": organization_id, "lim": page_size, "off": off}).mappings().all()
        total = int(rows[0]["total"]) if rows else (
            0 if page == 1 else int(db.execute(text("SELECT total FROM leadex_admin_audit_logs(:org, 1, 0)"),
                                               {"org": organization_id}).scalar() or 0))
        items = [AdminAuditOut(**{k: v for k, v in r.items() if k != "total"}) for r in rows]
        return Page[AdminAuditOut](items=items, total=total, page=page, page_size=page_size)
    base = select(AuditLog)
    if organization_id:
        base = base.where(AuditLog.organization_id == organization_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(AuditLog.created_at.desc()).offset(off).limit(page_size)).all()
    items = [AdminAuditOut(id=r.id, organization_id=r.organization_id, actor_user_id=r.actor_user_id,
                           action=r.action, entity_type=r.entity_type, entity_id=r.entity_id, data=r.data,
                           ip_address=r.ip_address, created_at=r.created_at) for r in rows]
    return Page[AdminAuditOut](items=items, total=total, page=page, page_size=page_size)


@admin_router.get("/kill-switches", response_model=list[KillSwitchOut])
def admin_list_kill_switches(_: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    return db.scalars(select(KillSwitch).where(KillSwitch.organization_id.is_(None))
                      .order_by(KillSwitch.created_at.desc())).all()


@admin_router.post("/kill-switches", response_model=KillSwitchOut, status_code=201)
def admin_create_kill_switch(body: KillSwitchCreate, request: Request, user: User = Depends(require_superadmin),
                             db: Session = Depends(get_db)):
    ks = KillSwitch(organization_id=None, scope="global", channel=body.channel, active=True, reason=body.reason,
                    set_by_user_id=user.id)
    db.add(ks)
    db.flush()
    audit(db, "kill_switch.global_activate", org_id=None, user_id=user.id, entity_type="kill_switch",
          entity_id=ks.id, data={"channel": ks.channel, "reason": ks.reason}, request=request)
    db.commit()
    return ks


@admin_router.post("/kill-switches/{switch_id}/deactivate", response_model=KillSwitchOut)
def admin_deactivate_kill_switch(switch_id: uuid.UUID, request: Request, user: User = Depends(require_superadmin),
                                 db: Session = Depends(get_db)):
    ks = db.scalar(select(KillSwitch).where(KillSwitch.id == switch_id, KillSwitch.organization_id.is_(None)))
    if ks is None:
        raise AppError(404, "not_found", "Kill switch not found")
    if ks.active:
        ks.active = False
        audit(db, "kill_switch.global_deactivate", org_id=None, user_id=user.id, entity_type="kill_switch",
              entity_id=ks.id, data={"channel": ks.channel}, request=request)
        db.commit()
    return ks


# ================================================================ integrations (tenant)
# Catalog of supported providers and the credentials each needs before it counts as configured.
PROVIDERS: dict[str, dict] = {
    "twilio": {"label": "Twilio (voice / SMS)", "credentials": ["account_sid", "auth_token"]},
    "sendgrid": {"label": "SendGrid (email)", "credentials": ["api_key"]},
    "whatsapp_cloud": {"label": "WhatsApp Cloud API", "credentials": ["access_token", "phone_number_id"]},
    "google_places": {"label": "Google Places (discovery)", "credentials": ["api_key"]},
    "openai": {"label": "OpenAI (AI models)", "credentials": ["api_key"]},
    "stripe": {"label": "Stripe (billing)", "credentials": ["secret_key"]},
    "calendar": {"label": "Calendar (meetings)", "credentials": ["client_id", "client_secret"]},
}
_NAME = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
INTEGRATIONS_READ = require_permission("org:read")
INTEGRATIONS_WRITE = require_permission("integrations:manage")


def _integration_out(provider: str, row: Integration | None, cred_names: list[str]) -> IntegrationOut:
    meta = PROVIDERS[provider]
    return IntegrationOut(provider=provider, label=meta["label"], status=row.status if row else "not_configured",
                          config=(row.config or {}) if row else {}, credential_names=sorted(cred_names),
                          required_credentials=meta["credentials"], updated_at=row.updated_at if row else None)


def _creds(db: Session, org_id: uuid.UUID, integration_id: uuid.UUID) -> list[IntegrationCredential]:
    return db.scalars(select(IntegrationCredential).where(IntegrationCredential.organization_id == org_id,
                                                          IntegrationCredential.integration_id == integration_id)
                      ).all()


def get_credential(db: Session, org_id: uuid.UUID, provider: str, name: str) -> str | None:
    """For adapters: decrypted credential or None (=> adapter must report status "not_configured")."""
    row = db.scalar(select(Integration).where(Integration.organization_id == org_id,
                                              Integration.provider == provider))
    if row is None or row.status != "configured":
        return None
    cred = db.scalar(select(IntegrationCredential).where(IntegrationCredential.integration_id == row.id,
                                                         IntegrationCredential.name == name))
    return decrypt(cred.secret_enc) if cred else None


@router.get("/integrations", response_model=list[IntegrationOut])
def list_integrations(ctx: TenantContext = Depends(INTEGRATIONS_READ), db: Session = Depends(get_db)):
    rows = {r.provider: r for r in db.scalars(select(Integration).where(
        Integration.organization_id == ctx.organization_id))}
    out = []
    for provider in PROVIDERS:
        row = rows.get(provider)
        names = [c.name for c in _creds(db, ctx.organization_id, row.id)] if row else []
        out.append(_integration_out(provider, row, names))
    return out


@router.put("/integrations/{provider}", response_model=IntegrationOut)
def upsert_integration(provider: str, body: IntegrationUpdate, request: Request,
                       ctx: TenantContext = Depends(INTEGRATIONS_WRITE), db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise AppError(404, "not_found", "Unknown integration provider")
    row = db.scalar(select(Integration).where(Integration.organization_id == ctx.organization_id,
                                              Integration.provider == provider))
    if row is None:
        row = Integration(organization_id=ctx.organization_id, provider=provider, status="not_configured")
        db.add(row)
        db.flush()
    if body.config is not None:
        row.config = body.config
    existing = {c.name: c for c in _creds(db, ctx.organization_id, row.id)}
    for name, value in (body.credentials or {}).items():
        if not _NAME.match(name):
            raise AppError(422, "validation_error", f"Invalid credential name: {name}")
        if not value or not value.strip():
            continue
        if name in existing:
            existing[name].secret_enc = encrypt(value.strip())
        else:
            existing[name] = IntegrationCredential(organization_id=ctx.organization_id, integration_id=row.id,
                                                   name=name, secret_enc=encrypt(value.strip()))
            db.add(existing[name])
    required = PROVIDERS[provider]["credentials"]
    row.status = "configured" if all(n in existing for n in required) else "not_configured"
    row.updated_at = utcnow()
    audit(db, "integration.update", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="integration",
          entity_id=row.id, request=request,
          data={"provider": provider, "credential_names": sorted((body.credentials or {}).keys()),
                "status": row.status})
    db.commit()
    return _integration_out(provider, row, list(existing))


@router.delete("/integrations/{provider}/credentials", response_model=IntegrationOut)
def clear_integration(provider: str, request: Request, ctx: TenantContext = Depends(INTEGRATIONS_WRITE),
                      db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise AppError(404, "not_found", "Unknown integration provider")
    row = db.scalar(select(Integration).where(Integration.organization_id == ctx.organization_id,
                                              Integration.provider == provider))
    if row is not None:
        for c in _creds(db, ctx.organization_id, row.id):
            db.delete(c)
        row.status = "not_configured"
        audit(db, "integration.credentials_cleared", org_id=ctx.organization_id, user_id=ctx.user.id,
              entity_type="integration", entity_id=row.id, data={"provider": provider}, request=request)
        db.commit()
    return _integration_out(provider, row, [])


# ================================================================ notifications
def notify(db: Session, org_id: uuid.UUID, user_id: uuid.UUID | None, kind: str, title: str,
           body: str | None = None) -> Notification:
    """Helper for other modules. user_id=None broadcasts to every member of the organization."""
    n = Notification(organization_id=org_id, user_id=user_id, kind=kind, title=title[:200], body=body)
    db.add(n)
    return n


MEMBER = require_permission("org:read")


@router.get("/notifications", response_model=Page[NotificationOut])
def list_notifications(ctx: TenantContext = Depends(MEMBER), db: Session = Depends(get_db),
                       unread: bool = False, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    base = select(Notification).where(Notification.organization_id == ctx.organization_id,
                                      or_(Notification.user_id == ctx.user.id, Notification.user_id.is_(None)))
    if unread:
        base = base.where(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Notification.created_at.desc()).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    return Page[NotificationOut](items=[NotificationOut.model_validate(r) for r in rows], total=total, page=page,
                                 page_size=page_size)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, ctx: TenantContext = Depends(MEMBER), db: Session = Depends(get_db)):
    n = db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.organization_id == ctx.organization_id,
        or_(Notification.user_id == ctx.user.id, Notification.user_id.is_(None))))
    if n is None:
        raise AppError(404, "not_found", "Notification not found")
    if n.read_at is None:
        n.read_at = utcnow()  # note: broadcast notifications are marked read for the whole org
        db.commit()
    return n


# ================================================================ support tickets
@router.get("/support/tickets", response_model=Page[TicketOut])
def list_tickets(ctx: TenantContext = Depends(MEMBER), db: Session = Depends(get_db),
                 page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    base = select(SupportTicket).where(SupportTicket.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(SupportTicket.created_at.desc()).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    return Page[TicketOut](items=[TicketOut.model_validate(r) for r in rows], total=total, page=page,
                           page_size=page_size)


@router.post("/support/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, request: Request, ctx: TenantContext = Depends(MEMBER),
                  db: Session = Depends(get_db)):
    t = SupportTicket(organization_id=ctx.organization_id, created_by_user_id=ctx.user.id, subject=body.subject,
                      body=body.body, priority=body.priority, status="open")
    db.add(t)
    db.flush()
    audit(db, "support_ticket.create", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="support_ticket", entity_id=t.id, data={"priority": t.priority}, request=request)
    db.commit()
    return t


extra_routers = [mfa_router, admin_router]
