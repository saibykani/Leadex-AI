"""growth: onboarding progress + investor demo workspaces

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
USR = "NULLIF(current_setting('app.current_user', true), '')::uuid"
ROLE = "leadex_app"


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _ts():
    return (sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def upgrade() -> None:
    op.create_table(
        "onboarding_progress",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("profile", sa.JSON),
        *_ts(),
        sa.UniqueConstraint("organization_id", name="uq_onboarding_progress_org"),
    )
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("owner_user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.JSON),
        *_ts(),
        sa.UniqueConstraint("organization_id", name="uq_demo_workspaces_org"),
    )
    op.create_index("ix_demo_workspaces_owner_user_id", "demo_workspaces", ["owner_user_id"])
    if op.get_bind().dialect.name == "postgresql":
        for t in ("onboarding_progress", "demo_workspaces"):
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON onboarding_progress USING (organization_id = {ORG}) "
                   f"WITH CHECK (organization_id = {ORG})")
        # Visible from inside the demo org, or to its owner from any org (to find / reset it).
        op.execute(f"CREATE POLICY demo_access ON demo_workspaces "
                   f"USING (organization_id = {ORG} OR owner_user_id = {USR}) "
                   f"WITH CHECK (organization_id = {ORG} AND owner_user_id = {USR})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON onboarding_progress, demo_workspaces TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON onboarding_progress")
        op.execute("DROP POLICY IF EXISTS demo_access ON demo_workspaces")
    op.drop_table("demo_workspaces")
    op.drop_table("onboarding_progress")
