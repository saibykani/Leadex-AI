"""discovery: businesses, provenance, verifications, website audits, saved searches, search jobs, usage records

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

ROLE = "leadex_app"
ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
TABLES = ("saved_searches", "search_jobs", "businesses", "business_sources", "business_source_fields",
          "business_verifications", "website_audits", "usage_records")
APPEND_ONLY = ("usage_records",)
TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731


def _id():
    return sa.Column("id", sa.Uuid, primary_key=True)


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def _biz():
    return sa.Column("business_id", sa.Uuid, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)


def _fk(name, target):
    return sa.Column(name, sa.Uuid, sa.ForeignKey(target, ondelete="SET NULL"))


def _bool(name, default="false"):
    return sa.Column(name, sa.Boolean, nullable=False, server_default=sa.text(default))


def _int(name):
    return sa.Column(name, sa.Integer, nullable=False, server_default="0")


def upgrade() -> None:
    op.create_table(
        "saved_searches", _id(), _org(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("criteria", sa.JSON, nullable=False),
        sa.Column("schedule", sa.String(120)),
        _fk("created_by_user_id", "users.id"),
        TS("last_run_at", True), TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_saved_searches_org", "saved_searches", ["organization_id"])

    op.create_table(
        "search_jobs", _id(), _org(),
        _fk("saved_search_id", "saved_searches.id"),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("criteria", sa.JSON, nullable=False),
        _int("results_count"), _int("new_count"), _int("duplicate_count"), _int("cost_units"),
        sa.Column("error", sa.Text),
        _bool("is_simulated"),
        _fk("created_by_user_id", "users.id"),
        TS("started_at", True), TS("finished_at", True), TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_search_jobs_org_created", "search_jobs", ["organization_id", "created_at"])

    op.create_table(
        "businesses", _id(), _org(),
        sa.Column("name", sa.String(300)),
        sa.Column("industry", sa.String(120)),
        sa.Column("category", sa.String(120)),
        sa.Column("address", sa.String(500)),
        sa.Column("country", sa.String(2)),
        sa.Column("state", sa.String(120)),
        sa.Column("city", sa.String(120)),
        sa.Column("locality", sa.String(120)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("phone", sa.String(40)),
        sa.Column("phone_normalized", sa.String(40)),
        sa.Column("email", sa.String(320)),
        sa.Column("website", sa.String(500)),
        sa.Column("website_domain", sa.String(255)),
        sa.Column("name_city_key", sa.String(450)),
        sa.Column("google_place_id", sa.String(300)),
        sa.Column("source", sa.String(60), nullable=False),
        _bool("is_simulated"),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="unverified"),
        sa.Column("website_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("contact_permission_status", sa.String(30), nullable=False, server_default="unknown"),
        _fk("lead_id", "leads.id"),
        TS("collected_at"), TS("last_verified_at", True), TS("deleted_at", True),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", "google_place_id", name="uq_businesses_org_place"),
    )
    op.create_index("ix_businesses_org_phone", "businesses", ["organization_id", "phone_normalized"])
    op.create_index("ix_businesses_org_domain", "businesses", ["organization_id", "website_domain"])
    op.create_index("ix_businesses_org_namecity", "businesses", ["organization_id", "name_city_key"])
    op.create_index("ix_businesses_org_wstatus", "businesses", ["organization_id", "website_status"])
    op.create_index("ix_businesses_org_created", "businesses", ["organization_id", "created_at"])

    op.create_table(
        "business_sources", _id(), _org(), _biz(),
        _fk("search_job_id", "search_jobs.id"),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("source_ref", sa.String(300)),
        _bool("is_simulated"),
        TS("collected_at"),
    )
    op.create_index("ix_business_sources_org_biz", "business_sources", ["organization_id", "business_id"])

    op.create_table(
        "business_source_fields", _id(), _org(), _biz(),
        sa.Column("field", sa.String(60), nullable=False),
        sa.Column("value", sa.Text),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("source_ref", sa.String(300)),
        TS("collected_at"), TS("retention_until", True), TS("purged_at", True),
    )
    op.create_index("ix_bsf_org_biz", "business_source_fields", ["organization_id", "business_id"])
    op.create_index("ix_bsf_retention", "business_source_fields", ["retention_until"])

    op.create_table(
        "business_verifications", _id(), _org(), _biz(),
        sa.Column("method", sa.String(60), nullable=False),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("details", sa.JSON),
        _fk("actor_user_id", "users.id"),
        TS("created_at"),
    )
    op.create_index("ix_bver_org_biz", "business_verifications", ["organization_id", "business_id"])

    op.create_table(
        "website_audits", _id(), _org(), _biz(),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("final_url", sa.String(1000)),
        _bool("reachable"),
        sa.Column("http_status", sa.Integer),
        sa.Column("ssl_valid", sa.Boolean),
        sa.Column("mobile_viewport", sa.Boolean),
        sa.Column("load_ms", sa.Integer),
        sa.Column("has_contact_info", sa.Boolean),
        sa.Column("has_cta", sa.Boolean),
        sa.Column("has_title", sa.Boolean),
        sa.Column("has_meta_description", sa.Boolean),
        _int("broken_links_checked"), _int("broken_links_found"),
        sa.Column("score", sa.Integer),
        sa.Column("findings", sa.JSON),
        sa.Column("error", sa.Text),
        _int("attempts"),
        TS("created_at"),
        sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_website_audits_score"),
    )
    op.create_index("ix_waudit_org_biz_created", "website_audits", ["organization_id", "business_id", "created_at"])

    op.create_table(
        "usage_records", _id(), _org(),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(12, 6)),
        sa.Column("campaign_id", sa.Uuid),
        _fk("lead_id", "leads.id"),
        _fk("search_job_id", "search_jobs.id"),
        TS("created_at"),
    )
    op.create_index("ix_usage_org_resource_created", "usage_records", ["organization_id", "resource", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {ROLE}")
        for t in APPEND_ONLY:
            op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in reversed(TABLES):
        op.drop_table(t)
