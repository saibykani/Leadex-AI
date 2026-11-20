"""automation: workflows, versions, nodes, executions, events, approvals, settings, webhooks

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"
RLS_TABLES = ("workflows", "workflow_versions", "workflow_nodes", "workflow_executions", "workflow_execution_events",
              "workflow_approvals", "automation_settings")
APPEND_ONLY = ("workflow_execution_events",)
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _user(name):
    return sa.Column(name, sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"))


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("trigger_type", sa.String(40)),
        sa.Column("draft_graph", sa.JSON),
        sa.Column("current_version_id", sa.Uuid),
        _user("created_by_user_id"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_workflows_org_status", "workflows", ["organization_id", "status"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("workflow_id", sa.Uuid, sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("graph", sa.JSON, nullable=False),
        _user("created_by_user_id"),
        TS("created_at"),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_wf_version"),
    )

    op.create_table(
        "workflow_nodes",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_key", sa.String(80), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("config", sa.JSON),
    )
    op.create_index("ix_workflow_nodes_org_version", "workflow_nodes", ["organization_id", "version_id"])

    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("workflow_id", sa.Uuid, sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("trigger_type", sa.String(40), nullable=False),
        sa.Column("trigger_payload", sa.JSON),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("state", sa.JSON),
        sa.Column("resume_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
        _user("started_by_user_id"),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("workflow_id", "idempotency_key", name="uq_workflow_executions_idem"),
    )
    op.create_index("ix_workflow_executions_org_wf_created", "workflow_executions",
                    ["organization_id", "workflow_id", "created_at"])
    op.create_index("ix_workflow_executions_org_status_resume", "workflow_executions",
                    ["organization_id", "status", "resume_at"])

    op.create_table(
        "workflow_execution_events",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("execution_id", sa.Uuid, sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("node_key", sa.String(80)),
        sa.Column("node_type", sa.String(40)),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("output", sa.JSON),
        sa.Column("error", sa.Text),
        TS("created_at"),
    )
    op.create_index("ix_wf_exec_events_org_exec", "workflow_execution_events",
                    ["organization_id", "execution_id", "created_at"])

    op.create_table(
        "workflow_approvals",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("execution_id", sa.Uuid, sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("node_key", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text),
        _user("decided_by_user_id"),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("comment", sa.Text),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("execution_id", "node_key", name="uq_workflow_approvals_exec_node"),
    )
    op.create_index("ix_workflow_approvals_org_status", "workflow_approvals", ["organization_id", "status"])

    op.create_table(
        "automation_settings",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("allowed_hosts", sa.JSON),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", name="uq_automation_settings_org"),
    )

    # Not under RLS by design: the public hook endpoint resolves the tenant from it (stores only a secret hash).
    op.create_table(
        "workflow_webhooks",
        sa.Column("workflow_id", sa.Uuid, sa.ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True),
        _org(),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        TS("created_at"),
    )

    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(RLS_TABLES)}, workflow_webhooks TO {ROLE}")
        for t in APPEND_ONLY:
            op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in ("workflow_webhooks", "automation_settings", "workflow_approvals", "workflow_execution_events",
              "workflow_executions", "workflow_nodes", "workflow_versions", "workflows"):
        op.drop_table(t)
