"""Growth insights (read-only analytics) and the first-run onboarding checklist."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.identity.models import Organization, OrganizationMembership
from app.modules.insights import service as svc
from app.modules.insights.models import OnboardingProgress

router = APIRouter(tags=["insights"])
READ = require_permission("leads:read")
MEMBER = require_permission("org:read")
ORG_WRITE = require_permission("org:write")


@router.get("/insights/overview")
def get_overview(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                 days: int = Query(30, ge=7, le=90)):
    return svc.overview(db, ctx.organization_id, days)


@router.get("/insights/pipeline-value")
def get_pipeline_value(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return svc.pipeline_value(db, ctx.organization_id)


@router.get("/insights/forecast")
def get_forecast(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return svc.forecast(db, ctx.organization_id)


@router.get("/insights/briefing")
def get_briefing(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db), polish: bool = False):
    return svc.briefing(db, ctx.organization_id, polish)


@router.get("/insights/analytics")
def get_analytics(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                  weeks: int = Query(8, ge=4, le=26)):
    return svc.analytics(db, ctx.organization_id, weeks)


@router.get("/insights/opportunities")
def get_opportunities(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                      limit: int = Query(6, ge=1, le=50)):
    return svc.top_opportunities(db, ctx.organization_id, limit)


# ================================================================ onboarding
STEPS = (
    ("profile", "Company profile"),
    ("integrations", "Review integrations"),
    ("businesses", "Import or discover businesses"),
    ("agent", "Create your first AI agent"),
    ("website", "Generate a website demo"),
    ("teammate", "Invite a teammate"),
)
STEP_KEYS = tuple(k for k, _ in STEPS)


class ProfileIn(BaseModel):
    industry: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    team_size: str | None = Field(default=None, max_length=40)
    goal: str | None = Field(default=None, max_length=300)
    website: str | None = Field(default=None, max_length=300)


class StepIn(BaseModel):
    step: Literal["profile", "integrations", "businesses", "agent", "website", "teammate"]
    action: Literal["complete", "skip", "reset"] = "complete"
    profile: ProfileIn | None = None


def _progress(db: Session, org) -> OnboardingProgress | None:
    return db.scalar(select(OnboardingProgress).where(OnboardingProgress.organization_id == org))


def onboarding_state(db: Session, ctx: TenantContext) -> dict:
    org = ctx.organization_id
    p = _progress(db, org)
    stored = (p.steps if p else {}) or {}
    f = svc.facts(db, org)
    members = db.scalar(select(func.count()).select_from(OrganizationMembership).where(
        OrganizationMembership.organization_id == org, OrganizationMembership.status == "active")) or 0
    derived = {
        "profile": bool(p and p.profile),
        "integrations": False,
        "businesses": f["businesses"] > 0 or f["total_leads"] > 0,
        "agent": f["agents"] > 0,
        "website": f["websites_total"] > 0,
        "teammate": members > 1,
    }
    evidence = {"businesses": f"{f['businesses']} businesses, {f['total_leads']} leads",
                "agent": f"{f['agents']} agents", "website": f"{f['websites_total']} websites",
                "teammate": f"{members} members"}
    steps = []
    for key, title in STEPS:
        s = stored.get(key) or {}
        done = derived[key] or s.get("state") == "complete"
        steps.append({"key": key, "title": title, "done": done, "skipped": not done and s.get("state") == "skip",
                      "source": "data" if derived[key] else ("manual" if s.get("state") else None),
                      "evidence": evidence.get(key)})
    org_row = db.get(Organization, org)
    completed = sum(1 for s in steps if s["done"])
    return {"steps": steps, "completed": completed, "total": len(steps),
            "percent": round(completed * 100 / len(steps)), "profile": (p.profile if p else None) or {},
            "organization": {"name": org_row.name if org_row else None,
                             "country_code": org_row.country_code if org_row else None}}


@router.get("/onboarding")
def get_onboarding(ctx: TenantContext = Depends(MEMBER), db: Session = Depends(get_db)):
    return onboarding_state(db, ctx)


@router.post("/onboarding/step")
def update_step(body: StepIn, request: Request, ctx: TenantContext = Depends(ORG_WRITE),
                db: Session = Depends(get_db)):
    p = _progress(db, ctx.organization_id)
    if p is None:
        p = OnboardingProgress(organization_id=ctx.organization_id, steps={})
        db.add(p)
    steps = dict(p.steps or {})
    if body.action == "reset":
        steps.pop(body.step, None)
    else:
        steps[body.step] = {"state": body.action, "at": utcnow().isoformat(), "by": str(ctx.user.id)}
    p.steps = steps
    if body.step == "profile" and body.profile is not None and body.action == "complete":
        p.profile = body.profile.model_dump(exclude_none=True)
    audit(db, "onboarding.step", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="onboarding",
          data={"step": body.step, "action": body.action}, request=request)
    db.commit()
    return onboarding_state(db, ctx)
