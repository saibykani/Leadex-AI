"""websites: templates, projects, immutable versions, deployments, preview feedback

Revision ID: 0008
Revises: 0007
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
TENANT_TABLES = ("website_projects", "website_versions", "website_deployments", "website_feedback")
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731

# Frozen copy of the template catalogue at the time of this migration.
from app.modules.websites.templates import TEMPLATES  # noqa: E402


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _project():
    return sa.Column("project_id", sa.Uuid, sa.ForeignKey("website_projects.id", ondelete="CASCADE"),
                     nullable=False)


def _user(name):
    return sa.Column(name, sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"))


def upgrade() -> None:
    templates = op.create_table(
        "website_templates",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("key", sa.String(60), nullable=False, unique=True),
        sa.Column("industry", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sections", sa.JSON, nullable=False),
        sa.Column("theme", sa.JSON, nullable=False),
        TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "website_projects",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("business_id", sa.Uuid),
        sa.Column("lead_id", sa.Uuid, sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("template_key", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("preview_token", sa.String(64), nullable=False, unique=True),
        sa.Column("current_version_id", sa.Uuid),
        sa.Column("approved_version_id", sa.Uuid),
        sa.Column("published_version_id", sa.Uuid),
        sa.Column("custom_domain", sa.String(255)),
        sa.Column("domain_verification_status", sa.String(20), nullable=False, server_default="none"),
        _user("created_by"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_website_projects_org_created", "website_projects", ["organization_id", "created_at"])
    op.create_table(
        "website_versions",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _project(),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("content", sa.JSON, nullable=False),
        sa.Column("rendered_html", sa.Text, nullable=False),
        _user("created_by"),
        sa.Column("note", sa.String(300)),
        sa.Column("generation_mode", sa.String(20), nullable=False, server_default="template"),
        TS("created_at"),
        sa.UniqueConstraint("project_id", "number", name="uq_website_versions_project_number"),
    )
    op.create_index("ix_website_versions_org_project", "website_versions", ["organization_id", "project_id", "number"])
    op.create_table(
        "website_deployments",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _project(),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("website_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="live"),
        sa.Column("target", sa.String(20), nullable=False, server_default="local"),
        sa.Column("url", sa.String(500), nullable=False),
        TS("deployed_at"),
        _user("deployed_by"),
        sa.Column("rolled_back_from", sa.Uuid),
    )
    op.create_index("ix_website_deployments_org_project", "website_deployments", ["organization_id", "project_id"])
    op.create_table(
        "website_feedback",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _project(),
        sa.Column("version_id", sa.Uuid),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False, server_default=sa.false()),
        TS("created_at"),
    )
    op.create_index("ix_website_feedback_org_project", "website_feedback", ["organization_id", "project_id"])

    now = datetime.now(UTC)
    op.bulk_insert(templates, [{"id": uuid.uuid4(), **t, "created_at": now, "updated_at": now} for t in TEMPLATES])

    if op.get_bind().dialect.name == "postgresql":
        for t in TENANT_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        # Versions are immutable.
        op.execute("REVOKE UPDATE ON website_versions FROM leadex_app")
        # Public preview / site routes must find the owning tenant before RLS can be bound. These definer
        # functions reveal only an organization id for an exact unguessable token / published project id.
        op.execute("""CREATE OR REPLACE FUNCTION website_org_by_preview_token(t text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
            $$ SELECT organization_id FROM website_projects WHERE preview_token = t $$""")
        op.execute("""CREATE OR REPLACE FUNCTION website_org_by_published_project(p text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
            $$ SELECT organization_id FROM website_projects
               WHERE id = p::uuid AND published_version_id IS NOT NULL $$""")
        for fn in ("website_org_by_preview_token(text)", "website_org_by_published_project(text)"):
            op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
            op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO leadex_app")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS website_org_by_preview_token(text)")
        op.execute("DROP FUNCTION IF EXISTS website_org_by_published_project(text)")
        for t in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in ("website_feedback", "website_deployments", "website_versions", "website_projects",
              "website_templates"):
        op.drop_table(t)
