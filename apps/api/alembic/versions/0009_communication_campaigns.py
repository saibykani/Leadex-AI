"""communication (email, whatsapp, suppressions) and campaigns

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

ROLE = "leadex_app"
ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
# communication_routes is intentionally NOT tenant-scoped (public id -> org lookup for webhooks; no content).
RLS_TABLES = (
    "whatsapp_templates", "campaigns", "email_accounts", "email_templates", "email_campaigns", "email_messages",
    "unsubscribe_tokens", "communication_suppressions", "whatsapp_accounts", "whatsapp_conversations",
    "whatsapp_messages", "campaign_recipients", "campaign_approvals", "campaign_events",
)
APPEND_ONLY = ("campaign_events", "campaign_approvals")
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def _id():
    return sa.Column("id", sa.Uuid, primary_key=True)


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _fk(name, table, nullable=True, ondelete="SET NULL"):
    return sa.Column(name, sa.Uuid, sa.ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "communication_routes", _id(),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(320), nullable=False), _org(), TS("created_at"),
        sa.UniqueConstraint("kind", "external_id", name="uq_comm_route_kind_ext"),
    )
    op.create_table(
        "whatsapp_templates", _id(), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "name", "language", name="uq_wa_template"),
    )
    op.create_table(
        "campaigns", _id(), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("spend_limit", sa.Numeric(12, 2)),
        sa.Column("cost_per_message", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("spent", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("send_window", sa.JSON),
        _fk("whatsapp_template_id", "whatsapp_templates"),
        _fk("created_by_user_id", "users"), _fk("approved_by_user_id", "users"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_campaigns_org_status", "campaigns", ["organization_id", "status"])
    op.create_table(
        "email_accounts", _id(), _org(),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("address", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_configured"),
        sa.Column("credentials_enc", sa.Text),
        sa.Column("credentials_encrypted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        _fk("created_by_user_id", "users"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_email_accounts_org", "email_accounts", ["organization_id"])
    op.create_table(
        "email_templates", _id(), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("html", sa.Text, nullable=False),
        sa.Column("text", sa.Text),
        sa.Column("variables", sa.JSON),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_email_templates_org", "email_templates", ["organization_id"])
    op.create_table(
        "email_campaigns", _id(), _org(),
        _fk("campaign_id", "campaigns", nullable=False, ondelete="CASCADE"),
        _fk("account_id", "email_accounts"),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("physical_address", sa.String(500)),
        sa.Column("website_preview_base_url", sa.String(500)),
        sa.Column("personalize_with_ai", sa.Boolean, nullable=False, server_default=sa.false()),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("campaign_id", name="uq_email_campaign_campaign"),
    )
    op.create_table(
        "email_messages", _id(), _org(),
        _fk("campaign_id", "campaigns"), _fk("lead_id", "leads"), _fk("account_id", "email_accounts"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("step_index", sa.Integer),
        sa.Column("from_address", sa.String(320)),
        sa.Column("to_address", sa.String(320)),
        sa.Column("subject", sa.String(300)),
        sa.Column("html", sa.Text),
        sa.Column("text", sa.Text),
        sa.Column("gate_reasons", sa.JSON),
        sa.Column("provider_message_id", sa.String(255)),
        _fk("in_reply_to_id", "email_messages"),
        sa.Column("error", sa.String(500)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_email_messages_org_created", "email_messages", ["organization_id", "created_at"])
    op.create_index("ix_email_messages_org_campaign", "email_messages", ["organization_id", "campaign_id"])
    op.create_index("ix_email_messages_provider_id", "email_messages", ["provider_message_id"])
    op.create_table(
        "unsubscribe_tokens", _id(), _org(),
        sa.Column("token_hash", sa.String(64), nullable=False),
        _fk("lead_id", "leads"),
        sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
        sa.Column("address", sa.String(320), nullable=False),
        _fk("campaign_id", "campaigns"),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        TS("created_at"),
        sa.UniqueConstraint("token_hash", name="uq_unsub_token_hash"),
    )
    op.create_table(
        "communication_suppressions", _id(), _org(),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("source", sa.String(200)),
        TS("created_at"),
        sa.UniqueConstraint("organization_id", "channel", "value", name="uq_comm_suppr"),
    )
    op.create_table(
        "whatsapp_accounts", _id(), _org(),
        sa.Column("phone_number_id", sa.String(64), nullable=False),
        sa.Column("display_phone", sa.String(40)),
        sa.Column("business_account_id", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_configured"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_whatsapp_accounts_org", "whatsapp_accounts", ["organization_id"])
    op.create_table(
        "whatsapp_conversations", _id(), _org(),
        _fk("account_id", "whatsapp_accounts"),
        sa.Column("contact_phone", sa.String(40), nullable=False),
        sa.Column("contact_name", sa.String(200)),
        _fk("lead_id", "leads"),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("handoff_to_human", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("opted_out", sa.Boolean, nullable=False, server_default=sa.false()),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "contact_phone", name="uq_wa_conv_contact"),
    )
    op.create_table(
        "whatsapp_messages", _id(), _org(),
        _fk("conversation_id", "whatsapp_conversations", nullable=False, ondelete="CASCADE"),
        _fk("campaign_id", "campaigns"), _fk("lead_id", "leads"), _fk("template_id", "whatsapp_templates"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("gate_reasons", sa.JSON),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("error", sa.String(500)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_wa_messages_org_conv", "whatsapp_messages", ["organization_id", "conversation_id",
                                                                     "created_at"])
    op.create_index("ix_wa_messages_provider_id", "whatsapp_messages", ["provider_message_id"])
    op.create_table(
        "campaign_recipients", _id(), _org(),
        _fk("campaign_id", "campaigns", nullable=False, ondelete="CASCADE"),
        _fk("lead_id", "leads", nullable=False, ondelete="CASCADE"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("gate_allowed", sa.Boolean),
        sa.Column("gate_simulated", sa.Boolean),
        sa.Column("gate_reasons", sa.JSON),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_recipient"),
    )
    op.create_index("ix_campaign_recipients_org_due", "campaign_recipients",
                    ["organization_id", "campaign_id", "next_due_at"])
    op.create_table(
        "campaign_approvals", _id(), _org(),
        _fk("campaign_id", "campaigns", nullable=False, ondelete="CASCADE"),
        _fk("approver_user_id", "users"),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text),
        TS("created_at"),
    )
    op.create_index("ix_campaign_approvals_org_campaign", "campaign_approvals", ["organization_id", "campaign_id"])
    op.create_table(
        "campaign_events", _id(), _org(),
        _fk("campaign_id", "campaigns", nullable=False, ondelete="CASCADE"),
        _fk("actor_user_id", "users"),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("data", sa.JSON),
        TS("created_at"),
    )
    op.create_index("ix_campaign_events_org_campaign_created", "campaign_events",
                    ["organization_id", "campaign_id", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        for t in APPEND_ONLY:
            op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")
        # Routes: the app role may read/insert mappings but never rewrite or delete another tenant's route.
        op.execute(f"REVOKE UPDATE, DELETE ON communication_routes FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in ("campaign_events", "campaign_approvals", "campaign_recipients", "whatsapp_messages",
              "whatsapp_conversations", "whatsapp_accounts", "communication_suppressions", "unsubscribe_tokens",
              "email_messages", "email_campaigns", "email_templates", "email_accounts", "campaigns",
              "whatsapp_templates", "communication_routes"):
        op.drop_table(t)
