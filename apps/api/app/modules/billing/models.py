import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

MONEY = Numeric(14, 2)


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


class Plan(IdMixin, TimestampMixin, Base):
    """Global catalog (no organization_id, no RLS)."""

    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    price_monthly: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    limits: Mapped[dict] = mapped_column(JSON)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_subscriptions_org"),)
    organization_id: Mapped[uuid.UUID] = _org()
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(20), default="trialing")  # trialing | active | past_due | cancelled
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)


class BillingUsage(IdMixin, Base):
    """Append-only metering ledger."""

    __tablename__ = "billing_usage"
    __table_args__ = (Index("ix_billing_usage_org_res_created", "organization_id", "resource", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    resource: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column()
    lead_id: Mapped[uuid.UUID | None] = mapped_column()
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Budget(IdMixin, TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_budgets_org"),)
    organization_id: Mapped[uuid.UUID] = _org()
    monthly_limit: Mapped[Decimal | None] = mapped_column(MONEY)
    alert_thresholds: Mapped[list] = mapped_column(JSON, default=lambda: [50, 80, 100])
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class BudgetAlert(IdMixin, Base):
    __tablename__ = "budget_alerts"
    __table_args__ = (
        UniqueConstraint("organization_id", "kind", "resource", "period", "threshold", name="uq_budget_alerts_once"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    kind: Mapped[str] = mapped_column(String(20))  # budget | plan_limit
    resource: Mapped[str] = mapped_column(String(40))  # "spend" for budget alerts
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    threshold: Mapped[int] = mapped_column(Integer)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    limit_value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoices_org_created", "organization_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = _org()
    number: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | paid | void
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class InvoiceLine(IdMixin, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (Index("ix_invoice_lines_org_invoice", "organization_id", "invoice_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("1"))
    unit_amount: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_org_invoice", "organization_id", "invoice_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))  # simulated | stripe | razorpay
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20))  # succeeded | pending | failed
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)


class BillingWebhookEvent(IdMixin, Base):
    """Global (no RLS) idempotency ledger for provider webhooks. Holds only provider event ids/types."""

    __tablename__ = "billing_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_billing_webhook_event"),)
    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
