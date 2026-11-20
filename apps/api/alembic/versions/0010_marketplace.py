"""marketplace: requirements, providers, matching, referrals, commission ledger

Default service categories are seeded per tenant lazily by the application (tables are tenant-scoped
under RLS, so there are no global rows). referral_events and commission_transactions are append-only.

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"
APPEND_ONLY = ("referral_events", "commission_transactions")
TABLES = (
    "service_categories", "marketplace_matching_settings", "customers", "customer_requirements",
    "service_providers", "provider_categories", "provider_documents", "provider_verifications",
    "provider_matches", "referrals", "referral_events", "commission_agreements", "commission_transactions",
    "commission_disputes",
)
MONEY = sa.Numeric(14, 2)


def _id():
    return sa.Column("id", sa.Uuid, primary_key=True)


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _fk(name, target, ondelete="CASCADE", nullable=False):
    return sa.Column(name, sa.Uuid, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def _user(name):
    return _fk(name, "users.id", "SET NULL", True)


def _ts(*names):
    return [sa.Column(n, sa.DateTime(timezone=True), nullable=False) for n in names]


def upgrade() -> None:
    op.create_table(
        "service_categories", _id(), _org(),
        sa.Column("slug", sa.String(80), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        *_ts("created_at", "updated_at"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_service_categories_org_slug"),
    )
    op.create_table(
        "marketplace_matching_settings", _id(), _org(), sa.Column("weights", sa.JSON, nullable=False),
        *_ts("created_at", "updated_at"), sa.UniqueConstraint("organization_id", name="uq_matching_settings_org"),
    )
    op.create_table(
        "customers", _id(), _org(),
        sa.Column("full_name", sa.String(200), nullable=False), sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(40)), *_ts("created_at", "updated_at"),
        sa.UniqueConstraint("organization_id", "email", name="uq_customers_org_email"),
    )
    op.create_table(
        "customer_requirements", _id(), _org(), _fk("customer_id", "customers.id"),
        _fk("category_id", "service_categories.id", "RESTRICT"),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("city", sa.String(120)),
        sa.Column("country", sa.String(2)), sa.Column("budget_min", MONEY), sa.Column("budget_max", MONEY),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("timeline", sa.String(120)),
        sa.Column("description", sa.Text), sa.Column("preferences", sa.JSON),
        sa.Column("contact_permission", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consent_reference", sa.String(255)),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        *_ts("created_at", "updated_at"),
        sa.CheckConstraint("budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
                           name="ck_requirement_budget"),
    )
    op.create_index("ix_requirements_org_status", "customer_requirements", ["organization_id", "status"])
    op.create_table(
        "service_providers", _id(), _org(),
        sa.Column("business_name", sa.String(300), nullable=False), sa.Column("legal_name", sa.String(300)),
        sa.Column("email", sa.String(320)), sa.Column("phone", sa.String(40)), sa.Column("website", sa.String(500)),
        sa.Column("description", sa.Text), sa.Column("service_areas", sa.JSON),
        sa.Column("experience_years", sa.Integer), sa.Column("portfolio", sa.JSON), sa.Column("credentials", sa.JSON),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="unverified"),
        sa.Column("availability", sa.String(20), nullable=False, server_default="available"),
        sa.Column("price_min", MONEY), sa.Column("price_max", MONEY),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("pricing_notes", sa.Text),
        _user("portal_user_id"), *_ts("created_at", "updated_at"),
        sa.CheckConstraint("verification_status IN ('unverified','pending','verified','rejected')",
                           name="ck_provider_verification_status"),
    )
    op.create_index("ix_service_providers_portal_user", "service_providers", ["portal_user_id"])
    op.create_table(
        "provider_categories", _id(), _org(), _fk("provider_id", "service_providers.id"),
        _fk("category_id", "service_categories.id"),
        sa.UniqueConstraint("provider_id", "category_id", name="uq_provider_category"),
    )
    op.create_table(
        "provider_documents", _id(), _org(), _fk("provider_id", "service_providers.id"),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False), sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("content", sa.LargeBinary, nullable=False),
        _user("uploaded_by"), *_ts("created_at"),
        sa.CheckConstraint("size_bytes <= 5242880", name="ck_provider_document_size"),
    )
    op.create_table(
        "provider_verifications", _id(), _org(), _fk("provider_id", "service_providers.id"),
        sa.Column("method", sa.String(20), nullable=False), sa.Column("registry_name", sa.String(80)),
        sa.Column("reference", sa.String(200)), sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("evidence", sa.Text), sa.Column("document_ids", sa.JSON), _user("verified_by"), *_ts("created_at"),
    )
    op.create_table(
        "provider_matches", _id(), _org(), _fk("requirement_id", "customer_requirements.id"),
        _fk("provider_id", "service_providers.id"), sa.Column("score", sa.Integer, nullable=False),
        sa.Column("explanation", sa.JSON, nullable=False), *_ts("created_at"),
    )
    op.create_index("ix_provider_matches_org_req", "provider_matches", ["organization_id", "requirement_id"])
    op.create_table(
        "referrals", _id(), _org(), _fk("requirement_id", "customer_requirements.id"),
        _fk("provider_id", "service_providers.id"), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("deal_value", MONEY), sa.Column("currency", sa.String(3), nullable=False),
        _user("created_by"), *_ts("created_at", "updated_at"),
        sa.UniqueConstraint("requirement_id", "provider_id", name="uq_referral_req_provider"),
    )
    op.create_index("ix_referrals_org_status", "referrals", ["organization_id", "status"])
    op.create_table(
        "referral_events", _id(), _org(), _fk("referral_id", "referrals.id"), _user("actor_user_id"),
        sa.Column("type", sa.String(40), nullable=False), sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)), sa.Column("note", sa.Text), *_ts("created_at"),
    )
    op.create_index("ix_referral_events_org_ref", "referral_events", ["organization_id", "referral_id", "created_at"])
    op.create_table(
        "commission_agreements", _id(), _org(), _fk("provider_id", "service_providers.id"),
        sa.Column("type", sa.String(20), nullable=False), sa.Column("value", sa.Numeric(14, 4)),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("splits", sa.JSON),
        sa.Column("settlement_conditions", sa.JSON),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("notes", sa.Text),
        *_ts("created_at", "updated_at"),
        sa.CheckConstraint("type IN ('fixed','percentage','negotiated')", name="ck_commission_agreement_type"),
    )
    op.create_table(
        "commission_transactions", _id(), _org(), _fk("referral_id", "referrals.id"),
        _fk("agreement_id", "commission_agreements.id", "SET NULL", True),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("reference", sa.String(200)),
        sa.Column("data", sa.JSON), _user("created_by"), *_ts("created_at"),
        sa.CheckConstraint("amount >= 0", name="ck_commission_tx_amount"),
        sa.CheckConstraint("kind IN ('accrual','invoice','payment','settlement','refund','dispute','reversal')",
                           name="ck_commission_tx_kind"),
    )
    op.create_index("ix_commission_tx_org_ref", "commission_transactions", ["organization_id", "referral_id"])
    op.create_table(
        "commission_disputes", _id(), _org(), _fk("referral_id", "referrals.id"), _user("raised_by"),
        sa.Column("reason", sa.Text, nullable=False), sa.Column("amount", MONEY),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"), sa.Column("resolution", sa.Text),
        *_ts("created_at", "updated_at"),
    )

    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"""DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN
            {' '.join(f'REVOKE UPDATE, DELETE ON {t} FROM {ROLE};' for t in APPEND_ONLY)}
          END IF;
        END $$;""")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in reversed(TABLES):
        op.drop_table(t)
