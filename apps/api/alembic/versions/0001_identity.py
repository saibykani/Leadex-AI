"""identity, organizations, rbac, sessions, audit, idempotency

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("country_code", sa.String(2)),
        sa.Column("is_platform_owner", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("mfa_secret_enc", sa.String(512)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "name", name="uq_roles_org_name"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Uuid, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(400)),
        sa.Column("ip_address", sa.String(64)),
        TS("created_at"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id")),
        sa.Column("actor_user_id", sa.Uuid, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(60)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("data", sa.JSON),
        sa.Column("ip_address", sa.String(64)),
        TS("created_at"),
    )
    op.create_index("ix_audit_org_created", "audit_logs", ["organization_id", "created_at"])
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON),
        TS("created_at"),
        sa.UniqueConstraint("organization_id", "key", name="uq_idem_org_key"),
    )

    from app.modules.identity.rbac import seed_rbac

    seed_rbac(Session(bind=op.get_bind()))


def downgrade() -> None:
    for t in ["idempotency_keys", "audit_logs", "sessions", "organization_memberships", "role_permissions",
              "roles", "permissions", "users", "organizations"]:
        op.drop_table(t)
