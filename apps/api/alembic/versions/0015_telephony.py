"""telephony: Twilio call fields on call_sessions + tenant resolver for public telephony webhooks

Revision ID: 0015
Revises: 0014
"""
import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

ROLE = "leadex_app"


def upgrade() -> None:
    op.add_column("call_sessions", sa.Column("provider_call_id", sa.String(64), nullable=True))
    op.add_column("call_sessions", sa.Column("to_number", sa.String(20), nullable=True))
    op.add_column("call_sessions", sa.Column("error_message", sa.Text, nullable=True))
    op.add_column("call_sessions", sa.Column("price", sa.Numeric(12, 4), nullable=True))
    op.add_column("call_sessions", sa.Column("price_unit", sa.String(8), nullable=True))
    op.add_column("call_sessions", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        # Public Twilio webhooks carry only the (unguessable, random UUID) call session id. RLS hides every row until
        # a tenant is bound, so this narrow resolver reveals ONLY the owning organization id of a session that was
        # actually dialled through Twilio. Signature validation (per-org auth token) happens afterwards in the app.
        op.execute("""CREATE OR REPLACE FUNCTION telephony_call_org(cid uuid) RETURNS uuid
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
            $$ SELECT organization_id FROM call_sessions WHERE id = cid AND provider = 'twilio' $$""")
        op.execute("REVOKE ALL ON FUNCTION telephony_call_org(uuid) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION telephony_call_org(uuid) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS telephony_call_org(uuid)")
    for c in ("finalized_at", "price_unit", "price", "error_message", "to_number", "provider_call_id"):
        op.drop_column("call_sessions", c)
