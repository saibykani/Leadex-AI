"""Agent domain rules. Other modules (voice, campaigns) call these functions; never the tables directly.

Languages: `en` is enabled. `hi` and `te` are `evaluation_pending`: agents may be drafted, tested and published in
those languages, but `live_call_blockers()` refuses live calls until an AgentEvaluation(kind='language',
language=<code>, passed=True) exists for that agent. Only Owners/Admins may record evaluations.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.agents.config import ai_settings
from app.modules.agents.llm import ModelSpec
from app.modules.agents.models import AgentEvaluation, AgentVersion, AIAgent, ModelConfiguration
from app.modules.agents.tools import TOOLS
from app.modules.billing.service import register_counter

LANGUAGES: dict[str, dict] = {
    "en": {"name": "English", "status": "enabled"},
    "hi": {"name": "Hindi", "status": "evaluation_pending"},
    "te": {"name": "Telugu", "status": "evaluation_pending"},
    "ta": {"name": "Tamil", "status": "evaluation_pending"},
    "kn": {"name": "Kannada", "status": "evaluation_pending"},
    "ml": {"name": "Malayalam", "status": "evaluation_pending"},
    "mr": {"name": "Marathi", "status": "evaluation_pending"},
    "bn": {"name": "Bengali", "status": "evaluation_pending"},
    "gu": {"name": "Gujarati", "status": "evaluation_pending"},
}
STATUSES = ("draft", "published", "killed")
EVALUATOR_ROLES = frozenset({"Owner", "Admin"})
SNAPSHOT_FIELDS = (
    "name", "purpose", "industry", "personality", "voice", "language", "speaking_rate", "greeting", "business_info",
    "qualification_questions", "conversation_flow", "objection_handling", "tools", "escalation_policy",
    "max_call_seconds", "business_hours", "compliance_disclosure", "model_config_id",
)


def get_agent(db: Session, ctx: TenantContext, agent_id: uuid.UUID) -> AIAgent:
    agent = db.scalar(select(AIAgent).where(AIAgent.id == agent_id, AIAgent.organization_id == ctx.organization_id,
                                            AIAgent.deleted_at.is_(None)))
    if agent is None:
        raise AppError(404, "not_found", "Agent not found")
    return agent


def get_agent_for_org(db: Session, org_id: uuid.UUID, agent_id: uuid.UUID) -> AIAgent | None:
    return db.scalar(select(AIAgent).where(AIAgent.id == agent_id, AIAgent.organization_id == org_id,
                                           AIAgent.deleted_at.is_(None)))


def validate_fields(db: Session, ctx: TenantContext, data: dict) -> None:
    lang = data.get("language")
    if lang is not None and lang not in LANGUAGES:
        raise AppError(422, "unsupported_language", f"Language must be one of {sorted(LANGUAGES)}")
    unknown = sorted(set(data.get("tools") or []) - set(TOOLS))
    if unknown:
        raise AppError(422, "unknown_tool", "Unknown tools in allow-list",
                       {"unknown": unknown, "catalog": sorted(TOOLS)})
    if data.get("model_config_id"):
        mc = db.scalar(select(ModelConfiguration).where(ModelConfiguration.id == data["model_config_id"],
                                                        ModelConfiguration.organization_id == ctx.organization_id))
        if mc is None:
            raise AppError(422, "invalid_model_config", "model_config_id not found in this organization")


def snapshot(agent: AIAgent) -> dict:
    out = {}
    for f in SNAPSHOT_FIELDS:
        v = getattr(agent, f)
        out[f] = str(v) if isinstance(v, uuid.UUID) else v
    return out


def publish(db: Session, ctx: TenantContext, agent: AIAgent) -> AgentVersion:
    if agent.status == "killed":
        raise AppError(409, "agent_killed", "Agent is killed; reactivate it before publishing")
    problems = []
    if not (agent.compliance_disclosure or "").strip():
        problems.append("compliance_disclosure is required")
    if not (agent.greeting or "").strip():
        problems.append("greeting is required")
    if problems:
        raise AppError(422, "not_publishable", "Agent cannot be published", {"problems": problems})
    current = db.scalar(select(func.max(AgentVersion.version)).where(AgentVersion.agent_id == agent.id)) or 0
    v = AgentVersion(organization_id=ctx.organization_id, agent_id=agent.id, version=current + 1,
                     snapshot=snapshot(agent), published_by_user_id=ctx.user.id)
    db.add(v)
    agent.status, agent.published_version = "published", v.version
    return v


def language_evaluated(db: Session, org_id: uuid.UUID, agent_id: uuid.UUID, language: str) -> bool:
    return db.scalar(select(AgentEvaluation.id).where(
        AgentEvaluation.organization_id == org_id, AgentEvaluation.agent_id == agent_id,
        AgentEvaluation.kind == "language", AgentEvaluation.language == language,
        AgentEvaluation.passed.is_(True)).limit(1)) is not None


def live_call_blockers(db: Session, org_id: uuid.UUID, agent: AIAgent) -> list[str]:
    """Agent-side reasons a live call must not happen (compliance gate reasons are added by the caller)."""
    reasons = []
    if ai_settings().voice_kill_switch:
        reasons.append("global_kill_switch")
    if agent.status == "killed":
        reasons.append("agent_killed")
    elif agent.status != "published":
        reasons.append("agent_not_published")
    lang = LANGUAGES.get(agent.language)
    if lang is None:
        reasons.append(f"language_unsupported:{agent.language}")
    elif lang["status"] != "enabled" and not language_evaluated(db, org_id, agent.id, agent.language):
        reasons.append(f"language_evaluation_pending:{agent.language}")
    return reasons


def model_spec(db: Session, agent: AIAgent, override: str | None) -> ModelSpec:
    mc = db.get(ModelConfiguration, agent.model_config_id) if agent.model_config_id else None
    if mc is not None and mc.organization_id != agent.organization_id:
        mc = None
    if override == "simulated":
        return ModelSpec()
    if override == "openai":
        from app.modules.agents.llm import fast_spec

        fs = fast_spec(mc.temperature if mc else 0.4, mc.max_tokens if mc else 512)
        if fs:
            return fs
        override = "ollama"
    if override == "ollama" and (mc is None or mc.provider != "ollama"):
        return ModelSpec(provider="ollama", model=ai_settings().ollama_chat_model)
    if mc is None:
        return ModelSpec()
    return ModelSpec(mc.provider, mc.model, mc.temperature, mc.max_tokens, mc.base_url)


def count_active_agents(db: Session, org_id: uuid.UUID) -> int:
    """Billing counter for the 'active_agents' plan limit: published (live) agents that are not deleted."""
    return db.scalar(select(func.count()).select_from(AIAgent).where(
        AIAgent.organization_id == org_id, AIAgent.status == "published", AIAgent.deleted_at.is_(None))) or 0


register_counter("active_agents", count_active_agents)
