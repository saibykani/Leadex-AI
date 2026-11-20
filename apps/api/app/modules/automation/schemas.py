import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Graph(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    graph: Graph | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    graph: Graph | None = None
    status: str | None = Field(None, pattern="^(active|paused|archived)$")


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    trigger_type: str | None
    draft_graph: dict | None
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class WorkflowCreated(WorkflowOut):
    webhook_secret: str | None = None  # returned once on creation / rotation only


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    version: int
    graph: dict
    created_at: datetime


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]


class ExecuteBody(BaseModel):
    payload: dict = Field(default_factory=dict)


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    trigger_type: str
    trigger_payload: dict | None
    idempotency_key: str
    resume_at: datetime | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    seq: int
    node_key: str | None
    node_type: str | None
    event: str
    attempt: int
    output: dict | None
    error: str | None
    created_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    execution_id: uuid.UUID
    node_key: str
    status: str
    message: str | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    comment: str | None


class Decision(BaseModel):
    comment: str | None = Field(None, max_length=2000)


class SettingsBody(BaseModel):
    allowed_hosts: list[str] = Field(default_factory=list, max_length=100)


class Analytics(BaseModel):
    total: int
    by_status: dict[str, int]
    success_rate: float | None
    failed_nodes: dict[str, int]
