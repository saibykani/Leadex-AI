"""PostgreSQL row-level security for tenant tables

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
USR = "NULLIF(current_setting('app.current_user', true), '')::uuid"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for t in ("organization_memberships", "audit_logs", "idempotency_keys"):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    # Memberships: visible within the bound tenant, or the acting user's own memberships.
    op.execute(
        f"CREATE POLICY tenant_isolation ON organization_memberships "
        f"USING (organization_id = {ORG} OR user_id = {USR}) "
        f"WITH CHECK (organization_id = {ORG})"
    )
    # Audit: read only own tenant; platform-level events (NULL org) may be written but not read via app.
    op.execute(f"CREATE POLICY audit_read ON audit_logs FOR SELECT USING (organization_id = {ORG})")
    op.execute(
        f"CREATE POLICY audit_insert ON audit_logs FOR INSERT "
        f"WITH CHECK (organization_id IS NULL OR organization_id = {ORG})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation ON idempotency_keys "
        f"USING (organization_id = {ORG}) WITH CHECK (organization_id = {ORG})"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_memberships")
    op.execute("DROP POLICY IF EXISTS audit_read ON audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_insert ON audit_logs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON idempotency_keys")
    for t in ("organization_memberships", "audit_logs", "idempotency_keys"):
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
