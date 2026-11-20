import json
import uuid
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_db, set_tenant, utcnow
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.discovery import service as discovery
from app.modules.pipeline import extraction, images, photos
from app.modules.pipeline import service as svc
from app.modules.pipeline.config import pipeline_config
from app.modules.pipeline.models import BusinessImage, ConversationOutcome, PipelineRun, PipelineSettings

router = APIRouter(tags=["pipeline"])
public_router = APIRouter(tags=["pipeline-public"])
extra_routers = [public_router]

B_READ = require_permission("businesses:read")
B_WRITE = require_permission("businesses:write")
A_READ = require_permission("agents:read")
A_WRITE = require_permission("agents:write")
L_WRITE = require_permission("leads:write")


# ------------------------------------------------------------------ schemas
class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ImageOut(_ORM):
    id: uuid.UUID
    business_id: uuid.UUID
    source: str
    status: str
    permission_confirmed: bool
    permission_confirmed_at: object | None = None
    content_type: str
    size_bytes: int
    origin_url: str | None
    filename: str | None
    alt: str | None
    created_at: object
    usable_in_website: bool = False


def _img_out(i: BusinessImage) -> ImageOut:
    o = ImageOut.model_validate(i)
    o.usable_in_website = i.status == "approved" and i.permission_confirmed
    return o


class ApproveIn(BaseModel):
    permission_confirmed: bool
    alt: str | None = Field(default=None, max_length=300)


class Package(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _range(self):
        if self.max < self.min:
            raise ValueError("max must be >= min")
        self.currency = self.currency.upper()
        return self


class PackagesIn(BaseModel):
    packages: list[Package] = Field(default_factory=list, max_length=10)


class BudgetAgentIn(BaseModel):
    business_name: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class Turn(BaseModel):
    role: str = Field(max_length=20)
    text: str = Field(max_length=4000)


class ExtractIn(BaseModel):
    transcript: list[Turn] = Field(default_factory=list, max_length=200)
    lead_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    call_id: uuid.UUID | None = None
    source: Literal["test_lab", "browser_voice", "call"] = "test_lab"
    mode: Literal["auto", "llm", "rules"] = "auto"


class OutcomeOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    call_id: uuid.UUID | None
    source: str
    extraction_mode: str
    model: str | None
    interest: str
    budget_min: float | None
    budget_max: float | None
    budget_currency: str | None
    budget_evidence: str | None
    timeline: str | None
    timeline_evidence: str | None
    decision_maker: str | None
    decision_maker_evidence: str | None
    objections: list | None
    next_step: str | None
    summary: str
    simulated: bool
    created_at: object
    warnings: list[str] = []


class RunIn(BaseModel):
    business_id: uuid.UUID
    template_key: str = Field(default="general_smb", max_length=60)
    image_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)
    generate_website: bool = True
    use_ai: bool = False
    agent_id: uuid.UUID | None = None
    place_call: bool = False


class RunOut(_ORM):
    id: uuid.UUID
    business_id: uuid.UUID
    lead_id: uuid.UUID | None
    website_project_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    call_id: uuid.UUID | None
    status: str
    steps: list
    created_at: object
    updated_at: object
    outcome: OutcomeOut | None = None


def _run_out(db, run: PipelineRun) -> RunOut:
    o = RunOut.model_validate(run)
    oc = svc.latest_outcome(db, run.organization_id, run.lead_id)
    o.outcome = OutcomeOut.model_validate(oc) if oc else None
    return o


# ------------------------------------------------------------------ Google photos (display-only proxy)
@router.get("/businesses/{business_id}/google-photos")
def google_photos(business_id: uuid.UUID, ctx: TenantContext = Depends(B_READ), db: Session = Depends(get_db)):
    b = discovery.get_business(db, ctx, business_id)
    return {"photos": photos.list_photo_refs(db, ctx.organization_id, b.id), "notice": photos.TOS_NOTE}


@router.get("/businesses/{business_id}/google-photos/media")
def google_photo_media(business_id: uuid.UUID, name: str = Query(min_length=10, max_length=500),
                       max_width: int = Query(800, ge=64, le=1600), ctx: TenantContext = Depends(B_READ),
                       db: Session = Depends(get_db)):
    b = discovery.get_business(db, ctx, business_id)
    data, ctype, attributions = photos.fetch_photo(db, ctx.organization_id, b.id, name, max_width)
    # Streamed straight through; never persisted. Attribution travels with every response.
    return Response(content=data, media_type=ctype, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "X-Photo-Source": "google_places",
        "X-Photo-Attribution": quote(json.dumps(attributions, ensure_ascii=False)),
        "Access-Control-Expose-Headers": "X-Photo-Attribution, X-Photo-Source"})


# ------------------------------------------------------------------ business-owned images
@router.get("/businesses/{business_id}/images", response_model=list[ImageOut])
def list_images(business_id: uuid.UUID, ctx: TenantContext = Depends(B_READ), db: Session = Depends(get_db)):
    b = discovery.get_business(db, ctx, business_id)
    rows = db.scalars(select(BusinessImage).where(BusinessImage.organization_id == ctx.organization_id,
                                                  BusinessImage.business_id == b.id)
                      .order_by(BusinessImage.created_at)).all()
    return [_img_out(i) for i in rows]


@router.post("/businesses/{business_id}/images", response_model=ImageOut, status_code=201)
async def upload_image(business_id: uuid.UUID, request: Request, file: UploadFile = File(...),
                       permission_confirmed: bool = Form(False), alt: str | None = Form(None, max_length=300),
                       ctx: TenantContext = Depends(B_WRITE), db: Session = Depends(get_db)):
    if not permission_confirmed:
        raise AppError(422, "permission_required",
                       "Confirm 'I have permission to use these images' before uploading")
    b = discovery.get_business(db, ctx, business_id)
    data = await file.read(pipeline_config().image_max_bytes + 1)
    from app.core.scanning import scan_bytes

    scan_bytes(data, file.filename or "image")
    img = images.create_image(db, ctx, b, data, source="owner_supplied", permission_confirmed=True,
                              filename=file.filename, alt=alt)
    audit(db, "business_image.upload", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="business_image", entity_id=img.id, request=request,
          data={"business_id": str(b.id), "permission_confirmed": True, "size": img.size_bytes})
    db.commit()
    return _img_out(img)


@router.post("/businesses/{business_id}/images/import-website")
def import_website_images(business_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(B_WRITE),
                          db: Session = Depends(get_db)):
    b = discovery.get_business(db, ctx, business_id)
    res = images.import_from_website(db, ctx, b)
    audit(db, "business_image.import_website", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="business", entity_id=b.id, request=request,
          data={"imported": len(res["imported"]), "skipped": len(res["skipped"])})
    db.commit()
    return {"imported": [_img_out(i) for i in res["imported"]], "skipped": res["skipped"],
            "notice": "Images found on the business's own website need your confirmation of permission before "
                      "they can be used."}


@router.post("/businesses/{business_id}/images/{image_id}/approve", response_model=ImageOut)
def approve_image(business_id: uuid.UUID, image_id: uuid.UUID, body: ApproveIn, request: Request,
                  ctx: TenantContext = Depends(B_WRITE), db: Session = Depends(get_db)):
    if not body.permission_confirmed:
        raise AppError(422, "permission_required", "Confirm you have permission to use this image")
    discovery.get_business(db, ctx, business_id)
    img = images.get_image(db, ctx, business_id, image_id)
    img.status, img.permission_confirmed = "approved", True
    img.permission_confirmed_by, img.permission_confirmed_at = ctx.user.id, utcnow()
    if body.alt:
        img.alt = body.alt
    audit(db, "business_image.approve", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="business_image", entity_id=img.id, request=request, data={"source": img.source})
    db.commit()
    return _img_out(img)


@router.post("/businesses/{business_id}/images/{image_id}/reject", response_model=ImageOut)
def reject_image(business_id: uuid.UUID, image_id: uuid.UUID, ctx: TenantContext = Depends(B_WRITE),
                 db: Session = Depends(get_db)):
    discovery.get_business(db, ctx, business_id)
    img = images.get_image(db, ctx, business_id, image_id)
    img.status, img.permission_confirmed = "rejected", False
    db.commit()
    return _img_out(img)


@router.delete("/businesses/{business_id}/images/{image_id}", status_code=204)
def delete_image(business_id: uuid.UUID, image_id: uuid.UUID, request: Request,
                 ctx: TenantContext = Depends(B_WRITE), db: Session = Depends(get_db)):
    discovery.get_business(db, ctx, business_id)
    img = images.get_image(db, ctx, business_id, image_id)
    db.delete(img)
    audit(db, "business_image.delete", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="business_image", entity_id=image_id, request=request)
    db.commit()


@router.get("/businesses/{business_id}/images/{image_id}/content")
def image_content(business_id: uuid.UUID, image_id: uuid.UUID, ctx: TenantContext = Depends(B_READ),
                  db: Session = Depends(get_db)):
    discovery.get_business(db, ctx, business_id)
    img = images.get_image(db, ctx, business_id, image_id)
    return Response(content=img.data, media_type=img.content_type,
                    headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@public_router.get("/public/media/{token}")
def public_media(token: str, request: Request, db: Session = Depends(get_db)):
    """Serves ONLY approved, permission-confirmed business images (used by generated websites)."""
    ip = request.client.host if request.client else "unknown"
    if not limiter.hit(f"media:{ip}", 600):
        raise AppError(429, "rate_limited", "Too many requests")
    if not (20 <= len(token) <= 64):
        raise AppError(404, "not_found", "Not found")
    if db.get_bind().dialect.name == "postgresql":
        org = db.scalar(text("SELECT business_image_org_by_token(:t)"), {"t": token})
        if org is None:
            raise AppError(404, "not_found", "Not found")
        set_tenant(db, org)
    img = db.scalar(select(BusinessImage).where(BusinessImage.public_token == token))
    if img is None or img.status != "approved" or not img.permission_confirmed:
        raise AppError(404, "not_found", "Not found")
    return Response(content=img.data, media_type=img.content_type,
                    headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
                             "Cross-Origin-Resource-Policy": "cross-origin"})


# ------------------------------------------------------------------ packages + budget agent
@router.get("/pipeline/packages", response_model=PackagesIn)
def get_packages(ctx: TenantContext = Depends(A_READ), db: Session = Depends(get_db)):
    row = svc.get_settings_row(db, ctx.organization_id)
    return PackagesIn(packages=(row.packages if row else []) or [])


@router.put("/pipeline/packages", response_model=PackagesIn)
def put_packages(body: PackagesIn, request: Request, ctx: TenantContext = Depends(A_WRITE),
                 db: Session = Depends(get_db)):
    row = svc.get_settings_row(db, ctx.organization_id)
    if row is None:
        row = PipelineSettings(organization_id=ctx.organization_id, packages=[])
        db.add(row)
    row.packages = [p.model_dump() for p in body.packages]
    audit(db, "pipeline.packages.update", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="pipeline_settings", entity_id=None, request=request, data={"count": len(body.packages)})
    db.commit()
    return PackagesIn(packages=row.packages)


@router.post("/pipeline/budget-agent", status_code=201)
def create_budget_agent(body: BudgetAgentIn, request: Request, ctx: TenantContext = Depends(A_WRITE),
                        db: Session = Depends(get_db)):
    from app.modules.agents.router import _create
    from app.modules.agents.schemas import AgentOut
    from app.modules.agents.templates import TEMPLATES_BY_KEY

    tpl = TEMPLATES_BY_KEY["website_sales_budget_discovery"]
    data = {k: v for k, v in tpl.items() if k != "key"}
    data["compliance_disclosure"] = data["compliance_disclosure"].format(
        business=body.business_name or "our business")
    row = svc.get_settings_row(db, ctx.organization_id)
    data["business_info"] = svc.packages_text((row.packages if row else []) or [])
    if body.name:
        data["name"] = body.name
    return AgentOut.model_validate(_create(db, ctx, data, request, template_key=tpl["key"]))


# ------------------------------------------------------------------ outcomes
@router.post("/pipeline/outcomes/extract", response_model=OutcomeOut, status_code=201)
def extract_outcome(body: ExtractIn, request: Request, ctx: TenantContext = Depends(A_READ),
                    db: Session = Depends(get_db)):
    from app.modules.agents import service as agents
    from app.modules.voice.models import CallSession, CallTranscript

    lead = None
    if body.lead_id:
        ctx.require("leads:write")
        lead = svc.require_lead(db, ctx, body.lead_id)
    if body.agent_id:
        agents.get_agent(db, ctx, body.agent_id)
    transcript = [t.model_dump() for t in body.transcript]
    simulated = False
    if body.call_id:
        call = db.scalar(select(CallSession).where(CallSession.id == body.call_id,
                                                   CallSession.organization_id == ctx.organization_id))
        if call is None:
            raise svc.not_found("Call")
        simulated = call.simulated
        if not transcript:
            transcript = [{"role": "contact" if t.speaker == "contact" else t.speaker, "text": t.text}
                          for t in db.scalars(select(CallTranscript).where(
                              CallTranscript.call_id == call.id,
                              CallTranscript.organization_id == ctx.organization_id).order_by(CallTranscript.seq))]
        if lead is None and call.lead_id:
            lead = svc.require_lead(db, ctx, call.lead_id)
    if not transcript:
        raise AppError(422, "empty_transcript", "Provide a transcript (or a call that has one)")
    o = extraction.extract(transcript, body.mode)
    row = svc.save_outcome(db, ctx, o, transcript=transcript, source=body.source, lead=lead,
                           agent_id=body.agent_id, call_id=body.call_id, simulated=simulated)
    audit(db, "conversation.outcome", org_id=ctx.organization_id, user_id=ctx.user.id,
          entity_type="conversation_outcome", entity_id=row.id, request=request,
          data={"mode": o.extraction_mode, "lead_id": str(lead.id) if lead else None})
    db.commit()
    out = OutcomeOut.model_validate(row)
    out.warnings = o.warnings
    return out


@router.get("/pipeline/outcomes", response_model=list[OutcomeOut])
def list_outcomes(ctx: TenantContext = Depends(A_READ), db: Session = Depends(get_db),
                  lead_id: uuid.UUID | None = None, agent_id: uuid.UUID | None = None,
                  limit: int = Query(20, ge=1, le=100)):
    q = select(ConversationOutcome).where(ConversationOutcome.organization_id == ctx.organization_id)
    if lead_id:
        q = q.where(ConversationOutcome.lead_id == lead_id)
    if agent_id:
        q = q.where(ConversationOutcome.agent_id == agent_id)
    return db.scalars(q.order_by(ConversationOutcome.created_at.desc()).limit(limit)).all()


# ------------------------------------------------------------------ one-click pipeline
@router.post("/pipeline/run", response_model=RunOut)
def run_pipeline(body: RunIn, request: Request, ctx: TenantContext = Depends(L_WRITE),
                 db: Session = Depends(get_db)):
    return _run_out(db, svc.run_pipeline(db, ctx, body, request))


@router.get("/pipeline/runs", response_model=list[RunOut])
def list_runs(ctx: TenantContext = Depends(B_READ), db: Session = Depends(get_db),
              business_id: uuid.UUID | None = None, limit: int = Query(20, ge=1, le=100)):
    q = select(PipelineRun).where(PipelineRun.organization_id == ctx.organization_id)
    if business_id:
        q = q.where(PipelineRun.business_id == business_id)
    return [_run_out(db, r) for r in db.scalars(q.order_by(PipelineRun.updated_at.desc()).limit(limit))]


@router.get("/pipeline/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, ctx: TenantContext = Depends(B_READ), db: Session = Depends(get_db)):
    run = db.scalar(select(PipelineRun).where(PipelineRun.id == run_id,
                                              PipelineRun.organization_id == ctx.organization_id))
    if run is None:
        raise svc.not_found("Pipeline run")
    return _run_out(db, run)
