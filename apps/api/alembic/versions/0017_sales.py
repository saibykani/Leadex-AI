"""sales: plan display settings, inbound inquiries, demo booking

Revision ID: 0017
Revises: 0016

* plan_display / sales_settings / sales_booked_slots: global platform tables (no PII, no RLS).
* sales_inquiries: RLS tenant table, rows live in the platform-owner organization.
* sales_inquiries_inbox: no RLS; used only when no platform-owner org exists. The app role may INSERT only;
  reads go through superadmin tooling.
* sales_platform_owner_org(): narrow SECURITY DEFINER lookup so public routes can bind RLS to the owner org.
"""
import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"


def _ts():
    return (sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def _inquiry_cols():
    return [
        sa.Column("reference", sa.String(20), nullable=False, unique=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("role", sa.String(120)),
        sa.Column("team_size", sa.String(20)),
        sa.Column("country", sa.String(2)),
        sa.Column("phone", sa.String(40)),
        sa.Column("interests", sa.JSON),
        sa.Column("message", sa.Text),
        sa.Column("preferred_time", sa.String(120)),
        sa.Column("timezone", sa.String(64)),
        sa.Column("marketing_consent", sa.Boolean, nullable=False),
        sa.Column("privacy_ack_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_start", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(64)),
    ]


def upgrade() -> None:
    op.create_table(
        "plan_display",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("plan_code", sa.String(40), nullable=False, unique=True),
        sa.Column("price_monthly", sa.Numeric(14, 2)),
        sa.Column("price_annual", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("contact_sales", sa.Boolean, nullable=False),
        sa.Column("highlight", sa.Boolean, nullable=False),
        sa.Column("badge", sa.String(40)),
        sa.Column("tagline", sa.String(200)),
        sa.Column("bullets", sa.JSON),
        *_ts(),
    )
    op.create_table(
        "sales_settings",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("key", sa.String(20), nullable=False, unique=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("weekdays", sa.JSON, nullable=False),
        sa.Column("day_start", sa.String(5), nullable=False),
        sa.Column("day_end", sa.String(5), nullable=False),
        sa.Column("slot_minutes", sa.Integer, nullable=False),
        sa.Column("buffer_minutes", sa.Integer, nullable=False),
        sa.Column("min_notice_hours", sa.Integer, nullable=False),
        sa.Column("horizon_days", sa.Integer, nullable=False),
        sa.Column("booking_enabled", sa.Boolean, nullable=False),
        *_ts(),
    )
    op.create_table(
        "sales_booked_slots",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(20), nullable=False),
        sa.Column("ics_token", sa.String(64), nullable=False, unique=True),
        sa.Column("cancelled", sa.Boolean, nullable=False),
        *_ts(),
    )
    op.create_table(
        "sales_inquiries",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.Uuid, sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("assignee_user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_inquiry_cols(),
        *_ts(),
    )
    op.create_index("ix_sales_inquiries_org_email_type", "sales_inquiries",
                    ["organization_id", "email", "type", "created_at"])
    op.create_index("ix_sales_inquiries_org_status", "sales_inquiries", ["organization_id", "status"])
    op.create_table("sales_inquiries_inbox", sa.Column("id", sa.Uuid, primary_key=True), *_inquiry_cols(), *_ts())
    op.create_index("ix_sales_inbox_email_type", "sales_inquiries_inbox", ["email", "type", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE sales_inquiries ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE sales_inquiries FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON sales_inquiries USING (organization_id = {ORG}) "
                   f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON sales_inquiries, plan_display, sales_settings, "
                   f"sales_booked_slots TO {ROLE}")
        # Fallback inbox: insert + dedupe/count reads only (holds PII from unrouted inquiries).
        op.execute(f"GRANT SELECT, INSERT ON sales_inquiries_inbox TO {ROLE}")
        op.execute("""CREATE OR REPLACE FUNCTION sales_platform_owner_org() RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
            $$ SELECT id FROM organizations WHERE is_platform_owner AND deleted_at IS NULL
               ORDER BY created_at LIMIT 1 $$""")
        op.execute("REVOKE ALL ON FUNCTION sales_platform_owner_org() FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION sales_platform_owner_org() TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS sales_platform_owner_org()")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON sales_inquiries")
    op.drop_table("sales_inquiries_inbox")
    op.drop_table("sales_inquiries")
    op.drop_table("sales_booked_slots")
    op.drop_table("sales_settings")
    op.drop_table("plan_display")
