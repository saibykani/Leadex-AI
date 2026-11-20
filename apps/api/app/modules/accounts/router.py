"""Account lifecycle: password reset, email verification, email invitations, session management.

Every token is random, stored only as a SHA-256 hash, single-use and short-lived. Outside production no
email leaves the platform; the response carries `dev_link` (labelled simulated) so flows can be tested.
Forgot-password never reveals whether an account exists.
"""
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_actor, set_tenant, utcnow
from app.core.errors import AppError
from app.core.mailer import send_system_email, web_url
from app.core.ratelimit import auth_rate_limit
from app.core.security import hash_password, hash_token
from app.core.tenancy import audit, build_context, get_current_user
from app.modules.accounts.models import AccountToken
from app.modules.identity.models import Organization, OrganizationMembership, Role, User, UserSession
from app.modules.identity.schemas import _strong

router = APIRouter(prefix="/auth", tags=["accounts"])
org_router = APIRouter(tags=["accounts"])
extra_routers = [org_router]

TTL = {"password_reset": timedelta(hours=1), "email_verify": timedelta(days=2), "invite": timedelta(days=7)}


class EmailBody(BaseModel):
    email: EmailStr


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetBody(TokenBody):
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        return _strong(v)


class AcceptInviteBody(TokenBody):
    full_name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def strong(cls, v: str | None) -> str | None:
        return None if v is None else _strong(v)


class InviteBody(BaseModel):
    email: EmailStr
    role: str = Field(default="Sales Rep", max_length=80)


class Delivery(BaseModel):
    status: str
    simulated: bool
    dev_link: str | None = None


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=utcnow().tzinfo)


def _issue(db: Session, purpose: str, email: str, **kw) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AccountToken(purpose=purpose, token_hash=hash_token(raw), email=email.lower(),
                        expires_at=utcnow() + TTL[purpose], **kw))
    return raw


def _deliver(to: str, subject: str, body: str, link: str) -> Delivery:
    r = send_system_email(to, subject, f"{body}\n\n{link}\n\nIf you did not expect this email, you can ignore it.")
    return Delivery(status=r.status, simulated=r.simulated, dev_link=link if r.simulated else None)


def _consume(db: Session, raw: str, purpose: str, *, mark_used: bool = True) -> AccountToken:
    t = db.scalar(select(AccountToken).where(AccountToken.token_hash == hash_token(raw),
                                             AccountToken.purpose == purpose))
    if t is None or t.used_at or t.revoked_at or _aware(t.expires_at) < utcnow():
        raise AppError(400, "invalid_token", "This link is invalid or has expired")
    if mark_used:
        t.used_at = utcnow()
    return t


# ------------------------------------------------------------------ password reset
@router.post("/password/forgot", response_model=Delivery, status_code=202, dependencies=[Depends(auth_rate_limit)])
def forgot_password(body: EmailBody, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.is_active.is_(True)))
    if user is None:  # same shape as success: account existence is not revealed
        return Delivery(status="accepted", simulated=True)
    raw = _issue(db, "password_reset", user.email, user_id=user.id)
    audit(db, "auth.password_reset_requested", org_id=None, user_id=user.id, request=request)
    db.commit()
    return _deliver(user.email, "Reset your Leadex password",
                    "Use this link within 1 hour to choose a new password:", web_url(f"/reset-password?token={raw}"))


@router.post("/password/reset", status_code=204, dependencies=[Depends(auth_rate_limit)])
def reset_password(body: ResetBody, request: Request, db: Session = Depends(get_db)):
    t = _consume(db, body.token, "password_reset")
    user = db.get(User, t.user_id)
    if user is None or not user.is_active:
        raise AppError(400, "invalid_token", "This link is invalid or has expired")
    user.password_hash = hash_password(body.password)
    user.email_verified_at = user.email_verified_at or utcnow()  # they proved control of the mailbox
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))):
        s.revoked_at = utcnow()  # sign out everywhere
    audit(db, "auth.password_reset", org_id=None, user_id=user.id, request=request)
    db.commit()


# ------------------------------------------------------------------ email verification
@router.post("/email/verify/request", response_model=Delivery, dependencies=[Depends(auth_rate_limit)])
def request_verification(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.email_verified_at:
        return Delivery(status="already_verified", simulated=False)
    raw = _issue(db, "email_verify", user.email, user_id=user.id)
    db.commit()
    return _deliver(user.email, "Verify your Leadex email", "Confirm your email address:",
                    web_url(f"/verify-email?token={raw}"))


@router.post("/email/verify", status_code=204, dependencies=[Depends(auth_rate_limit)])
def verify_email(body: TokenBody, request: Request, db: Session = Depends(get_db)):
    t = _consume(db, body.token, "email_verify")
    user = db.get(User, t.user_id)
    if user is None or user.email != t.email:
        raise AppError(400, "invalid_token", "This link is invalid or has expired")
    user.email_verified_at = utcnow()
    audit(db, "auth.email_verified", org_id=None, user_id=user.id, request=request)
    db.commit()


# ------------------------------------------------------------------ sessions / devices
class SessionOut(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    expires_at: datetime


class KeepBody(BaseModel):
    keep_refresh_token: str | None = None


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
                                                UserSession.expires_at > utcnow())
                      .order_by(UserSession.created_at.desc()).limit(50))
    return [SessionOut(id=s.id, user_agent=s.user_agent, ip_address=s.ip_address, created_at=s.created_at,
                       expires_at=s.expires_at) for s in rows]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = db.get(UserSession, session_id)
    if s is None or s.user_id != user.id:
        raise AppError(404, "not_found", "Session not found")
    if s.revoked_at is None:
        s.revoked_at = utcnow()
        audit(db, "auth.session_revoked", org_id=None, user_id=user.id, entity_type="session", entity_id=s.id,
              request=request)
        db.commit()


@router.post("/sessions/revoke-others", response_model=dict)
def revoke_other_sessions(body: KeepBody, request: Request, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    from app.modules.identity.router import refresh_token_from

    current = refresh_token_from(request, body.keep_refresh_token)
    keep = hash_token(current) if current else None
    n = 0
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))):
        if s.refresh_token_hash != keep:
            s.revoked_at = utcnow()
            n += 1
    audit(db, "auth.sessions_revoked", org_id=None, user_id=user.id, data={"count": n}, request=request)
    db.commit()
    return {"revoked": n}


# ------------------------------------------------------------------ invitations
class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InviteCreated(Delivery):
    invite: InviteOut


def _invite_out(db: Session, t: AccountToken) -> InviteOut:
    role = db.get(Role, t.role_id)
    return InviteOut(id=t.id, email=t.email, role=role.name if role else "?", expires_at=t.expires_at,
                     created_at=t.created_at)


@org_router.post("/organizations/{org_id}/invitations", response_model=InviteCreated, status_code=201)
def create_invitation(org_id: uuid.UUID, body: InviteBody, request: Request,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = build_context(db, user, org_id)
    ctx.require("members:write")
    role = db.scalar(select(Role).where(Role.name == body.role,
                                        or_(Role.organization_id.is_(None), Role.organization_id == org_id)))
    if role is None:
        raise AppError(422, "unknown_role", f"Role '{body.role}' does not exist")
    if role.name == "Owner" and ctx.role_name != "Owner":
        raise AppError(403, "forbidden", "Only owners can grant the Owner role")
    email = body.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing and db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == existing.id)):
        raise AppError(409, "already_member", "User is already a member")
    for old in db.scalars(select(AccountToken).where(AccountToken.purpose == "invite", AccountToken.email == email,
                                                     AccountToken.organization_id == org_id,
                                                     AccountToken.used_at.is_(None),
                                                     AccountToken.revoked_at.is_(None))):
        old.revoked_at = utcnow()  # re-inviting replaces the previous link
    raw = _issue(db, "invite", email, organization_id=org_id, role_id=role.id, created_by_user_id=user.id)
    db.flush()
    t = db.scalar(select(AccountToken).where(AccountToken.token_hash == hash_token(raw)))
    audit(db, "member.invite", org_id=org_id, user_id=user.id, entity_type="invitation", entity_id=t.id,
          data={"email": email, "role": role.name}, request=request)
    db.commit()
    org = db.get(Organization, org_id)
    d = _deliver(email, f"{user.full_name} invited you to {org.name} on Leadex",
                 f"You have been invited to join {org.name} as {role.name}. Accept within 7 days:",
                 web_url(f"/accept-invite?token={raw}"))
    return InviteCreated(**d.model_dump(), invite=_invite_out(db, t))


@org_router.get("/organizations/{org_id}/invitations", response_model=list[InviteOut])
def list_invitations(org_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    build_context(db, user, org_id).require("members:read")
    rows = db.scalars(select(AccountToken).where(
        AccountToken.purpose == "invite", AccountToken.organization_id == org_id, AccountToken.used_at.is_(None),
        AccountToken.revoked_at.is_(None), AccountToken.expires_at > utcnow()).order_by(AccountToken.created_at.desc()))
    return [_invite_out(db, t) for t in rows]


@org_router.delete("/organizations/{org_id}/invitations/{invite_id}", status_code=204)
def revoke_invitation(org_id: uuid.UUID, invite_id: uuid.UUID, request: Request,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    build_context(db, user, org_id).require("members:write")
    t = db.get(AccountToken, invite_id)
    if t is None or t.purpose != "invite" or t.organization_id != org_id:
        raise AppError(404, "not_found", "Invitation not found")
    t.revoked_at = utcnow()
    audit(db, "member.invite_revoked", org_id=org_id, user_id=user.id, entity_type="invitation", entity_id=t.id,
          request=request)
    db.commit()


class InvitePreview(BaseModel):
    email: str
    organization_name: str
    role: str
    account_exists: bool


@router.post("/invites/preview", response_model=InvitePreview, dependencies=[Depends(auth_rate_limit)])
def preview_invite(body: TokenBody, db: Session = Depends(get_db)):
    t = _consume(db, body.token, "invite", mark_used=False)
    org = db.get(Organization, t.organization_id)
    role = db.get(Role, t.role_id)
    exists = db.scalar(select(User.id).where(User.email == t.email)) is not None
    return InvitePreview(email=t.email, organization_name=org.name if org else "?", role=role.name if role else "?",
                         account_exists=exists)


@router.post("/invites/accept", status_code=204, dependencies=[Depends(auth_rate_limit)])
def accept_invite(body: AcceptInviteBody, request: Request, db: Session = Depends(get_db)):
    """New users set their name + password here. Existing users must sign in first; then the frontend calls
    this with their bearer token, and the invite email must match their account."""
    t = _consume(db, body.token, "invite")
    org = db.get(Organization, t.organization_id)
    if org is None or org.deleted_at is not None:
        raise AppError(400, "invalid_token", "This link is invalid or has expired")
    user = db.scalar(select(User).where(User.email == t.email))
    if user is None:
        if not body.password or not (body.full_name or "").strip():
            raise AppError(422, "details_required", "Your name and a password are required to create the account")
        user = User(email=t.email, password_hash=hash_password(body.password), full_name=body.full_name.strip(),
                    email_verified_at=utcnow())  # the invite link proves mailbox control
        db.add(user)
        db.flush()
    else:
        from app.core.security import decode_access_token

        auth = request.headers.get("authorization", "")
        uid = decode_access_token(auth[7:]) if auth.lower().startswith("bearer ") else None
        if str(uid) != str(user.id):
            raise AppError(401, "sign_in_required", "Sign in with the invited email address to accept")
    set_actor(db, user.id)
    set_tenant(db, org.id)
    if not db.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == org.id,
                                                          OrganizationMembership.user_id == user.id)):
        from app.modules.billing.service import enforce_limit

        enforce_limit(db, org.id, "users")
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role_id=t.role_id))
    audit(db, "member.invite_accepted", org_id=org.id, user_id=user.id, entity_type="invitation", entity_id=t.id,
          request=request)
    db.commit()
