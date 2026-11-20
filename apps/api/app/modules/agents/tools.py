"""Agent tools = thin clients of backend services.

Authorisation (all three must pass, otherwise the call is refused and recorded, never executed):
  1. tool key is in the agent's `tools` allow-list;
  2. the *calling user* holds the tool's `required_permission` in the tenant;
  3. tools that contact a person (`contacts_person=True`) must pass compliance.OutreachGate.
Tools never reach across tenants: every lookup is scoped by TenantContext.organization_id.
"""
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.agents.models import AIAgent


@dataclass(frozen=True)
class ToolSpec:
    key: str
    name: str
    description: str
    required_permission: str
    side_effect: bool
    contacts_person: bool
    parameters: dict  # JSON schema (also sent to Ollama's tool-calling API)


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


_LEAD = {"lead_id": {"type": "string", "description": "Lead UUID"}}

TOOLS: dict[str, ToolSpec] = {t.key: t for t in [
    ToolSpec("crm_lookup", "CRM lookup", "Read a lead's name, status, industry and city.", "leads:read",
             False, False, _schema(_LEAD, ["lead_id"])),
    ToolSpec("create_note", "Create note", "Add a note to a lead's CRM record.", "leads:write", True, False,
             _schema({**_LEAD, "body": {"type": "string"}}, ["lead_id", "body"])),
    ToolSpec("book_callback", "Book callback task", "Create a callback task on a lead.", "leads:write", True,
             False, _schema({**_LEAD, "title": {"type": "string"}, "due_at": {"type": "string",
                                                                                 "format": "date-time"}},
                            ["lead_id"])),
    ToolSpec("schedule_outbound_call", "Schedule outbound call",
             "Request a follow-up call to the lead. Routed through the compliance gate; never dials directly.",
             "calls:initiate", True, True, _schema(_LEAD, ["lead_id"])),
]}


@dataclass
class ToolEnv:
    db: Session
    ctx: TenantContext
    agent: AIAgent
    dry_run: bool = True


def _lead_id(args: dict) -> uuid.UUID:
    try:
        return uuid.UUID(str(args.get("lead_id")))
    except ValueError as e:
        raise ValueError("lead_id must be a UUID") from e


def _lead(env: ToolEnv, args: dict):
    from app.modules.crm import service as crm

    return crm.get_lead(env.db, env.ctx, _lead_id(args))  # 404 AppError if not in this tenant


def _crm_lookup(env: ToolEnv, args: dict) -> dict:
    lead = _lead(env, args)
    return {"lead_id": str(lead.id), "business_name": lead.business_name, "status": lead.status,
            "industry": lead.industry, "city": lead.city}


def _create_note(env: ToolEnv, args: dict) -> dict:
    from app.modules.crm import service as crm
    from app.modules.crm.models import LeadNote

    lead = _lead(env, args)
    body = str(args.get("body") or "").strip()[:5000]
    if not body:
        raise ValueError("body is required")
    if env.dry_run:
        return {"dry_run": True, "would_create": "lead_note", "lead_id": str(lead.id)}
    note = LeadNote(organization_id=env.ctx.organization_id, lead_id=lead.id, author_user_id=env.ctx.user.id,
                    body=f"[AI agent {env.agent.name}] {body}")
    env.db.add(note)
    env.db.flush()
    crm.record_activity(env.db, env.ctx, lead, "note.added", {"note_id": str(note.id), "agent_id": str(env.agent.id)})
    return {"note_id": str(note.id), "lead_id": str(lead.id)}


def _book_callback(env: ToolEnv, args: dict) -> dict:
    from app.modules.crm import service as crm
    from app.modules.crm.models import LeadTask

    lead = _lead(env, args)
    due = None
    if args.get("due_at"):
        try:
            due = datetime.fromisoformat(str(args["due_at"]).replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError("due_at must be ISO-8601") from e
    title = str(args.get("title") or "Callback requested via AI agent")[:300]
    if env.dry_run:
        return {"dry_run": True, "would_create": "lead_task", "lead_id": str(lead.id), "title": title}
    task = LeadTask(organization_id=env.ctx.organization_id, lead_id=lead.id, title=title, due_at=due,
                    created_by_user_id=env.ctx.user.id)
    env.db.add(task)
    env.db.flush()
    crm.record_activity(env.db, env.ctx, lead, "task.created", {"task_id": str(task.id), "agent_id": str(env.agent.id)})
    return {"task_id": str(task.id), "lead_id": str(lead.id)}


def _schedule_call(env: ToolEnv, args: dict) -> dict:
    from app.modules.compliance.gate import check_outreach

    lead = _lead(env, args)
    decision = check_outreach(env.db, env.ctx.organization_id, lead.id, "voice")
    if not decision.allowed:
        return {"blocked": True, "reasons": decision.reasons}
    # Placing the call is the voice module's job (POST /calls with an Idempotency-Key); tools never dial.
    return {"blocked": False, "simulated": decision.simulated, "next_step": "POST /calls", "lead_id": str(lead.id)}


_IMPL: dict[str, Callable[[ToolEnv, dict], dict]] = {
    "crm_lookup": _crm_lookup, "create_note": _create_note, "book_callback": _book_callback,
    "schedule_outbound_call": _schedule_call,
}


def allowed_specs(agent: AIAgent) -> list[ToolSpec]:
    return [TOOLS[k] for k in (agent.tools or []) if k in TOOLS]


def invoke(env: ToolEnv, name: str, args: dict | None) -> dict:
    """Execute one tool call; always returns a record {name, arguments, ok, result|error}."""
    args = args if isinstance(args, dict) else {}
    rec: dict = {"name": name, "arguments": args, "ok": False}
    spec = TOOLS.get(name)
    if spec is None:
        rec["error"] = "unknown_tool"
    elif name not in (env.agent.tools or []):
        rec["error"] = "tool_not_allowed"
    elif spec.required_permission not in env.ctx.permissions:
        rec["error"] = f"missing_permission:{spec.required_permission}"
    else:
        try:
            rec["result"] = _IMPL[name](env, args)
            rec["ok"] = not rec["result"].get("blocked", False)
            if rec["result"].get("blocked"):
                rec["error"] = "blocked_by_compliance_gate"
        except AppError as e:
            rec["error"] = e.code
        except ValueError as e:
            rec["error"] = f"invalid_arguments:{e}"
    return rec
