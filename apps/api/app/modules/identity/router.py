import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, set_actor, set_tenant, utcnow
from app.core.errors import AppError
from app.core.ratelimit import auth_rate_limit
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.core.tenancy import TenantContext, audit, get_current_user, require_permission
from app.modules.identity.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    Role,
    User,
    UserSession,
)
from app.modules.identity.schemas import (
    AuditLogOut,
    LoginRequest,
    MembershipOut,
    MeResponse,
    OrganizationOut,
    Page,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
audit_router = APIRouter(tags=["audit"])

# Equalises timing for unknown e-mails so account existence is not revealed.
_DUMMY_HASH = hash_password("timing-equaliser-0")


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "org"
    return f"{base}-{secrets.token_hex(3)}"


def system_role(db: Session, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.organization_id.is_(None), Role.name == name))
    if role is None:
        raise AppError(500, "rbac_not_seeded", "System roles are missing; run migrations")
    return role


def create_organization(db: Session, user: User, name: str, country_code: str | None) -> Organization:
    org = Organization(name=name, slug=slugify(name), country_code=(country_code or None) and country_code.upper())
    db.add(org)
    db.flush()
    set_tenant(db, org.id)
    db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role_id=system_role(db, "Owner").id))
    return org


REFRESH_COOKIE = "lx_refresh"
COOKIE_PATH = "/api/v1/auth"
CSRF_HEADER = "x-requested-with"


def set_refresh_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(REFRESH_COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=True,
                        secure=s.is_production or s.cookie_samesite == "none", samesite=s.cookie_samesite,
                        path=COOKIE_PATH)


def clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, secure=s.is_production or s.cookie_samesite == "none",
                           samesite=s.cookie_samesite)


def refresh_token_from(request: Request, body_token: str | None) -> str | None:
    """Body token (API clients) or httpOnly cookie (browsers). Cookie use requires a custom header, which a
    cross-site form cannot send without a CORS preflight, so the cookie cannot be used for CSRF."""
    if body_token:
        return body_token
    cookie = request.cookies.get(REFRESH_COOKIE)
    if cookie and request.headers.get(CSRF_HEADER, "").lower() == "leadex":
        return cookie
    return None


def _issue_tokens(db: Session, user: User, request: Request, response: Response | None = None) -> TokenResponse:
    s = get_settings()
    refresh = new_refresh_token()
    db.add(
        UserSession(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh),
            expires_at=utcnow() + timedelta(days=s.refresh_token_days),
            user_agent=(request.headers.get("user-agent") or "")[:400],
            ip_address=request.client.host if request.client else None,
        )
    )
    if response is not None:
        set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=create_access_token(user.id), refresh_token=refresh, expires_in=s.access_token_minutes * 60
    )


@router.post("/register", response_model=TokenResponse, status_code=201, dependencies=[Depends(auth_rate_limit)])
def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError(409, "email_taken", "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.flush()
    set_actor(db, user.id)
    org = create_organization(db, user, body.organization_name.strip(), body.country_code)
    audit(db, "auth.register", org_id=org.id, user_id=user.id, entity_type="organization", entity_id=org.id,
          request=request)
    tokens = _issue_tokens(db, user, request, response)
    db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    if not verify_password(body.password, user.password_hash) or not user.is_active:
        audit(db, "auth.login_failed", org_id=None, user_id=user.id, request=request)
        db.commit()
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    if user.mfa_enabled:
        from app.modules.administration.mfa import verify as verify_totp

        if not body.otp_code:
            raise AppError(401, "mfa_required", "A one-time code from your authenticator app is required")
        if not verify_totp(user.mfa_secret_enc, body.otp_code):
            audit(db, "auth.mfa_failed", org_id=None, user_id=user.id, request=request)
            db.commit()
            raise AppError(401, "invalid_otp", "Invalid one-time code")
    user.last_login_at = utcnow()
    audit(db, "auth.login", org_id=None, user_id=user.id, request=request)
    tokens = _issue_tokens(db, user, request, response)
    db.commit()
    return tokens


def _active_session(db: Session, token: str) -> UserSession:
    sess = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == hash_token(token)))
    if sess is None or sess.revoked_at is not None:
        raise AppError(401, "invalid_refresh_token", "Refresh token is invalid")
    expires = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        raise AppError(401, "invalid_refresh_token", "Refresh token has expired")
    return sess


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
def refresh(request: Request, response: Response, body: RefreshRequest | None = None,
            db: Session = Depends(get_db)):
    token = refresh_token_from(request, body.refresh_token if body else None)
    if not token:
        raise AppError(401, "invalid_refresh_token", "Refresh token is missing")
    sess = _active_session(db, token)
    sess.revoked_at = utcnow()  # rotation: old token is single-use
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_refresh_token", "Refresh token is invalid")
    tokens = _issue_tokens(db, user, request, response)
    db.commit()
    return tokens


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, body: RefreshRequest | None = None,
           db: Session = Depends(get_db)):
    clear_refresh_cookie(response)
    token = refresh_token_from(request, body.refresh_token if body else None)
    if not token:
        return
    sess = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == hash_token(token)))
    if sess and sess.revoked_at is None:
        sess.revoked_at = utcnow()
        audit(db, "auth.logout", org_id=None, user_id=sess.user_id, request=request)
        db.commit()


def memberships_for(db: Session, user: User) -> list[MembershipOut]:
    rows = db.scalars(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active"
        )
    )
    return [
        MembershipOut(
            organization=OrganizationOut.model_validate(m.organization),
            role=m.role.name,
            permissions=sorted(p.code for p in m.role.permissions),
        )
        for m in rows
        if m.organization.deleted_at is None
    ]


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return MeResponse(user=UserOut.model_validate(user), memberships=memberships_for(db, user))


@audit_router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    page: int = 1,
    page_size: int = 25,
    ctx: TenantContext = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    page, page_size = max(page, 1), min(max(page_size, 1), 100)
    q = select(AuditLog).where(AuditLog.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page[AuditLogOut](items=list(items), total=total, page=page, page_size=page_size)


extra_routers = [audit_router]
