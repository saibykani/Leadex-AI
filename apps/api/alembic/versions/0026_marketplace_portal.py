"""marketplace portal: external provider/customer accounts and magic-link tokens

Revision ID: 0026
Revises: 0025

Both tables are global (no RLS), like account_tokens: they are looked up by email / token hash before any
tenant is known and hold only ids and the login email. Tokens are stored only as SHA-256 hashes. Every
portal data query afterwards runs with app.current_org bound from the signed portal session, so the
tenant tables keep their normal row-level security.
"""
import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_accounts",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Uuid, nullable=False),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "role", "subject_id", name="uq_portal_account_subject"),
    )
    op.create_table(
        "portal_tokens",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("portal_accounts.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Runtime role gets DML via 0004's default privileges (same as account_tokens); no RLS by design.


def downgrade() -> None:
    op.drop_table("portal_tokens")
    op.drop_table("portal_accounts")
