"""compliance + administration: consent, suppression, preferences, jurisdictions, kill switches, DSRs,
integrations (encrypted credentials), notifications, support tickets, super-admin read functions

Revision ID: 0005
Revises: 0004
"""
import json
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from app.modules.compliance.jurisdictions import DEFAULT_PROFILES

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
USR = "NULLIF(current_setting('app.current_user', true), '')::uuid"
IS_SUPER = f"EXISTS (SELECT 1 FROM users u WHERE u.id = {USR} AND u.is_superadmin AND u.is_active)"  # noqa: S608
ROLE = "leadex_app"
TENANT_TABLES = ("consent_records", "suppression_records", "communication_preferences", "data_subject_requests",
                 "integrations", "integration_credentials", "notifications", "support_tickets")
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def _id():
    return sa.Column("id", sa.Uuid, primary_key=True)


def _org(nullable=False):
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=nullable)


def _user(name, ondelete="SET NULL"):
    return sa.Column(name, sa.Uuid, sa.ForeignKey("users.id", ondelete=ondelete))


def _lead(nullable=False, ondelete="CASCADE"):
    return sa.Column("lead_id", sa.Uuid, sa.ForeignKey("leads.id", ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "consent_records", _id(), _org(), _lead(),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("evidence_text", sa.Text),
        sa.Column("evidence_url", sa.String(1000)),
        TS("captured_at"),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_reason", sa.String(500)),
        _user("created_by_user_id"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_consent_org_lead_channel", "consent_records", ["organization_id", "lead_id", "channel"])

    op.create_table(
        "suppression_records", _id(), _org(),
        sa.Column("channel", sa.String(20), nullable=False, server_default="all"),
        sa.Column("email_normalized", sa.String(320)),
        sa.Column("phone_normalized", sa.String(40)),
        sa.Column("reason", sa.String(500), nullable=False),
        _user("created_by_user_id"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_suppression_org_email", "suppression_records", ["organization_id", "email_normalized"])
    op.create_index("ix_suppression_org_phone", "suppression_records", ["organization_id", "phone_normalized"])

    op.create_table(
        "communication_preferences", _id(), _org(), _lead(),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.String(500)),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "lead_id", "channel", name="uq_comm_pref_lead_channel"),
    )

    profiles = op.create_table(
        "jurisdiction_profiles", _id(),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rules", sa.JSON, nullable=False),
        TS("created_at"), TS("updated_at"),
    )
    now = datetime.now(UTC)
    op.bulk_insert(profiles, [
        {"id": uuid.uuid4(), "code": code, "name": p["name"], "rules": json.loads(json.dumps(p["rules"])),
         "created_at": now, "updated_at": now}
        for code, p in DEFAULT_PROFILES.items()
    ])

    op.create_table(
        "kill_switches", _id(), _org(nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="all"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(500), nullable=False),
        _user("set_by_user_id"),
        TS("created_at"), TS("updated_at"),
        sa.CheckConstraint("(scope = 'global' AND organization_id IS NULL) OR "
                           "(scope = 'organization' AND organization_id IS NOT NULL)", name="ck_kill_switch_scope"),
    )
    op.create_index("ix_kill_switch_org_active", "kill_switches", ["organization_id", "active"])

    op.create_table(
        "data_subject_requests", _id(), _org(), _lead(nullable=True, ondelete="SET NULL"),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("subject_email", sa.String(320)),
        sa.Column("subject_phone", sa.String(40)),
        sa.Column("details", sa.Text),
        sa.Column("resolution", sa.Text),
        TS("due_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        _user("created_by_user_id"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_dsr_org_status", "data_subject_requests", ["organization_id", "status"])

    op.create_table(
        "integrations", _id(), _org(),
        sa.Column("provider", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_configured"),
        sa.Column("config", sa.JSON),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "provider", name="uq_integration_org_provider"),
    )
    op.create_table(
        "integration_credentials", _id(), _org(),
        sa.Column("integration_id", sa.Uuid, sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("secret_enc", sa.Text, nullable=False),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("integration_id", "name", name="uq_integration_cred_name"),
    )
    op.create_table(
        "notifications", _id(), _org(), _user("user_id", ondelete="CASCADE"),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_notifications_org_user", "notifications", ["organization_id", "user_id", "read_at"])
    op.create_table(
        "support_tickets", _id(), _org(), _user("created_by_user_id"),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_support_org_status", "support_tickets", ["organization_id", "status"])

    if op.get_bind().dialect.name != "postgresql":
        return

    for t in TENANT_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                   f"WITH CHECK (organization_id = {ORG})")

    # Kill switches: tenant sees its own + global rows; only a super admin may write global rows.
    op.execute("ALTER TABLE kill_switches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE kill_switches FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY ks_read ON kill_switches FOR SELECT "
               f"USING (organization_id IS NULL OR organization_id = {ORG})")
    op.execute(f"CREATE POLICY ks_insert ON kill_switches FOR INSERT "
               f"WITH CHECK (organization_id = {ORG} OR (organization_id IS NULL AND {IS_SUPER}))")
    op.execute(f"CREATE POLICY ks_update ON kill_switches FOR UPDATE "
               f"USING (organization_id = {ORG} OR (organization_id IS NULL AND {IS_SUPER})) "
               f"WITH CHECK (organization_id = {ORG} OR (organization_id IS NULL AND {IS_SUPER}))")
    # No DELETE policy: kill switches are deactivated, never deleted, by the app role.
    op.execute(f"REVOKE DELETE ON kill_switches FROM {ROLE}")

    # Jurisdiction profiles are platform reference data: read-only for the app role.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON jurisdiction_profiles FROM {ROLE}")

    # ---- Super-admin cross-tenant reads. The app role cannot bypass RLS, so these SECURITY DEFINER functions
    # run as the migration (owner) role. Because tables use FORCE RLS, the owner is also subject to policies
    # unless it is a superuser / BYPASSRLS, so we add owner-only read policies. Each function re-checks that
    # the acting user (app.current_user) is an active super admin and returns nothing otherwise.
    owner = op.get_bind().exec_driver_sql("SELECT current_user").scalar()
    for t in ("audit_logs", "leads", "organization_memberships"):
        op.execute(f'CREATE POLICY platform_admin_read ON {t} FOR SELECT TO "{owner}" USING (true)')
    op.execute(f"""
        CREATE OR REPLACE FUNCTION leadex_admin_audit_logs(p_org uuid, p_limit int, p_offset int)
        RETURNS TABLE (id uuid, organization_id uuid, actor_user_id uuid, action varchar, entity_type varchar,
                       entity_id varchar, data json, ip_address varchar, created_at timestamptz, total bigint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
          SELECT a.id, a.organization_id, a.actor_user_id, a.action, a.entity_type, a.entity_id, a.data,
                 a.ip_address, a.created_at, count(*) OVER () AS total
          FROM audit_logs a
          WHERE {IS_SUPER} AND (p_org IS NULL OR a.organization_id = p_org)
          ORDER BY a.created_at DESC
          LIMIT LEAST(GREATEST(p_limit, 1), 200) OFFSET GREATEST(p_offset, 0)
        $$""")  # noqa: S608 (static DDL, no user input)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION leadex_admin_org_usage()
        RETURNS TABLE (organization_id uuid, members bigint, leads bigint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
          SELECT o.id,
                 (SELECT count(*) FROM organization_memberships m WHERE m.organization_id = o.id
                    AND m.status = 'active'),
                 (SELECT count(*) FROM leads l WHERE l.organization_id = o.id AND l.deleted_at IS NULL)
          FROM organizations o
          WHERE {IS_SUPER}
        $$""")  # noqa: S608 (static DDL, no user input)
    for fn in ("leadex_admin_audit_logs(uuid, int, int)", "leadex_admin_org_usage()"):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS leadex_admin_audit_logs(uuid, int, int)")
        op.execute("DROP FUNCTION IF EXISTS leadex_admin_org_usage()")
        for t in ("audit_logs", "leads", "organization_memberships"):
            op.execute(f"DROP POLICY IF EXISTS platform_admin_read ON {t}")
    for t in ("support_tickets", "notifications", "integration_credentials", "integrations",
              "data_subject_requests", "kill_switches", "jurisdiction_profiles", "communication_preferences",
              "suppression_records", "consent_records"):
        op.drop_table(t)  # policies are dropped with their tables
