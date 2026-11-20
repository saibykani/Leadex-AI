"""accounts: password reset / email verification / invitation tokens; users.email_verified_at

Revision ID: 0018
Revises: 0017

account_tokens is a global table (no RLS): it is looked up by token hash before any tenant is known.
Tokens are stored only as SHA-256 hashes.
"""
import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    uuid_t = sa.Uuid
    op.create_table(
        "account_tokens",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("user_id", uuid_t, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("organization_id", uuid_t, sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("role_id", uuid_t, sa.ForeignKey("roles.id", ondelete="CASCADE")),
        sa.Column("created_by_user_id", uuid_t, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_tokens_org_purpose", "account_tokens", ["organization_id", "purpose"])


def downgrade() -> None:
    op.drop_index("ix_account_tokens_org_purpose", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_column("users", "email_verified_at")
