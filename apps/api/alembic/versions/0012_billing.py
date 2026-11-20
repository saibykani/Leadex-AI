"""billing: plans (seeded), subscriptions, usage ledger, budgets, alerts, invoices, payments

Revision ID: 0012
Revises: 0011
"""
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"
ROLE = "leadex_app"
RLS_TABLES = ("subscriptions", "billing_usage", "budgets", "budget_alerts", "invoices", "invoice_lines", "payments")
APPEND_ONLY = ("billing_usage", "budget_alerts")
MONEY = sa.Numeric(14, 2)
TS = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731

RES = ("users", "leads", "searches", "ai_conversations", "voice_minutes", "email_campaigns", "websites",
       "workflows", "active_agents", "storage_mb")
# Snapshot of app.modules.billing.service.PLAN_CATALOG (migrations must not import mutable app code).
PLANS = [
    ("free_trial", "Free Trial", "0.00", 14, False, (2, 100, 50, 100, 30, 2, 1, 3, 1, 500)),
    ("starter", "Starter", "49.00", 0, True, (3, 1000, 500, 1000, 200, 10, 3, 10, 3, 5000)),
    ("professional", "Professional", "149.00", 0, True, (10, 10000, 3000, 10000, 1000, 50, 10, 50, 10, 25000)),
    ("business", "Business", "399.00", 0, True, (25, 50000, 10000, 50000, 5000, 200, 50, 200, 25, 100000)),
    ("enterprise", "Enterprise", "999.00", 0, True,
     (100, 500000, 50000, 250000, 25000, 1000, 250, 1000, 100, 1000000)),
    ("white_label", "White Label", "1999.00", 0, True, (None,) * 10),
]


def _org():
    return sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False)


def upgrade() -> None:
    plans = op.create_table(
        "plans",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("price_monthly", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("limits", sa.JSON, nullable=False),
        sa.Column("trial_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.true()),
        TS("created_at"), TS("updated_at"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("plan_id", sa.Uuid, sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trialing"),
        TS("current_period_start"), TS("current_period_end"),
        sa.Column("trial_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.false()),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", name="uq_subscriptions_org"),
    )
    op.create_table(
        "billing_usage",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("cost", MONEY, nullable=False, server_default="0"),
        sa.Column("campaign_id", sa.Uuid),
        sa.Column("lead_id", sa.Uuid),
        sa.Column("meta", sa.JSON),
        TS("created_at"),
    )
    op.create_index("ix_billing_usage_org_res_created", "billing_usage", ["organization_id", "resource", "created_at"])
    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("monthly_limit", MONEY),
        sa.Column("alert_thresholds", sa.JSON, nullable=False),
        sa.Column("hard_stop", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("paid_fallback_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        TS("created_at"), TS("updated_at"),
        sa.UniqueConstraint("organization_id", name="uq_budgets_org"),
    )
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("threshold", sa.Integer, nullable=False),
        sa.Column("value", sa.Numeric(14, 4), nullable=False),
        sa.Column("limit_value", sa.Numeric(14, 4), nullable=False),
        TS("created_at"),
        sa.UniqueConstraint("organization_id", "kind", "resource", "period", "threshold",
                            name="uq_budget_alerts_once"),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("subtotal", MONEY, nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_invoices_org_created", "invoices", ["organization_id", "created_at"])
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("invoice_id", sa.Uuid, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_amount", MONEY, nullable=False),
        sa.Column("amount", MONEY, nullable=False),
    )
    op.create_index("ix_invoice_lines_org_invoice", "invoice_lines", ["organization_id", "invoice_id"])
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid, primary_key=True), _org(),
        sa.Column("invoice_id", sa.Uuid, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_reference", sa.String(200)),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text),
        TS("created_at"), TS("updated_at"),
    )
    op.create_index("ix_payments_org_invoice", "payments", ["organization_id", "invoice_id"])

    now = datetime.now(UTC)
    op.bulk_insert(plans, [
        {"id": uuid.uuid5(uuid.NAMESPACE_URL, f"leadex:plan:{code}"), "code": code, "name": name,
         "price_monthly": Decimal(price), "currency": "USD", 
         "limits": json.loads(json.dumps(dict(zip(RES, lim, strict=True)))),
         "trial_days": trial, "sort_order": i, "is_public": public, "created_at": now, "updated_at": now}
        for i, (code, name, price, trial, public, lim) in enumerate(PLANS)
    ])

    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {t} USING (organization_id = {ORG}) "
                       f"WITH CHECK (organization_id = {ORG})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(RLS_TABLES)} TO {ROLE}")
        op.execute(f"GRANT SELECT ON plans TO {ROLE}")  # the catalog is read-only to the app at runtime
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON plans FROM {ROLE}")
        for t in APPEND_ONLY:
            op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
    for t in ("payments", "invoice_lines", "invoices", "budget_alerts", "budgets", "billing_usage", "subscriptions",
              "plans"):
        op.drop_table(t)
