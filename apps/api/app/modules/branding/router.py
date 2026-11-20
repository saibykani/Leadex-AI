"""White label: per-organization app name, logo, colour, support email and custom app domain."""
import re
import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.branding.models import OrganizationBranding

router = APIRouter(tags=["branding"])
public_router = APIRouter(tags=["branding"])
extra_routers = [public_router]
READ = require_permission("org:read")
WRITE = require_permission("org:write")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class BrandingIn(BaseModel):
    app_name: str | None = Field(None, max_length=80)
    logo_url: str | None = Field(None, max_length=1000)
    primary_color: str | None = None
    support_email: EmailStr | None = None
    app_domain: str | None = Field(None, max_length=255)
    hide_powered_by: bool = False

    @field_validator("primary_color")
    @classmethod
    def hex_color(cls, v):
        if v and not _HEX.match(v):
            raise ValueError("primary_color must look like #1a73e8")
        return v.lower() if v else None

    @field_validator("logo_url")
    @classmethod
    def https_logo(cls, v):
        if v and not v.startswith("https://"):
            raise ValueError("logo_url must be an https:// URL")
        return v or None

    @field_validator("app_domain")
    @classmethod
    def domain(cls, v):
        if not v:
            return None
        v = v.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
        if not _DOMAIN.match(v):
            raise ValueError("app_domain must be a hostname like app.yourbrand.com")
        return v


def _out(b: OrganizationBranding | None) -> dict:
    if b is None:
        return {"app_name": None, "logo_url": None, "primary_color": None, "support_email": None,
                "app_domain": None, "hide_powered_by": False}
    return {"app_name": b.app_name, "logo_url": b.logo_url, "primary_color": b.primary_color,
            "support_email": b.support_email, "app_domain": b.app_domain, "hide_powered_by": b.hide_powered_by}


def get_branding(db: Session, org_id: uuid.UUID) -> OrganizationBranding | None:
    return db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == org_id))


@router.get("/branding")
def read_branding(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _out(get_branding(db, ctx.organization_id))


@router.put("/branding")
def save_branding(body: BrandingIn, request: Request, ctx: TenantContext = Depends(WRITE),
                  db: Session = Depends(get_db)):
    if body.app_domain:
        taken = _domain_org(db, body.app_domain)
        if taken and taken != ctx.organization_id:
            raise AppError(409, "domain_taken", "That domain is already used by another workspace")
    b = get_branding(db, ctx.organization_id)
    if b is None:
        b = OrganizationBranding(organization_id=ctx.organization_id)
        db.add(b)
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, "branding.update", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="branding",
          data={"app_domain": body.app_domain, "has_logo": bool(body.logo_url)}, request=request)
    db.commit()
    return _out(b)


def _domain_org(db: Session, domain: str) -> uuid.UUID | None:
    if db.bind.dialect.name == "postgresql":
        return db.scalar(text("SELECT branding_org_for_domain(:d)"), {"d": domain})
    return db.scalar(select(OrganizationBranding.organization_id).where(OrganizationBranding.app_domain == domain))


@public_router.get("/public/branding")
def public_branding(domain: str = Query(..., max_length=255), db: Session = Depends(get_db)):
    """Brand for a custom app domain (login page). Returns only display fields, never tenant data."""
    from app.core.db import set_tenant

    org = _domain_org(db, domain.strip().lower())
    if org is None:
        return _out(None)
    set_tenant(db, org)
    return _out(get_branding(db, org))
