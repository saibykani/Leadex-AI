import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


def _agent() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("ai_agents.id", ondelete="CASCADE"))


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ModelConfiguration(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_configurations"
    __table_args__ = (Index("ix_model_configurations_org", "organization_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(20), default="simulated")  # ollama | simulated
    model: Mapped[str] = mapped_column(String(120), default="template")
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=512)
    base_url: Mapped[str | None] = mapped_column(String(500))


class AIAgent(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_agents"
    __table_args__ = (Index("ix_ai_agents_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(120))
    personality: Mapped[str | None] = mapped_column(Text)
    voice: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(10), default="en")
    speaking_rate: Mapped[float] = mapped_column(Float, default=1.0)
    greeting: Mapped[str | None] = mapped_column(Text)
    business_info: Mapped[str | None] = mapped_column(Text)
    qualification_questions: Mapped[list | None] = mapped_column(JSON)
    conversation_flow: Mapped[list | None] = mapped_column(JSON)
    objection_handling: Mapped[list | None] = mapped_column(JSON)
    tools: Mapped[list | None] = mapped_column(JSON)  # allow-list of tool keys
    escalation_policy: Mapped[str | None] = mapped_column(Text)
    max_call_seconds: Mapped[int] = mapped_column(Integer, default=300)
    business_hours: Mapped[dict | None] = mapped_column(JSON)
    compliance_disclosure: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | published | killed
    template_key: Mapped[str | None] = mapped_column(String(60))
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_configurations.id", ondelete="SET NULL"))
    published_version: Mapped[int | None] = mapped_column(Integer)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentVersion(IdMixin, Base):
    """Immutable snapshot written on every publish (append-only)."""

    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
                      Index("ix_agent_versions_org_agent", "organization_id", "agent_id"))
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = _agent()
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()


class AgentTool(IdMixin, Base):
    """Global tool catalog (no tenant data). Source of truth is app.modules.agents.tools.TOOLS."""

    __tablename__ = "agent_tools"
    key: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    side_effect: Mapped[bool] = mapped_column(Boolean, default=False)
    contacts_person: Mapped[bool] = mapped_column(Boolean, default=False)
    required_permission: Mapped[str] = mapped_column(String(100))


class AgentKnowledge(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_knowledge"
    __table_args__ = (Index("ix_agent_knowledge_org_agent", "organization_id", "agent_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = _agent()
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")  # embedded|keyword_only|partial


class KnowledgeChunk(IdMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunks_org_agent", "organization_id", "agent_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = _agent()
    knowledge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_knowledge.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")  # embedded | keyword_only
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created()


class AgentEvaluation(IdMixin, Base):
    """Evaluation records (append-only). A passed `language` evaluation unlocks that language for live calls."""

    __tablename__ = "agent_evaluations"
    __table_args__ = (Index("ix_agent_evaluations_org_agent", "organization_id", "agent_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = _agent()
    kind: Mapped[str] = mapped_column(String(30), default="language")
    language: Mapped[str | None] = mapped_column(String(10))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    evaluated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()


class AgentRun(IdMixin, Base):
    """One orchestrator execution (append-only)."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_org_agent_created", "organization_id", "agent_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    agent_id: Mapped[uuid.UUID] = _agent()
    kind: Mapped[str] = mapped_column(String(20), default="test")
    input: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[list | None] = mapped_column(JSON)
    citations: Mapped[list | None] = mapped_column(JSON)
    retrieval_mode: Mapped[str | None] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()


class AgentLog(IdMixin, Base):
    """Step-level log lines for a run (append-only)."""

    __tablename__ = "agent_logs"
    __table_args__ = (Index("ix_agent_logs_org_run", "organization_id", "run_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    step: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(10), default="info")
    data: Mapped[dict | None] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created()
