"""white label branding per organization

Revision ID: 0024
Revises: 0023
"""
import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None
ROLE = "leadex_app"
ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "organization_branding",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
                  unique=True),
        sa.Column("app_name", sa.String(80)),
        sa.Column("logo_url", sa.String(1000)),
        sa.Column("primary_color", sa.String(7)),
        sa.Column("support_email", sa.String(320)),
        sa.Column("app_domain", sa.String(255), unique=True),
        sa.Column("hide_powered_by", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE organization_branding ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE organization_branding FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON organization_branding USING (organization_id = {ORG}) "
                   f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON organization_branding TO {ROLE}")
        op.execute("""CREATE OR REPLACE FUNCTION branding_org_for_domain(p_domain text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
            $$ SELECT organization_id FROM organization_branding WHERE app_domain = lower(p_domain) LIMIT 1 $$""")
        op.execute("REVOKE ALL ON FUNCTION branding_org_for_domain(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION branding_org_for_domain(text) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS branding_org_for_domain(text)")
    op.drop_table("organization_branding")
