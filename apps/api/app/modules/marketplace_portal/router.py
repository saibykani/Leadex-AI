"""Marketplace portal: passwordless magic-link access for external providers and customers.

Staff (marketplace:write) invite a provider / requirement customer. The invitee signs in with a single-use
magic link and receives a short-lived JWT of type "portal" (never valid on staff endpoints, and staff tokens
are never valid here). Every portal query is scoped to the token's subject AND tenant (set_tenant), deny by default.
"""
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.mailer import send_system_email, web_url
from app.core.ratelimit import auth_rate_limit
from app.core.security import PORTAL_TOKEN_MINUTES, create_portal_token, decode_portal_token, hash_token
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.identity.models import Organization
from app.modules.marketplace import engine
from app.modules.marketplace import service as svc
from app.modules.marketplace.models import Customer, CustomerRequirement, Referral, ServiceProvider
from app.modules.marketplace.router import _portal_ref, _provider_out
from app.modules.marketplace.schemas import ProviderOut, RequirementOut
from app.modules.marketplace_portal.models import PortalAccount, PortalToken

router = APIRouter(tags=["marketplace-portal"])  # staff side (access JWT + permission)
public_router = APIRouter(prefix="/marketplace-portal", tags=["marketplace-portal"])
extra_routers = [public_router]

MKT = require_permission("marketplace:write")
LOGIN_TTL = timedelta(minutes=30)
INVITE_TTL = timedelta(days=2)
_bearer = HTTPBearer(auto_error=False)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=utcnow().tzinfo)


class Delivery(BaseModel):
    status: str
    simulated: bool
    dev_link: str | None = None
    dev_links: list[str] = []


class InviteOut(Delivery):
    account_id: uuid.UUID
    role: str
    email: str


class AccountOut(BaseModel):
    id: uuid.UUID
    role: str
    subject_id: uuid.UUID
    email: str
    active: bool
    last_login_at: datetime | None
    created_at: datetime


class LoginBody(BaseModel):
    email: EmailStr


class ExchangeBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class SessionOut(BaseModel):
    portal_token: str
    role: str
    expires_in: int
    organization_name: str | None


def _issue(db: Session, acct: PortalAccount, ttl: timedelta) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(PortalToken(account_id=acct.id, token_hash=hash_token(raw), expires_at=utcnow() + ttl))
    return raw


def _link(raw: str) -> str:
    return web_url(f"/portal/auth?token={raw}")


def _send(email: str, subject: str, body: str, links: list[str]) -> Delivery:
    text = body + "\n\n" + "\n".join(links) + "\n\nIf you did not expect this email, you can ignore it."
    r = send_system_email(email, subject, text)
    return Delivery(status=r.status, simulated=r.simulated, dev_link=links[0] if r.simulated and links else None,
                    dev_links=links if r.simulated else [])


def _upsert_account(db: Session, ctx: TenantContext, role: str, subject_id: uuid.UUID, email: str) -> PortalAccount:
    email = email.strip().lower()
    acct = db.scalar(select(PortalAccount).where(PortalAccount.organization_id == ctx.organization_id,
                                                 PortalAccount.role == role, PortalAccount.subject_id == subject_id))
    if acct is None:
        acct = PortalAccount(organization_id=ctx.organization_id, role=role, subject_id=subject_id, email=email,
                             created_by_user_id=ctx.user.id)
        db.add(acct)
    else:
        acct.email, acct.active = email, True
    db.flush()
    return acct


# ================================================================ staff: invite / manage
@router.post("/marketplace/providers/{pid}/portal-invite", response_model=InviteOut, status_code=201)
def invite_provider(pid: uuid.UUID, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    p = svc.get_in_org(db, ctx, ServiceProvider, pid, "Provider")
    if not p.email:
        raise AppError(422, "email_required", "The provider has no email address to send the invite to")
    return _invite(db, ctx, request, "provider", p.id, p.email, p.business_name)


@router.post("/marketplace/requirements/{req_id}/portal-invite", response_model=InviteOut, status_code=201)
def invite_customer(req_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(MKT),
                    db: Session = Depends(get_db)):
    req = svc.get_in_org(db, ctx, CustomerRequirement, req_id, "Requirement")
    cust = svc.get_in_org(db, ctx, Customer, req.customer_id, "Customer")
    return _invite(db, ctx, request, "customer", cust.id, cust.email, cust.full_name)


def _invite(db, ctx, request, role, subject_id, email, name) -> InviteOut:
    acct = _upsert_account(db, ctx, role, subject_id, email)
    link = _link(_issue(db, acct, INVITE_TTL))
    audit(db, "marketplace.portal.invite", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type=f"portal_{role}", entity_id=subject_id, data={"account_id": str(acct.id)}, request=request)
    db.commit()
    d = _send(acct.email, "Your Leadex portal access",
              f"Hello {name}, you have been invited to the Leadex marketplace portal. "
              "Use this single-use link within 2 days to sign in:", [link])
    return InviteOut(**d.model_dump(), account_id=acct.id, role=role, email=acct.email)


@router.get("/marketplace/portal-access", response_model=list[AccountOut])
def list_access(ctx: TenantContext = Depends(MKT), db: Session = Depends(get_db)):
    rows = db.scalars(select(PortalAccount).where(PortalAccount.organization_id == ctx.organization_id)
                      .order_by(PortalAccount.created_at.desc())).all()
    return [AccountOut.model_validate(a, from_attributes=True) for a in rows]


@router.delete("/marketplace/portal-access/{account_id}", status_code=204)
def revoke_access(account_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(MKT),
                  db: Session = Depends(get_db)):
    a = db.scalar(select(PortalAccount).where(PortalAccount.id == account_id,
                                              PortalAccount.organization_id == ctx.organization_id))
    if a is None:
        raise AppError(404, "not_found", "Portal access not found")
    a.active = False
    audit(db, "marketplace.portal.revoke", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="portal_account", entity_id=a.id, request=request)
    db.commit()


# ================================================================ public: magic link
@public_router.post("/login", response_model=Delivery, status_code=202, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    accts = db.scalars(select(PortalAccount).where(PortalAccount.email == email,
                                                   PortalAccount.active.is_(True))).all()
    if not accts:  # same shape as success: account existence is not revealed
        return Delivery(status="accepted", simulated=True)
    links = [_link(_issue(db, a, LOGIN_TTL)) for a in accts]
    for a in accts:
        audit(db, "marketplace.portal.login_requested", org_id=a.organization_id, user_id=None,
              entity_type="portal_account", entity_id=a.id, request=request)
    db.commit()
    return _send(email, "Your Leadex portal sign-in link",
                 "Use this single-use link within 30 minutes to sign in:", links)


def _subject_ok(db: Session, acct: PortalAccount) -> bool:
    """The linked record must still exist in the tenant and still carry the invited email."""
    model = ServiceProvider if acct.role == "provider" else Customer
    row = db.scalar(select(model).where(model.id == acct.subject_id, model.organization_id == acct.organization_id))
    return row is not None and (row.email or "").strip().lower() == acct.email


@public_router.post("/exchange", response_model=SessionOut, dependencies=[Depends(auth_rate_limit)])
def exchange(body: ExchangeBody, request: Request, db: Session = Depends(get_db)):
    bad = AppError(400, "invalid_token", "This link is invalid or has expired")
    t = db.scalar(select(PortalToken).where(PortalToken.token_hash == hash_token(body.token)))
    if t is None or t.used_at or _aware(t.expires_at) < utcnow():
        raise bad
    acct = db.get(PortalAccount, t.account_id)
    if acct is None or not acct.active:
        raise bad
    set_tenant(db, acct.organization_id)
    org = db.get(Organization, acct.organization_id)
    if org is None or org.deleted_at is not None or org.status == "suspended" or not _subject_ok(db, acct):
        raise bad
    t.used_at = utcnow()
    acct.last_login_at = utcnow()
    audit(db, "marketplace.portal.login", org_id=acct.organization_id, user_id=None,
          entity_type="portal_account", entity_id=acct.id, data={"role": acct.role}, request=request)
    db.commit()
    return SessionOut(portal_token=create_portal_token(acct.id, acct.organization_id, acct.role, acct.subject_id),
                      role=acct.role, expires_in=PORTAL_TOKEN_MINUTES * 60, organization_name=org.name)


# ================================================================ portal session dependency
@dataclass
class PortalCtx:
    account: PortalAccount
    organization_id: uuid.UUID
    subject_id: uuid.UUID
    role: str


def _resolve(creds: HTTPAuthorizationCredentials | None, db: Session, role: str | None) -> PortalCtx:
    claims = decode_portal_token(creds.credentials) if creds else None
    if claims is None:
        raise AppError(401, "unauthenticated", "Portal sign-in required")
    if role is not None and claims["role"] != role:
        raise AppError(403, "forbidden", "This area is not available for your portal role")
    set_tenant(db, claims["org_id"])
    acct = db.get(PortalAccount, claims["account_id"])
    if (acct is None or not acct.active or acct.organization_id != claims["org_id"]
            or acct.subject_id != claims["subject_id"] or acct.role != claims["role"]):
        raise AppError(401, "unauthenticated", "Portal access is no longer valid")
    org = db.get(Organization, acct.organization_id)
    if org is None or org.deleted_at is not None or org.status == "suspended":
        raise AppError(403, "forbidden", "This organization is unavailable")
    return PortalCtx(acct, acct.organization_id, acct.subject_id, acct.role)


def _portal(role: str | None):
    def dep(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> PortalCtx:
        return _resolve(creds, db, role)
    return dep


PROV = Depends(_portal("provider"))
CUST = Depends(_portal("customer"))
ANY = Depends(_portal(None))


def _paudit(db, p: PortalCtx, request, action, entity_type, entity_id, data=None):
    audit(db, action, org_id=p.organization_id, user_id=None, entity_type=entity_type, entity_id=entity_id,
          data={"portal_account_id": str(p.account.id), "role": p.role, **(data or {})}, request=request)


@public_router.get("/me")
def me(p: PortalCtx = ANY):
    return {"role": p.role, "email": p.account.email, "subject_id": str(p.subject_id),
            "organization_id": str(p.organization_id)}


# ================================================================ provider portal
def _my_referral(db: Session, p: PortalCtx, rid: uuid.UUID) -> Referral:
    r = db.scalar(select(Referral).where(Referral.id == rid, Referral.organization_id == p.organization_id,
                                         Referral.provider_id == p.subject_id))
    if r is None:
        raise AppError(404, "not_found", "Referral not found")
    return r


@public_router.get("/provider/profile", response_model=ProviderOut)
def provider_profile(p: PortalCtx = PROV, db: Session = Depends(get_db)):
    prov = db.scalar(select(ServiceProvider).where(ServiceProvider.id == p.subject_id,
                                                   ServiceProvider.organization_id == p.organization_id))
    if prov is None:
        raise AppError(404, "not_found", "Provider not found")
    return _provider_out(db, prov)


@public_router.get("/provider/referrals")
def provider_referrals(p: PortalCtx = PROV, db: Session = Depends(get_db)):
    rows = db.scalars(select(Referral).where(Referral.organization_id == p.organization_id,
                                             Referral.provider_id == p.subject_id)
                      .order_by(Referral.updated_at.desc())).all()
    return [_portal_ref(db, r) for r in rows]


def _move(db, p: PortalCtx, request, rid, new):
    r = _my_referral(db, p, rid)
    if new not in engine.PROVIDER_ALLOWED:
        raise AppError(403, "forbidden", f"Providers may not set status '{new}'")
    old = r.status
    svc.transition(db, p.organization_id, None, r, new, "Updated via provider portal")
    _paudit(db, p, request, f"marketplace.portal.referral_{new}", "referral", r.id, {"from": old, "to": new})
    db.commit()
    db.refresh(r)
    return _portal_ref(db, r)


@public_router.post("/provider/referrals/{rid}/accept")
def provider_accept(rid: uuid.UUID, request: Request, p: PortalCtx = PROV, db: Session = Depends(get_db)):
    return _move(db, p, request, rid, "accepted")


@public_router.post("/provider/referrals/{rid}/decline")
def provider_decline(rid: uuid.UUID, request: Request, p: PortalCtx = PROV, db: Session = Depends(get_db)):
    return _move(db, p, request, rid, "declined")


def _money_rows(txs) -> list[dict]:
    return [{k: (v if k == "currency" else str(v)) for k, v in b.items()} for b in svc.balances(txs)]


@public_router.get("/provider/commissions")
def provider_commissions(p: PortalCtx = PROV, db: Session = Depends(get_db)):
    refs = db.scalars(select(Referral).where(Referral.organization_id == p.organization_id,
                                             Referral.provider_id == p.subject_id)).all()
    ids = [r.id for r in refs]
    txs = svc.ledger(db, p.organization_id, ids) if ids else []
    by_ref: dict[uuid.UUID, list] = {}
    for t in txs:
        by_ref.setdefault(t.referral_id, []).append(t)
    title = {r.id: db.scalar(select(CustomerRequirement.title).where(CustomerRequirement.id == r.requirement_id))
             for r in refs}
    items = [{"referral_id": str(r.id), "requirement_title": title[r.id], "referral_status": r.status,
              "deal_value": str(r.deal_value) if r.deal_value is not None else None, "currency": r.currency,
              "balances": _money_rows(by_ref.get(r.id, []))} for r in refs]
    return {"totals": _money_rows(txs), "referrals": items}


# ================================================================ customer portal
def _my_requirement(db: Session, p: PortalCtx, req_id: uuid.UUID) -> CustomerRequirement:
    req = db.scalar(select(CustomerRequirement).where(CustomerRequirement.id == req_id,
                                                      CustomerRequirement.organization_id == p.organization_id,
                                                      CustomerRequirement.customer_id == p.subject_id))
    if req is None:
        raise AppError(404, "not_found", "Requirement not found")
    return req


def _req_view(db: Session, r: CustomerRequirement) -> dict:
    refs = db.scalars(select(Referral).where(Referral.requirement_id == r.id,
                                             Referral.organization_id == r.organization_id)).all()
    names = {x.id: x.business_name for x in db.scalars(select(ServiceProvider).where(
        ServiceProvider.id.in_([x.provider_id for x in refs]))).all()} if refs else {}
    out = RequirementOut.model_validate(r).model_dump(mode="json")
    out["referrals"] = [{"id": str(x.id), "provider_name": names.get(x.provider_id), "status": x.status,
                         "updated_at": x.updated_at.isoformat()} for x in refs]
    return out


@public_router.get("/customer/requirements")
def customer_requirements(p: PortalCtx = CUST, db: Session = Depends(get_db)):
    rows = db.scalars(select(CustomerRequirement).where(CustomerRequirement.organization_id == p.organization_id,
                                                        CustomerRequirement.customer_id == p.subject_id)
                      .order_by(CustomerRequirement.created_at.desc())).all()
    return [_req_view(db, r) for r in rows]


@public_router.get("/customer/requirements/{req_id}")
def customer_requirement(req_id: uuid.UUID, p: PortalCtx = CUST, db: Session = Depends(get_db)):
    return _req_view(db, _my_requirement(db, p, req_id))


@public_router.post("/customer/requirements/{req_id}/withdraw-contact")
def withdraw_contact(req_id: uuid.UUID, request: Request, p: PortalCtx = CUST, db: Session = Depends(get_db)):
    req = _my_requirement(db, p, req_id)
    was = req.contact_permission
    req.contact_permission = False
    _paudit(db, p, request, "marketplace.portal.contact_withdrawn", "customer_requirement", req.id,
            {"previous": was})
    db.commit()
    return _req_view(db, req)
