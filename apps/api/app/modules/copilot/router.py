from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.copilot import service as svc

router = APIRouter(tags=["copilot"])
READ = require_permission("leads:read")


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    mode: Literal["auto", "llm", "rules"] = "auto"


@router.get("/copilot/suggestions")
def suggestions(ctx: TenantContext = Depends(READ)):
    return {"suggestions": svc.SUGGESTIONS, "tools": svc.TOOL_DOCS}


@router.post("/copilot/ask")
def ask(body: AskIn, request: Request, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    out = svc.ask(db, ctx.organization_id, body.question, body.mode)
    # Record that a read happened (question + tool only; no result data).
    audit(db, "copilot.ask", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="copilot",
          data={"tool": out["tool"], "mode": out["mode"], "refused": out["refused"], "q": body.question[:200]},
          request=request)
    db.commit()
    return out
