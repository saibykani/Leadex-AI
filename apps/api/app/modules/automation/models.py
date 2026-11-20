import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


class Workflow(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflows"
    __table_args__ = (Index("ix_workflows_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | active | paused | archived
    trigger_type: Mapped[str | None] = mapped_column(String(40))  # of the current version
    draft_graph: Mapped[dict | None] = mapped_column(JSON)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column()  # no FK: avoids a workflows<->versions cycle
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowVersion(IdMixin, Base):
    """Immutable published graph."""

    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_wf_version"),)
    organization_id: Mapped[uuid.UUID] = _org()
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    graph: Mapped[dict] = mapped_column(JSON)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkflowNode(IdMixin, Base):
    """Denormalized node rows per version (for querying by type, e.g. 'which workflows send email')."""

    __tablename__ = "workflow_nodes"
    __table_args__ = (Index("ix_workflow_nodes_org_version", "organization_id", "version_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    node_key: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict | None] = mapped_column(JSON)


class WorkflowExecution(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "idempotency_key", name="uq_workflow_executions_idem"),
        Index("ix_workflow_executions_org_wf_created", "organization_id", "workflow_id", "created_at"),
        Index("ix_workflow_executions_org_status_resume", "organization_id", "status", "resume_at"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    # queued | running | waiting | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued")
    trigger_type: Mapped[str] = mapped_column(String(40))
    trigger_payload: Mapped[dict | None] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[dict | None] = mapped_column(JSON)  # {"outputs": {}, "resolved": {}, "waiting_on": str|None}
    resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    started_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowExecutionEvent(IdMixin, Base):
    """Append-only per-node log: started | succeeded | failed | retried | skipped | waiting_approval | waiting_delay."""

    __tablename__ = "workflow_execution_events"
    __table_args__ = (Index("ix_wf_exec_events_org_exec", "organization_id", "execution_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_executions.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    node_key: Mapped[str | None] = mapped_column(String(80))
    node_type: Mapped[str | None] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(30))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkflowApproval(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_approvals"
    __table_args__ = (
        UniqueConstraint("execution_id", "node_key", name="uq_workflow_approvals_exec_node"),
        Index("ix_workflow_approvals_org_status", "organization_id", "status"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_executions.id", ondelete="CASCADE"))
    node_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    message: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)


class AutomationSettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "automation_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_automation_settings_org"),)
    organization_id: Mapped[uuid.UUID] = _org()
    allowed_hosts: Mapped[list | None] = mapped_column(JSON)  # api_request / webhook_out host allow-list


class WorkflowWebhook(Base):
    """Public webhook lookup. Deliberately NOT under RLS: the unauthenticated hook endpoint must find the tenant
    before it can bind it. Holds only a SHA-256 of the secret, never the secret itself."""

    __tablename__ = "workflow_webhooks"
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = _org()
    secret_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
