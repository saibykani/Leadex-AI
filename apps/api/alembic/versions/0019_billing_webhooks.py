"""billing webhooks: idempotency ledger + tenant lookup by provider reference

Revision ID: 0019
Revises: 0018

* billing_webhook_events: global (no RLS) ledger of processed provider event ids.
* billing_payment_org(provider, reference): narrow SECURITY DEFINER lookup returning only the organization id of
  the payment with that provider reference, so the public webhook can bind RLS to the right tenant.
"""
import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None
ROLE = "leadex_app"


def upgrade() -> None:
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_webhook_event"),
    )
    op.create_index("ix_payments_provider_ref", "payments", ["provider", "provider_reference"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION billing_payment_org(p_provider text, p_ref text) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
            $$ SELECT organization_id FROM payments WHERE provider = p_provider AND provider_reference = p_ref
               ORDER BY created_at DESC LIMIT 1 $$""")
        op.execute("REVOKE ALL ON FUNCTION billing_payment_org(text, text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION billing_payment_org(text, text) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS billing_payment_org(text, text)")
    op.drop_index("ix_payments_provider_ref", table_name="payments")
    op.drop_table("billing_webhook_events")
