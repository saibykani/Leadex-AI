"""learning: opening variants (Thompson sampling) and per-call rewards

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None
ROLE = "leadex_app"
ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
TABLES = ("agent_script_variants", "call_learning")


def upgrade() -> None:
    op.create_table(
        "agent_script_variants",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("opening", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_script_variants_org_agent", "agent_script_variants", ["organization_id", "agent_id"])
    op.create_table(
        "call_learning",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.Uuid, sa.ForeignKey("call_sessions.id", ondelete="CASCADE"), nullable=False,
                  unique=True),
        sa.Column("variant_id", sa.Uuid, sa.ForeignKey("agent_script_variants.id", ondelete="SET NULL")),
        sa.Column("reward", sa.Integer),
        sa.Column("reward_source", sa.String(10)),
        sa.Column("label", sa.String(40)),
        sa.Column("feedback_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_call_learning_org_agent", "call_learning", ["organization_id", "agent_id"])
    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {ROLE}")


def downgrade() -> None:
    op.drop_table("call_learning")
    op.drop_table("agent_script_variants")
