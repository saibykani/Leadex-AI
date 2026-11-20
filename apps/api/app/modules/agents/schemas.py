import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AgentBase(BaseModel):
    purpose: str | None = Field(default=None, max_length=2000)
    industry: str | None = Field(default=None, max_length=120)
    personality: str | None = Field(default=None, max_length=2000)
    voice: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=10)
    speaking_rate: float | None = Field(default=None, ge=0.5, le=2.0)
    greeting: str | None = Field(default=None, max_length=2000)
    business_info: str | None = Field(default=None, max_length=20000)
    qualification_questions: list[str] | None = Field(default=None, max_length=50)
    conversation_flow: list[str] | None = Field(default=None, max_length=50)
    objection_handling: list[dict] | None = Field(default=None, max_length=50)
    tools: list[str] | None = Field(default=None, max_length=20)
    escalation_policy: str | None = Field(default=None, max_length=2000)
    max_call_seconds: int | None = Field(default=None, ge=30, le=3600)
    business_hours: dict | None = None
    model_config_id: uuid.UUID | None = None


class AgentCreate(AgentBase):
    name: str = Field(min_length=1, max_length=200)
    compliance_disclosure: str = Field(min_length=10, max_length=2000)


class AgentUpdate(AgentBase):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    compliance_disclosure: str | None = Field(default=None, min_length=10, max_length=2000)


class AgentOut(_ORM):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    purpose: str | None
    industry: str | None
    personality: str | None
    voice: str | None
    language: str
    speaking_rate: float
    greeting: str | None
    business_info: str | None
    qualification_questions: list | None
    conversation_flow: list | None
    objection_handling: list | None
    tools: list | None
    escalation_policy: str | None
    max_call_seconds: int
    business_hours: dict | None
    compliance_disclosure: str
    status: str
    template_key: str | None
    model_config_id: uuid.UUID | None
    published_version: int | None
    created_at: datetime
    updated_at: datetime


class FromTemplate(BaseModel):
    template_key: str = Field(max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=200)


class VersionOut(_ORM):
    id: uuid.UUID
    agent_id: uuid.UUID
    version: int
    snapshot: dict
    published_by_user_id: uuid.UUID | None
    created_at: datetime


class ModelConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["ollama", "openai", "simulated"]
    model: str = Field(default="template", min_length=1, max_length=120)
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=16, le=8192)
    base_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")


class ModelConfigOut(_ORM):
    id: uuid.UUID
    name: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    base_url: str | None
    created_at: datetime


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)


class KnowledgeOut(_ORM):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    version: int
    chunk_count: int
    embedding_status: str
    created_at: datetime
    updated_at: datetime


class EvaluationIn(BaseModel):
    kind: Literal["language", "quality", "safety"] = "language"
    language: str | None = Field(default=None, max_length=10)
    passed: bool
    score: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=5000)


class EvaluationOut(_ORM):
    id: uuid.UUID
    agent_id: uuid.UUID
    kind: str
    language: str | None
    passed: bool
    score: float | None
    notes: str | None
    evaluated_by_user_id: uuid.UUID | None
    created_at: datetime


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ToolInvocation(BaseModel):
    name: str = Field(max_length=60)
    arguments: dict = Field(default_factory=dict)


class TestRequest(BaseModel):
    __test__ = False  # not a pytest class
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    provider: Literal["ollama", "openai", "simulated"] | None = None  # override the agent's configured provider
    use_knowledge: bool = True
    invoke_tools: list[ToolInvocation] = Field(default_factory=list, max_length=5)
    dry_run: bool = True  # side-effect tools only report what they would do


class TestResponse(BaseModel):
    __test__ = False
    run_id: uuid.UUID
    status: Literal["ok", "error", "not_configured"]
    reply: str
    simulated: bool
    provider: str
    model: str | None
    latency_ms: int
    tool_calls: list[dict]
    citations: list[dict]
    retrieval_mode: str
    error: str | None
    steps: list[dict]


class RunOut(_ORM):
    id: uuid.UUID
    agent_id: uuid.UUID
    kind: str
    input: dict | None
    output: str | None
    latency_ms: int
    tool_calls: list | None
    citations: list | None
    retrieval_mode: str | None
    provider: str
    model: str | None
    error: str | None
    simulated: bool
    created_at: datetime
