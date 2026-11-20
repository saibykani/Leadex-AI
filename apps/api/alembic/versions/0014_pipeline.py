"""pipeline: business images, conversation outcomes, pipeline runs, pipeline settings

Revision ID: 0014
Revises: 0013
"""
import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"
RLS_TABLES = ("business_images", "conversation_outcomes", "pipeline_runs", "pipeline_settings")
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _fk(name, table, nullable=True):
    return sa.Column(name, sa.Uuid, sa.ForeignKey(f"{table}.id", ondelete="CASCADE" if not nullable else "SET NULL"),
                     nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "business_images",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        _fk("business_id", "businesses", nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("permission_confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
        _fk("permission_confirmed_by", "users"),
        sa.Column("permission_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column("origin_url", sa.String(1000)),
        sa.Column("filename", sa.String(255)),
        sa.Column("alt", sa.String(300)),
        sa.Column("public_token", sa.String(64), nullable=False),
        _fk("uploaded_by", "users"),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("public_token", name="uq_business_images_token"),
    )
    op.create_index("ix_business_images_org_biz", "business_images", ["organization_id", "business_id"])
    op.create_table(
        "conversation_outcomes",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        _fk("lead_id", "leads"), _fk("agent_id", "ai_agents"), _fk("call_id", "call_sessions"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("extraction_mode", sa.String(10), nullable=False),
        sa.Column("model", sa.String(120)),
        sa.Column("interest", sa.String(10), nullable=False),
        sa.Column("budget_min", sa.Numeric(14, 2)), sa.Column("budget_max", sa.Numeric(14, 2)),
        sa.Column("budget_currency", sa.String(3)), sa.Column("budget_evidence", sa.Text),
        sa.Column("timeline", sa.String(200)), sa.Column("timeline_evidence", sa.Text),
        sa.Column("decision_maker", sa.String(200)), sa.Column("decision_maker_evidence", sa.Text),
        sa.Column("objections", sa.JSON), sa.Column("next_step", sa.String(300)),
        sa.Column("summary", sa.Text, nullable=False), sa.Column("transcript", sa.JSON),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        _fk("created_by", "users"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_conv_outcomes_org_lead", "conversation_outcomes", ["organization_id", "lead_id"])
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        _fk("business_id", "businesses", nullable=False),
        _fk("lead_id", "leads"), _fk("website_project_id", "website_projects"), _fk("agent_id", "ai_agents"),
        _fk("call_id", "call_sessions"),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("steps", sa.JSON, nullable=False),
        _fk("created_by", "users"),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "business_id", name="uq_pipeline_runs_org_biz"),
    )
    op.create_table(
        "pipeline_settings",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("packages", sa.JSON, nullable=False),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", name="uq_pipeline_settings_org"),
    )
    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(RLS_TABLES)} TO {ROLE}")
        # Public media route (generated websites) must resolve the tenant before RLS can be bound. Reveals only an
        # organization id for an exact unguessable token of an APPROVED, permission-confirmed image.
        op.execute("""CREATE OR REPLACE FUNCTION business_image_org_by_token(t text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
            $$ SELECT organization_id FROM business_images
               WHERE public_token = t AND status = 'approved' AND permission_confirmed $$""")
        op.execute("REVOKE ALL ON FUNCTION business_image_org_by_token(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION business_image_org_by_token(text) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS business_image_org_by_token(text)")
        for t in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in ("pipeline_settings", "pipeline_runs", "conversation_outcomes", "business_images"):
        op.drop_table(t)
