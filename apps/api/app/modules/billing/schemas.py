import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    price_monthly: Decimal
    currency: str
    limits: dict
    trial_days: int
    is_public: bool


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    status: str
    plan: PlanOut
    current_period_start: datetime
    current_period_end: datetime
    trial_end: datetime | None
    cancel_at_period_end: bool


class ChangePlan(BaseModel):
    plan_code: str = Field(min_length=1, max_length=40)


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    description: str
    quantity: Decimal
    unit_amount: Decimal
    amount: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    number: str
    status: str
    currency: str
    subtotal: Decimal
    total: Decimal
    period_start: datetime | None
    period_end: datetime | None
    due_at: datetime | None
    paid_at: datetime | None
    notes: str | None
    created_at: datetime
    lines: list[InvoiceLineOut] = []


class ChangeResult(BaseModel):
    subscription: SubscriptionOut
    invoice: InvoiceOut | None
    proration: dict


class UsageItem(BaseModel):
    resource: str
    used: float
    limit: int | None
    percent: float | None
    level: str  # ok | warning (>=50) | critical (>=80) | exceeded (>=100) | unlimited
    cost: Decimal


class UsageOut(BaseModel):
    period: str
    items: list[UsageItem]
    total_cost: Decimal


class BudgetBody(BaseModel):
    monthly_limit: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    alert_thresholds: list[int] = Field(default_factory=lambda: [50, 80, 100], max_length=10)
    hard_stop: bool = False
    paid_fallback_enabled: bool = False

    @field_validator("alert_thresholds")
    @classmethod
    def _thr(cls, v):
        if any(not 1 <= t <= 100 for t in v):
            raise ValueError("thresholds must be between 1 and 100")
        return sorted(set(v))


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    resource: str
    period: str
    threshold: int
    value: Decimal
    limit_value: Decimal
    created_at: datetime


class BudgetOut(BudgetBody):
    month_spend: Decimal
    alerts: list[AlertOut]


class PayBody(BaseModel):
    provider: str = "simulated"


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_id: uuid.UUID
    provider: str
    provider_reference: str | None
    amount: Decimal
    currency: str
    status: str
    simulated: bool
    error: str | None
    checkout_url: str | None = None


class ProviderOut(BaseModel):
    name: str
    status: str
    label: str
