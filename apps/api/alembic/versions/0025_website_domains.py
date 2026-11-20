"""custom domains for published websites (DNS TXT verification, Host-header serving)

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None
ROLE = "leadex_app"


def upgrade() -> None:
    op.add_column("website_projects", sa.Column("domain_verification_token", sa.String(64)))
    op.add_column("website_projects", sa.Column("domain_verified_at", sa.DateTime(timezone=True)))
    # Normalise legacy values (domains were stored unverified before this migration).
    op.execute("UPDATE website_projects SET custom_domain = lower(custom_domain) WHERE custom_domain IS NOT NULL")
    op.execute("UPDATE website_projects SET custom_domain = NULL, domain_verification_status = 'none' "
               "WHERE custom_domain = ''")
    op.create_index("uq_website_projects_custom_domain", "website_projects", ["custom_domain"], unique=True)
    if op.get_bind().dialect.name == "postgresql":
        # Narrow lookup for public routes: RLS hides all rows until a tenant is bound, so resolve the owning
        # organization of a VERIFIED domain through this function only.
        op.execute("""CREATE OR REPLACE FUNCTION website_org_for_verified_domain(p_domain text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
            $$ SELECT organization_id FROM website_projects
               WHERE custom_domain = lower(p_domain) AND domain_verified_at IS NOT NULL LIMIT 1 $$""")
        op.execute("REVOKE ALL ON FUNCTION website_org_for_verified_domain(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION website_org_for_verified_domain(text) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS website_org_for_verified_domain(text)")
    op.drop_index("uq_website_projects_custom_domain", table_name="website_projects")
    op.drop_column("website_projects", "domain_verified_at")
    op.drop_column("website_projects", "domain_verification_token")
