"""voice campaigns: agent + concurrency cap on campaigns; campaign link on calls

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as b:
        b.add_column(sa.Column("voice_agent_id", sa.Uuid, sa.ForeignKey("ai_agents.id", ondelete="SET NULL",
                                                                        name="fk_campaigns_voice_agent")))
        b.add_column(sa.Column("max_concurrent_calls", sa.Integer, nullable=False, server_default="3"))
    with op.batch_alter_table("call_sessions") as b:
        b.add_column(sa.Column("campaign_id", sa.Uuid, sa.ForeignKey("campaigns.id", ondelete="SET NULL",
                                                                     name="fk_call_sessions_campaign")))
    op.create_index("ix_call_sessions_org_campaign", "call_sessions", ["organization_id", "campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_call_sessions_org_campaign", table_name="call_sessions")
    with op.batch_alter_table("call_sessions") as b:
        b.drop_column("campaign_id")
    with op.batch_alter_table("campaigns") as b:
        b.drop_column("max_concurrent_calls")
        b.drop_column("voice_agent_id")
