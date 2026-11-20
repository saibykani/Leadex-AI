"""Websites API.

Authenticated routes live on `router`; public preview/feedback/site routes live on `public_router` (exposed via
`extra_routers`, so they are served under /api/v1 too).

A published site is served locally by GET /api/v1/sites/{project_id}, and on a customer's custom domain (DNS TXT
verified, see domains.py) by GET /api/v1/public/custom-site resolved from the Host header. CDN upload is future work.
"""
import importlib
import secrets
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.billing import service as billing
from app.modules.identity.schemas import Page
from app.modules.websites import copywriter, domains
from app.modules.websites.models import (
    WebsiteDeployment,
    WebsiteFeedback,
    WebsiteProject,
    WebsiteTemplate,
    WebsiteVersion,
)
from app.modules.websites.renderer import render
from app.modules.websites.schemas import (
    DeploymentOut,
    DomainIn,
    DomainOut,
    FeedbackIn,
    FeedbackOut,
    GenerateIn,
    PreviewLinkIn,
    PreviewLinkOut,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
    RenderIn,
    RollbackIn,
    TemplateOut,
    VersionDetail,
    VersionOut,
)
from app.modules.websites.templates import TEMPLATES

router = APIRouter(tags=["websites"])
public_router = APIRouter(tags=["websites-public"])
extra_routers = [public_router]

# No dedicated websites:read permission exists; editing rights are required to view drafts.
WRITE = require_permission("websites:write")
PUBLISH = require_permission("websites:publish")
PUBLIC_LIMIT = 60  # requests / minute / IP for public preview & site routes
FEEDBACK_LIMIT = 10


def _audit(db, ctx: TenantContext, action: str, entity_id, request: Request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="website_project",
          entity_id=entity_id, data=data, request=request)


# ---------------------------------------------------------------- helpers
def ensure_templates(db: Session) -> None:
    """Idempotent seed (migration 0008 seeds PostgreSQL; this covers SQLite/test schemas)."""
    have = set(db.scalars(select(WebsiteTemplate.key)))
    missing = [t for t in TEMPLATES if t["key"] not in have]
    for t in missing:
        db.add(WebsiteTemplate(**t))
    if missing:
        db.commit()


def _template(db: Session, key: str) -> WebsiteTemplate:
    ensure_templates(db)
    t = db.scalar(select(WebsiteTemplate).where(WebsiteTemplate.key == key))
    if t is None:
        raise AppError(422, "invalid_template", f"Unknown template '{key}'")
    return t


def _project(db: Session, ctx: TenantContext, pid: uuid.UUID) -> WebsiteProject:
    p = db.scalar(select(WebsiteProject).where(WebsiteProject.id == pid,
                                               WebsiteProject.organization_id == ctx.organization_id))
    if p is None:
        raise AppError(404, "not_found", "Website not found")
    return p


def _version(db: Session, p: WebsiteProject, vid: uuid.UUID | None) -> WebsiteVersion | None:
    if vid is None:
        return None
    return db.scalar(select(WebsiteVersion).where(WebsiteVersion.id == vid, WebsiteVersion.project_id == p.id,
                                                  WebsiteVersion.organization_id == p.organization_id))


def _site_path(p: WebsiteProject) -> str:
    return f"/api/v1/sites/{p.id}"


def _new_version(db: Session, p: WebsiteProject, content: dict, theme: dict, user_id, mode: str,
                 note: str | None) -> WebsiteVersion:
    n = db.scalar(select(func.max(WebsiteVersion.number)).where(WebsiteVersion.project_id == p.id)) or 0
    v = WebsiteVersion(organization_id=p.organization_id, project_id=p.id, number=n + 1, content=content,
                       rendered_html=render(content, theme, url=None), created_by=user_id, note=note,
                       generation_mode=mode)
    db.add(v)
    db.flush()
    p.current_version_id = v.id
    # New content invalidates a prior approval; a live site stays live until the next publish.
    p.approved_version_id = None
    if p.status == "approved":
        p.status = "draft"
    return v


def _detail(db: Session, p: WebsiteProject) -> ProjectDetail:
    v = _version(db, p, p.current_version_id)
    return ProjectDetail(
        **ProjectOut.model_validate(p).model_dump(),
        current_version_number=v.number if v else None, content=v.content if v else None,
        rendered_html=v.rendered_html if v else None, generation_mode=v.generation_mode if v else None,
        preview_path=f"/api/v1/public/preview/{p.preview_token}",
        published_path=_site_path(p) if p.published_version_id else None,
    )


def _facts_from_lead(db: Session, ctx: TenantContext, lead_id: uuid.UUID) -> dict:
    from app.modules.crm.models import Lead

    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.organization_id == ctx.organization_id,
                                        Lead.deleted_at.is_(None)))
    if lead is None:
        raise AppError(404, "not_found", "Lead not found")
    return {"name": lead.business_name, "industry": lead.industry, "city": lead.city, "country": lead.country,
            "phone": lead.phone, "email": lead.email}


_BUSINESS_MODELS = (("businesses", "Business"), ("discovery", "Business"), ("discovery", "DiscoveredBusiness"))


def _facts_from_business(db: Session, ctx: TenantContext, business_id: uuid.UUID) -> dict:
    model = None
    for mod, cls in _BUSINESS_MODELS:  # guarded: the discovery/businesses module may not exist
        try:
            model = getattr(importlib.import_module(f"app.modules.{mod}.models"), cls, None)
        except ModuleNotFoundError:
            continue
        if model is not None:
            break
    if model is None:
        raise AppError(422, "business_unavailable", "Business records are not available; supply business fields")
    b = db.scalar(select(model).where(model.id == business_id, model.organization_id == ctx.organization_id))
    if b is None:
        raise AppError(404, "not_found", "Business not found")
    g = lambda *names: next((getattr(b, n) for n in names if getattr(b, n, None)), None)  # noqa: E731
    return {"name": g("name", "business_name") or "Business", "industry": g("industry", "category"),
            "city": g("city"), "country": g("country", "country_code"), "phone": g("phone"),
            "email": g("email"), "address": g("address", "formatted_address"), "description": g("description")}


# ---------------------------------------------------------------- authenticated routes
@router.get("/websites/templates", response_model=list[TemplateOut])
def list_templates(_: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    ensure_templates(db)
    order = {t["key"]: i for i, t in enumerate(TEMPLATES)}
    rows = db.scalars(select(WebsiteTemplate)).all()
    return sorted(rows, key=lambda r: order.get(r.key, 99))


@router.post("/websites/generate", response_model=ProjectDetail, status_code=201)
def generate(body: GenerateIn, request: Request, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    billing.enforce_limit(db, ctx.organization_id, "websites")
    tpl = _template(db, body.template_key)
    facts: dict = {}
    if body.lead_id:
        facts.update(_facts_from_lead(db, ctx, body.lead_id))
    if body.business_id:
        facts.update(_facts_from_business(db, ctx, body.business_id))
    if body.business:  # explicitly supplied fields override record-derived ones
        facts.update({k: v for k, v in body.business.model_dump().items() if v not in (None, [], "")})
    if not facts.get("name"):
        raise AppError(422, "validation_error", "Provide business fields, lead_id or business_id")
    tpl_dict = {"key": tpl.key, "industry": tpl.industry, "sections": tpl.sections, "theme": tpl.theme}
    content = copywriter.build_content(facts, tpl_dict)
    if body.images:  # additive: approved, permission-confirmed images only (never Google photos)
        from app.modules.pipeline.images import resolve_for_website

        content["images"] = resolve_for_website(db, ctx, body.images, body.business_id)
    mode = "ai" if body.use_ai and copywriter.try_ai_polish(content, facts) else "template"
    p = WebsiteProject(organization_id=ctx.organization_id, business_id=body.business_id, lead_id=body.lead_id,
                       name=(body.name or facts["name"]).strip(), template_key=tpl.key, status="draft",
                       preview_token=secrets.token_urlsafe(24), created_by=ctx.user.id)
    db.add(p)
    db.flush()
    _new_version(db, p, content, tpl.theme, ctx.user.id, mode, "Initial generation")
    billing.record_usage(db, ctx.organization_id, "websites", 1, 0, lead_id=body.lead_id,
                         meta={"website_id": str(p.id), "generation_mode": mode})
    _audit(db, ctx, "website.generate", p.id, request, {"template": tpl.key, "generation_mode": mode})
    db.commit()
    return _detail(db, p)


@router.get("/websites", response_model=Page[ProjectOut])
def list_projects(ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db),
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                  status: str | None = Query(None, max_length=20)):
    base = select(WebsiteProject).where(WebsiteProject.organization_id == ctx.organization_id)
    if status:
        base = base.where(WebsiteProject.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(WebsiteProject.updated_at.desc(), WebsiteProject.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ProjectOut](items=[ProjectOut.model_validate(r) for r in rows], total=total, page=page,
                            page_size=page_size)


@router.get("/websites/{pid}", response_model=ProjectDetail)
def get_project(pid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    return _detail(db, _project(db, ctx, pid))


@router.patch("/websites/{pid}", response_model=ProjectDetail)
def update_project(pid: uuid.UUID, body: ProjectUpdate, request: Request, ctx: TenantContext = Depends(WRITE),
                   db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and body.name:
        p.name = body.name.strip()
    new_tpl = body.template_key and body.template_key != p.template_key
    if body.content is not None or new_tpl:
        tpl = _template(db, body.template_key or p.template_key)
        p.template_key = tpl.key
        cur = _version(db, p, p.current_version_id)
        content = body.content.model_dump() if body.content is not None else (cur.content if cur else None)
        if content is None:
            raise AppError(422, "validation_error", "content is required")
        _new_version(db, p, content, tpl.theme, ctx.user.id, "manual", body.note or "Edited")
    _audit(db, ctx, "website.update", p.id, request, {"fields": sorted(changes)})
    db.commit()
    return _detail(db, p)


@router.post("/websites/{pid}/render", response_class=HTMLResponse)
def render_draft(pid: uuid.UUID, body: RenderIn, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    """Render unsaved editor content for the live preview (nothing is stored)."""
    p = _project(db, ctx, pid)
    tpl = _template(db, body.template_key or p.template_key)
    return HTMLResponse(render(body.content.model_dump(), tpl.theme, preview=True))


@router.get("/websites/{pid}/versions", response_model=list[VersionOut])
def list_versions(pid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    return db.scalars(select(WebsiteVersion).where(WebsiteVersion.project_id == p.id,
                                                   WebsiteVersion.organization_id == ctx.organization_id)
                      .order_by(WebsiteVersion.number.desc())).all()


@router.get("/websites/{pid}/versions/{vid}", response_model=VersionDetail)
def get_version(pid: uuid.UUID, vid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    v = _version(db, _project(db, ctx, pid), vid)
    if v is None:
        raise AppError(404, "not_found", "Version not found")
    return v


@router.post("/websites/{pid}/versions/{vid}/restore", response_model=ProjectDetail)
def restore_version(pid: uuid.UUID, vid: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    """Restore = new version copying an old one's content (history stays immutable)."""
    p = _project(db, ctx, pid)
    v = _version(db, p, vid)
    if v is None:
        raise AppError(404, "not_found", "Version not found")
    tpl = _template(db, p.template_key)
    _new_version(db, p, v.content, tpl.theme, ctx.user.id, "restore", f"Restored from v{v.number}")
    _audit(db, ctx, "website.restore", p.id, request, {"from_version": v.number})
    db.commit()
    return _detail(db, p)


@router.post("/websites/{pid}/preview-link", response_model=PreviewLinkOut)
def preview_link(pid: uuid.UUID, request: Request, body: PreviewLinkIn | None = None,
                 ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    if body and body.rotate:
        p.preview_token = secrets.token_urlsafe(24)  # old links stop working
    if p.status == "draft":
        p.status = "preview"
    _audit(db, ctx, "website.preview_link", p.id, request, {"rotated": bool(body and body.rotate)})
    db.commit()
    return PreviewLinkOut(token=p.preview_token, path=f"/api/v1/public/preview/{p.preview_token}")


@router.get("/websites/{pid}/feedback", response_model=list[FeedbackOut])
def list_feedback(pid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    return db.scalars(select(WebsiteFeedback).where(WebsiteFeedback.project_id == p.id,
                                                    WebsiteFeedback.organization_id == ctx.organization_id)
                      .order_by(WebsiteFeedback.created_at.desc())).all()


@router.get("/websites/{pid}/deployments", response_model=list[DeploymentOut])
def list_deployments(pid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    return db.scalars(select(WebsiteDeployment).where(WebsiteDeployment.project_id == p.id,
                                                      WebsiteDeployment.organization_id == ctx.organization_id)
                      .order_by(WebsiteDeployment.deployed_at.desc())).all()


@router.post("/websites/{pid}/approve", response_model=ProjectDetail)
def approve(pid: uuid.UUID, request: Request, ctx: TenantContext = Depends(PUBLISH), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    if p.current_version_id is None:
        raise AppError(409, "invalid_state", "Nothing to approve")
    p.approved_version_id = p.current_version_id
    p.status = "approved"
    _audit(db, ctx, "website.approve", p.id, request, {"version_id": str(p.current_version_id)})
    db.commit()
    return _detail(db, p)


def _deploy(db: Session, ctx: TenantContext, p: WebsiteProject, v: WebsiteVersion, rolled_back_from=None):
    for d in db.scalars(select(WebsiteDeployment).where(WebsiteDeployment.project_id == p.id,
                                                        WebsiteDeployment.status == "live")):
        d.status = "superseded"
    d = WebsiteDeployment(organization_id=p.organization_id, project_id=p.id, version_id=v.id, status="live",
                          target="local", url=_site_path(p), deployed_at=utcnow(), deployed_by=ctx.user.id,
                          rolled_back_from=rolled_back_from)
    db.add(d)
    p.published_version_id = v.id
    p.status = "published"
    return d


@router.post("/websites/{pid}/publish", response_model=DeploymentOut)
def publish(pid: uuid.UUID, request: Request, ctx: TenantContext = Depends(PUBLISH), db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    v = _version(db, p, p.approved_version_id)
    if p.status != "approved" or v is None:
        raise AppError(409, "not_approved", "The website must be approved before publishing")
    d = _deploy(db, ctx, p, v)
    _audit(db, ctx, "website.publish", p.id, request, {"version": v.number})
    db.commit()
    return d


@router.post("/websites/{pid}/rollback", response_model=DeploymentOut)
def rollback(pid: uuid.UUID, body: RollbackIn, request: Request, ctx: TenantContext = Depends(PUBLISH),
             db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    if p.published_version_id is None:
        raise AppError(409, "not_published", "The website has not been published")
    v = _version(db, p, body.version_id)
    if v is None:
        raise AppError(404, "not_found", "Version not found")
    was_deployed = db.scalar(select(func.count()).select_from(WebsiteDeployment).where(
        WebsiteDeployment.project_id == p.id, WebsiteDeployment.version_id == v.id))
    if not was_deployed:
        raise AppError(409, "never_published", "Rollback target must be a previously published version")
    prev = p.published_version_id
    d = _deploy(db, ctx, p, v, rolled_back_from=prev)
    _audit(db, ctx, "website.rollback", p.id, request, {"to_version": v.number, "from_version_id": str(prev)})
    db.commit()
    return d


# ---------------------------------------------------------------- public routes
def _rate(request: Request, bucket: str, limit: int) -> None:
    ip = request.client.host if request.client else "unknown"
    if not limiter.hit(f"web:{bucket}:{ip}", limit):
        raise AppError(429, "rate_limited", "Too many requests, try again later")


def _public_org(db: Session, fn: str, arg) -> uuid.UUID | None:
    """Resolve the owning tenant of a public resource. On PostgreSQL this goes through a narrow SECURITY DEFINER
    function (migration 0008), because RLS hides every row until a tenant is bound."""
    if db.get_bind().dialect.name == "postgresql":
        return db.scalar(text(f"SELECT {fn}(:a)"), {"a": str(arg)})
    if fn == "website_org_by_preview_token":
        return db.scalar(select(WebsiteProject.organization_id).where(WebsiteProject.preview_token == arg))
    return db.scalar(select(WebsiteProject.organization_id).where(
        WebsiteProject.id == arg, WebsiteProject.published_version_id.is_not(None)))


def _media_origin() -> str:
    """Origin serving approved business images (/api/v1/public/media/...) referenced by generated sites."""
    from urllib.parse import urlsplit

    from app.modules.pipeline.config import pipeline_config

    u = urlsplit(pipeline_config().public_api_url)
    return f"{u.scheme}://{u.netloc}" if u.scheme in ("http", "https") and u.netloc else ""


_PUBLIC_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                   "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data: 'self' "
                                              f"{_media_origin()}; "
                                              "form-action mailto:; frame-ancestors *; base-uri 'none'"}


def _by_token(db: Session, token: str) -> WebsiteProject:
    if not (8 <= len(token) <= 64):
        raise AppError(404, "not_found", "Preview not found")
    org = _public_org(db, "website_org_by_preview_token", token)
    if org is None:
        raise AppError(404, "not_found", "Preview not found")
    set_tenant(db, org)
    p = db.scalar(select(WebsiteProject).where(WebsiteProject.preview_token == token,
                                               WebsiteProject.organization_id == org))
    if p is None:
        raise AppError(404, "not_found", "Preview not found")
    return p


@public_router.get("/public/preview/{token}", response_class=HTMLResponse)
def public_preview(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, "preview", PUBLIC_LIMIT)
    p = _by_token(db, token)
    v = _version(db, p, p.current_version_id)
    if v is None:
        raise AppError(404, "not_found", "Preview not found")
    tpl = _template(db, p.template_key)
    html = render(v.content, tpl.theme, preview=True)
    return HTMLResponse(html, headers={**_PUBLIC_HEADERS, "X-Robots-Tag": "noindex, nofollow",
                                       "Cache-Control": "no-store"})


@public_router.post("/public/preview/{token}/feedback", response_model=FeedbackOut, status_code=201)
def public_feedback(token: str, body: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    _rate(request, "feedback", FEEDBACK_LIMIT)
    p = _by_token(db, token)
    fb = WebsiteFeedback(organization_id=p.organization_id, project_id=p.id, version_id=p.current_version_id,
                         name=body.name.strip(), message=body.message.strip(), approved=body.approved)
    db.add(fb)
    audit(db, "website.feedback", org_id=p.organization_id, user_id=None, entity_type="website_project",
          entity_id=p.id, data={"approved": body.approved}, request=request)
    db.commit()
    return fb


@public_router.get("/sites/{pid}", response_class=HTMLResponse)
def public_site(pid: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Local deployment target. Real hosting / custom domains are future work."""
    _rate(request, "site", PUBLIC_LIMIT * 5)
    org = _public_org(db, "website_org_by_published_project", pid)
    if org is None:
        raise AppError(404, "not_found", "Site not found")
    set_tenant(db, org)
    p = db.scalar(select(WebsiteProject).where(WebsiteProject.id == pid, WebsiteProject.organization_id == org))
    v = _version(db, p, p.published_version_id) if p else None
    if v is None:
        raise AppError(404, "not_found", "Site not found")
    return HTMLResponse(v.rendered_html, headers={**_PUBLIC_HEADERS, "Cache-Control": "public, max-age=60"})


# ---------------------------------------------------------------- custom domains
def _domain_out(p: WebsiteProject, message: str | None = None) -> DomainOut:
    if not p.custom_domain:
        return DomainOut(domain=None, status="none", message=message)
    return DomainOut(domain=p.custom_domain, status=p.domain_verification_status, verified_at=p.domain_verified_at,
                     record_name=domains.record_name(p.custom_domain), record_value=p.domain_verification_token,
                     message=message)


@router.get("/websites/{pid}/domain", response_model=DomainOut)
def get_domain(pid: uuid.UUID, ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    return _domain_out(_project(db, ctx, pid))


@router.put("/websites/{pid}/domain", response_model=DomainOut)
def set_domain(pid: uuid.UUID, body: DomainIn, request: Request, ctx: TenantContext = Depends(PUBLISH),
               db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    domain = domains.normalize_domain(body.domain)
    if domain != p.custom_domain:
        taken = db.scalar(select(func.count()).select_from(WebsiteProject).where(
            WebsiteProject.custom_domain == domain, WebsiteProject.id != p.id))
        if taken:
            raise AppError(409, "domain_taken", "This domain is already connected to another website")
        p.custom_domain = domain
        p.domain_verification_token = secrets.token_urlsafe(24)
        p.domain_verification_status = "pending"
        p.domain_verified_at = None
    _audit(db, ctx, "website.domain_set", p.id, request, {"domain": domain})
    try:
        db.commit()
    except IntegrityError:  # unique index also catches domains hidden from us by row-level security
        db.rollback()
        raise AppError(409, "domain_taken", "This domain is already connected to another website") from None
    return _domain_out(p)


@router.post("/websites/{pid}/domain/verify", response_model=DomainOut)
def verify_domain(pid: uuid.UUID, request: Request, ctx: TenantContext = Depends(PUBLISH),
                  db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    if not p.custom_domain or not p.domain_verification_token:
        raise AppError(409, "no_domain", "Set a custom domain first")
    if p.domain_verification_status == "verified":
        return _domain_out(p, "Domain is already verified")
    if not domains.txt_matches(p.custom_domain, p.domain_verification_token):
        return _domain_out(p, f"TXT record not found yet at {domains.record_name(p.custom_domain)}. "
                              "DNS changes can take a while to propagate; try again shortly.")
    p.domain_verification_status = "verified"
    p.domain_verified_at = utcnow()
    _audit(db, ctx, "website.domain_verified", p.id, request, {"domain": p.custom_domain})
    db.commit()
    return _domain_out(p, "Domain verified")


@router.delete("/websites/{pid}/domain", status_code=204)
def remove_domain(pid: uuid.UUID, request: Request, ctx: TenantContext = Depends(PUBLISH),
                  db: Session = Depends(get_db)):
    p = _project(db, ctx, pid)
    old = p.custom_domain
    p.custom_domain = None
    p.domain_verification_token = None
    p.domain_verification_status = "none"
    p.domain_verified_at = None
    _audit(db, ctx, "website.domain_removed", p.id, request, {"domain": old})
    db.commit()


def _verified_domain_org(db: Session, host: str) -> uuid.UUID | None:
    if db.get_bind().dialect.name == "postgresql":
        return db.scalar(text("SELECT website_org_for_verified_domain(:d)"), {"d": host})
    return db.scalar(select(WebsiteProject.organization_id).where(
        WebsiteProject.custom_domain == host, WebsiteProject.domain_verified_at.is_not(None)))


def _clean_host(raw: str | None) -> str:
    host = (raw or "").strip().lower().rstrip(".")
    if host.startswith("["):  # IPv6 literal: never a customer domain
        return ""
    return host.split(":", 1)[0]


@public_router.get("/public/domain-check")
def domain_check(request: Request, domain: str = Query("", max_length=255), db: Session = Depends(get_db)):
    """Caddy on-demand TLS `ask` hook: 200 only for verified custom domains, so certificates are never issued
    for arbitrary hostnames."""
    _rate(request, "domaincheck", PUBLIC_LIMIT * 20)
    host = _clean_host(domain)
    if not host or _verified_domain_org(db, host) is None:
        raise AppError(404, "not_found", "Domain not verified")
    return Response(status_code=200, content="ok", media_type="text/plain")


@public_router.get("/public/custom-site", response_class=HTMLResponse)
def custom_domain_site(request: Request, db: Session = Depends(get_db)):
    """Serve the published site of the verified custom domain in the Host header (Caddy rewrites every path of a
    customer domain to this route)."""
    _rate(request, "customsite", PUBLIC_LIMIT * 5)
    host = _clean_host(request.headers.get("host"))
    org = _verified_domain_org(db, host) if host else None
    if org is None:
        raise AppError(404, "not_found", "Site not found")
    set_tenant(db, org)
    p = db.scalar(select(WebsiteProject).where(WebsiteProject.custom_domain == host,
                                               WebsiteProject.organization_id == org,
                                               WebsiteProject.domain_verified_at.is_not(None)))
    v = _version(db, p, p.published_version_id) if p else None
    if v is None:
        raise AppError(404, "not_found", "Site not found")
    return HTMLResponse(v.rendered_html, headers={**_PUBLIC_HEADERS, "Cache-Control": "public, max-age=60"})
