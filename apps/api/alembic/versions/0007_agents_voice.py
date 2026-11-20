"""agents + voice: model configs, AI agents, versions, tool catalog, knowledge/RAG, evaluations, runs/logs,
call sessions and call artefacts

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"
TENANT_TABLES = (
    "model_configurations", "ai_agents", "agent_versions", "agent_knowledge", "knowledge_chunks",
    "agent_evaluations", "agent_runs", "agent_logs", "call_sessions", "call_events", "call_transcripts",
    "call_summaries", "call_dispositions", "call_recordings",
)
APPEND_ONLY = ("agent_versions", "agent_evaluations", "agent_runs", "agent_logs", "call_events", "call_transcripts")
ALL_TABLES = TENANT_TABLES[:2] + ("agent_tools",) + TENANT_TABLES[2:]

TOOLS = [  # mirrors app.modules.agents.tools.TOOLS (code is the source of truth)
    ("crm_lookup", "CRM lookup", "Read a lead's name, status, industry and city.", False, False, "leads:read"),
    ("create_note", "Create note", "Add a note to a lead's CRM record.", True, False, "leads:write"),
    ("book_callback", "Book callback task", "Create a callback task on a lead.", True, False, "leads:write"),
    ("schedule_outbound_call", "Schedule outbound call",
     "Request a follow-up call to the lead. Routed through the compliance gate; never dials directly.",
     True, True, "calls:initiate"),
]


def TS(name):  # noqa: N802
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False)


def _id():
    return sa.Column("id", sa.Uuid, primary_key=True)


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _fk(name, table, nullable=False, ondelete="CASCADE"):
    return sa.Column(name, sa.Uuid, sa.ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable)


def _user(name):
    return _fk(name, "users", nullable=True, ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "model_configurations", _id(), _org(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("temperature", sa.Float, nullable=False),
        sa.Column("max_tokens", sa.Integer, nullable=False),
        sa.Column("base_url", sa.String(500)),
        TS("created_at"), TS("updated_at"),
        sa.CheckConstraint("provider IN ('ollama','simulated')", name="ck_model_configurations_provider"),
    )
    op.create_index("ix_model_configurations_org", "model_configurations", ["organization_id"])

    op.create_table(
        "ai_agents", _id(), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("purpose", sa.Text), sa.Column("industry", sa.String(120)), sa.Column("personality", sa.Text),
        sa.Column("voice", sa.String(80)),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("speaking_rate", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("greeting", sa.Text), sa.Column("business_info", sa.Text),
        sa.Column("qualification_questions", sa.JSON), sa.Column("conversation_flow", sa.JSON),
        sa.Column("objection_handling", sa.JSON), sa.Column("tools", sa.JSON),
        sa.Column("escalation_policy", sa.Text),
        sa.Column("max_call_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("business_hours", sa.JSON),
        sa.Column("compliance_disclosure", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("template_key", sa.String(60)),
        _fk("model_config_id", "model_configurations", nullable=True, ondelete="SET NULL"),
        sa.Column("published_version", sa.Integer),
        _user("created_by_user_id"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
        sa.CheckConstraint("length(compliance_disclosure) >= 10", name="ck_ai_agents_disclosure"),
    )
    op.create_index("ix_ai_agents_org_status", "ai_agents", ["organization_id", "status"])

    tools = op.create_table(
        "agent_tools", _id(),
        sa.Column("key", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("side_effect", sa.Boolean, nullable=False),
        sa.Column("contacts_person", sa.Boolean, nullable=False),
        sa.Column("required_permission", sa.String(100), nullable=False),
    )
    import uuid

    op.bulk_insert(tools, [{"id": uuid.uuid5(uuid.NAMESPACE_URL, f"leadex:tool:{k}"), "key": k, "name": n,
                            "description": d, "side_effect": se, "contacts_person": cp, "required_permission": p}
                           for k, n, d, se, cp, p in TOOLS])

    op.create_table(
        "agent_versions", _id(), _org(), _fk("agent_id", "ai_agents"),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        _user("published_by_user_id"), TS("created_at"),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index("ix_agent_versions_org_agent", "agent_versions", ["organization_id", "agent_id"])

    op.create_table(
        "agent_knowledge", _id(), _org(), _fk("agent_id", "ai_agents"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("embedding_status", sa.String(20), nullable=False),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_agent_knowledge_org_agent", "agent_knowledge", ["organization_id", "agent_id"])

    op.create_table(
        "knowledge_chunks", _id(), _org(), _fk("agent_id", "ai_agents"), _fk("knowledge_id", "agent_knowledge"),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding_status", sa.String(20), nullable=False),
        sa.Column("embedding_model", sa.String(120)),
        TS("created_at"),
    )
    op.create_index("ix_knowledge_chunks_org_agent", "knowledge_chunks", ["organization_id", "agent_id"])

    op.create_table(
        "agent_evaluations", _id(), _org(), _fk("agent_id", "ai_agents"),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("language", sa.String(10)),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float), sa.Column("notes", sa.Text),
        _user("evaluated_by_user_id"), TS("created_at"),
    )
    op.create_index("ix_agent_evaluations_org_agent", "agent_evaluations", ["organization_id", "agent_id"])

    op.create_table(
        "agent_runs", _id(), _org(), _fk("agent_id", "ai_agents"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("input", sa.JSON), sa.Column("output", sa.Text),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("tool_calls", sa.JSON), sa.Column("citations", sa.JSON),
        sa.Column("retrieval_mode", sa.String(20)),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120)), sa.Column("error", sa.Text),
        sa.Column("simulated", sa.Boolean, nullable=False),
        _user("actor_user_id"), TS("created_at"),
    )
    op.create_index("ix_agent_runs_org_agent_created", "agent_runs", ["organization_id", "agent_id", "created_at"])

    op.create_table(
        "agent_logs", _id(), _org(), _fk("run_id", "agent_runs"),
        sa.Column("step", sa.String(40), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("data", sa.JSON),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        TS("created_at"),
    )
    op.create_index("ix_agent_logs_org_run", "agent_logs", ["organization_id", "run_id"])

    op.create_table(
        "call_sessions", _id(), _org(), _fk("lead_id", "leads"), _fk("agent_id", "ai_agents"),
        sa.Column("agent_version", sa.Integer),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("gate_reasons", sa.JSON),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_s", sa.Integer),
        sa.Column("idempotency_key", sa.String(128)),
        _user("initiated_by_user_id"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_call_sessions_org_created", "call_sessions", ["organization_id", "created_at"])
    op.create_index("ix_call_sessions_org_lead", "call_sessions", ["organization_id", "lead_id"])

    op.create_table(
        "call_events", _id(), _org(), _fk("call_id", "call_sessions"),
        sa.Column("type", sa.String(60), nullable=False), sa.Column("data", sa.JSON), TS("created_at"),
    )
    op.create_table(
        "call_transcripts", _id(), _org(), _fk("call_id", "call_sessions"),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("speaker", sa.String(20), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False), TS("created_at"),
    )
    op.create_table(
        "call_summaries", _id(), _org(), _fk("call_id", "call_sessions"),
        sa.Column("summary", sa.Text, nullable=False), sa.Column("simulated", sa.Boolean, nullable=False),
        TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "call_dispositions", _id(), _org(), _fk("call_id", "call_sessions"),
        sa.Column("disposition", sa.String(40), nullable=False), sa.Column("notes", sa.Text),
        _user("set_by_user_id"), TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "call_recordings", _id(), _org(), _fk("call_id", "call_sessions"),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("consent_reference", sa.String(255)),
        sa.Column("storage_key", sa.String(500)),
        sa.Column("duration_s", sa.Integer),
        TS("created_at"), TS("updated_at"),
        sa.CheckConstraint("enabled = false OR consent_reference IS NOT NULL", name="ck_call_recordings_consent"),
    )
    for t in ("call_events", "call_transcripts", "call_summaries", "call_dispositions", "call_recordings"):
        op.create_index(f"ix_{t}_org_call", t, ["organization_id", "call_id"])

    if op.get_bind().dialect.name == "postgresql":
        for t in TENANT_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        # Global catalog: readable by the app, never writable at runtime.
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON agent_tools FROM {ROLE}")
        op.execute(f"GRANT SELECT ON agent_tools TO {ROLE}")
        for t in APPEND_ONLY:
            op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in reversed(ALL_TABLES):
        op.drop_table(t)
