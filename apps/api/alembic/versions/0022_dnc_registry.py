"""national do-not-call registry imports (per organization, RLS)

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None
ROLE = "leadex_app"
ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
TABLES = ("dnc_registry_imports", "dnc_registry_entries")


def upgrade() -> None:
    op.create_table(
        "dnc_registry_imports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("rows", sa.Integer, nullable=False),
        sa.Column("rejected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("imported_by_user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dnc_imports_org_country", "dnc_registry_imports", ["organization_id", "country"])
    op.create_table(
        "dnc_registry_entries",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("import_id", sa.Uuid, sa.ForeignKey("dnc_registry_imports.id", ondelete="CASCADE"),
                  nullable=False),
    )
    op.create_index("ix_dnc_entries_org_phone", "dnc_registry_entries", ["organization_id", "phone_e164"])
    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {ROLE}")


def downgrade() -> None:
    op.drop_table("dnc_registry_entries")
    op.drop_table("dnc_registry_imports")
