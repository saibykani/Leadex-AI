"""crm: leads, contacts, notes, tasks, activities

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
TABLES = ("leads", "lead_contacts", "lead_notes", "lead_tasks", "lead_activities")
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _lead():
    return sa.Column("lead_id", sa.Uuid, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)


def _user(name):
    return sa.Column(name, sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"))


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid, primary_key=True),
        _org(),
        sa.Column("business_name", sa.String(300), nullable=False),
        sa.Column("industry", sa.String(120)),
        sa.Column("country", sa.String(2)),
        sa.Column("city", sa.String(120)),
        sa.Column("phone", sa.String(40)),
        sa.Column("phone_normalized", sa.String(40)),
        sa.Column("email", sa.String(320)),
        sa.Column("email_normalized", sa.String(320)),
        sa.Column("website", sa.String(500)),
        sa.Column("website_domain", sa.String(255)),
        sa.Column("source", sa.String(60), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(40), nullable=False, server_default="discovered"),
        sa.Column("score", sa.Integer),
        _user("owner_user_id"),
        sa.Column("consent_reference", sa.String(255)),
        sa.Column("custom_fields", sa.JSON),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_leads_org_status", "leads", ["organization_id", "status"])
    op.create_index("ix_leads_org_email", "leads", ["organization_id", "email_normalized"])
    op.create_index("ix_leads_org_phone", "leads", ["organization_id", "phone_normalized"])
    op.create_index("ix_leads_org_domain", "leads", ["organization_id", "website_domain"])
    op.create_index("ix_leads_org_created", "leads", ["organization_id", "created_at"])

    op.create_table(
        "lead_contacts",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _lead(),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(120)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(40)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_lead_contacts_org_lead", "lead_contacts", ["organization_id", "lead_id"])

    op.create_table(
        "lead_notes",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _lead(), _user("author_user_id"),
        sa.Column("body", sa.Text, nullable=False),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_lead_notes_org_lead", "lead_notes", ["organization_id", "lead_id"])

    op.create_table(
        "lead_tasks",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _lead(),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        _user("assignee_user_id"), _user("created_by_user_id"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_lead_tasks_org_lead", "lead_tasks", ["organization_id", "lead_id"])
    op.create_index("ix_lead_tasks_org_due", "lead_tasks", ["organization_id", "completed_at", "due_at"])

    op.create_table(
        "lead_activities",
        sa.Column("id", sa.Uuid, primary_key=True), _org(), _lead(), _user("actor_user_id"),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("data", sa.JSON),
        TS("created_at"),
    )
    op.create_index("ix_lead_activities_org_lead_created", "lead_activities",
                    ["organization_id", "lead_id", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in reversed(TABLES):
        op.drop_table(t)
