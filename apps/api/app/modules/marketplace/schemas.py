import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Currency = Field(default="INR", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80, pattern="^[a-z0-9-]+$")


class CategoryOut(_ORM):
    id: uuid.UUID
    slug: str
    name: str
    is_system: bool


class Weights(BaseModel):
    category: int = Field(ge=0, le=100)
    location: int = Field(ge=0, le=100)
    budget: int = Field(ge=0, le=100)
    availability: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    verification: int = Field(ge=0, le=100)
    preferences: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _nonzero(self):
        if sum(self.model_dump().values()) == 0:
            raise ValueError("At least one weight must be positive")
        return self


class CustomerIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)


class CustomerOut(_ORM):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None


class RequirementCreate(BaseModel):
    customer: CustomerIn
    category_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    budget_min: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    budget_max: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str = Currency
    timeline: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    preferences: dict | None = None
    contact_permission: bool = False
    consent_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min must be <= budget_max")
        if self.contact_permission and not (self.consent_reference or "").strip():
            raise ValueError("consent_reference is required when contact_permission is granted")
        return self


class RequirementOut(_ORM):
    id: uuid.UUID
    customer_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    city: str | None
    country: str | None
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str
    timeline: str | None
    description: str | None
    preferences: dict | None
    contact_permission: bool
    consent_reference: str | None
    status: str
    created_at: datetime


class ProviderBase(BaseModel):
    legal_name: str | None = Field(default=None, max_length=300)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    service_areas: list[dict] | None = None
    experience_years: int | None = Field(default=None, ge=0, le=100)
    portfolio: list | None = None
    credentials: list | None = None
    availability: Literal["available", "limited", "unavailable"] | None = None
    price_min: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    price_max: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    pricing_notes: str | None = Field(default=None, max_length=2000)
    portal_user_id: uuid.UUID | None = None
    category_ids: list[uuid.UUID] | None = None


class ProviderCreate(ProviderBase):
    business_name: str = Field(min_length=1, max_length=300)


class ProviderUpdate(ProviderBase):
    business_name: str | None = Field(default=None, min_length=1, max_length=300)


class ProviderOut(_ORM):
    id: uuid.UUID
    business_name: str
    legal_name: str | None
    email: str | None
    phone: str | None
    website: str | None
    description: str | None
    service_areas: list | None
    experience_years: int | None
    portfolio: list | None
    credentials: list | None
    verification_status: str
    availability: str
    price_min: Decimal | None
    price_max: Decimal | None
    currency: str
    pricing_notes: str | None
    portal_user_id: uuid.UUID | None
    category_ids: list[uuid.UUID] = []
    created_at: datetime


class DocumentOut(_ORM):
    id: uuid.UUID
    provider_id: uuid.UUID
    document_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class VerifyIn(BaseModel):
    method: Literal["manual", "registry"] = "manual"
    decision: Literal["pending", "verified", "rejected"]
    registry_name: str | None = Field(default=None, max_length=80)
    reference: str | None = Field(default=None, max_length=200)
    evidence: str | None = Field(default=None, max_length=5000)
    document_ids: list[uuid.UUID] = []


class VerificationOut(_ORM):
    id: uuid.UUID
    method: str
    registry_name: str | None
    reference: str | None
    decision: str
    evidence: str | None
    document_ids: list | None
    verified_by: uuid.UUID | None
    created_at: datetime


class MatchOut(_ORM):
    id: uuid.UUID
    requirement_id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str | None = None
    score: int
    explanation: dict
    created_at: datetime


class ReferralCreate(BaseModel):
    requirement_id: uuid.UUID
    provider_id: uuid.UUID
    note: str | None = Field(default=None, max_length=2000)


class StatusIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=2000)
    deal_value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class ReferralOut(_ORM):
    id: uuid.UUID
    requirement_id: uuid.UUID
    provider_id: uuid.UUID
    status: str
    deal_value: Decimal | None
    currency: str
    created_at: datetime
    updated_at: datetime
    provider_name: str | None = None
    requirement_title: str | None = None


class EventOut(_ORM):
    id: uuid.UUID
    type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime


class Split(BaseModel):
    party: str = Field(min_length=1, max_length=120)
    pct: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)


class SettlementConditions(BaseModel):
    requires_converted: bool = True
    requires_invoice_paid: bool = True
    no_open_disputes: bool = True


class AgreementIn(BaseModel):
    provider_id: uuid.UUID
    type: Literal["fixed", "percentage", "negotiated"]
    value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)
    currency: str = Currency
    splits: list[Split] = []
    settlement_conditions: SettlementConditions = SettlementConditions()
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check(self):
        if self.type in ("fixed", "percentage") and self.value is None:
            raise ValueError("value is required for fixed and percentage agreements")
        if self.type == "percentage" and self.value is not None and self.value > 100:
            raise ValueError("percentage value must be <= 100")
        return self


class AgreementUpdate(BaseModel):
    value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)
    splits: list[Split] | None = None
    settlement_conditions: SettlementConditions | None = None
    active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AgreementOut(_ORM):
    id: uuid.UUID
    provider_id: uuid.UUID
    type: str
    value: Decimal | None
    currency: str
    splits: list | None
    settlement_conditions: dict | None
    active: bool
    notes: str | None
    created_at: datetime


class AccrueIn(BaseModel):
    agreement_id: uuid.UUID | None = None
    deal_value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class AmountIn(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    reference: str | None = Field(default=None, max_length=200)


class DisputeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=5000)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class DisputeResolve(BaseModel):
    status: Literal["resolved", "rejected"]
    resolution: str = Field(min_length=3, max_length=5000)
    reversal_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class DisputeOut(_ORM):
    id: uuid.UUID
    referral_id: uuid.UUID
    reason: str
    amount: Decimal | None
    status: str
    resolution: str | None
    created_at: datetime


class TxOut(_ORM):
    id: uuid.UUID
    referral_id: uuid.UUID
    agreement_id: uuid.UUID | None
    kind: str
    amount: Decimal
    currency: str
    reference: str | None
    data: dict | None
    created_at: datetime


class Balance(BaseModel):
    currency: str
    accrued: Decimal
    reversed: Decimal
    invoiced: Decimal
    paid: Decimal
    refunded: Decimal
    settled: Decimal
    outstanding: Decimal


class ReferralCommission(BaseModel):
    referral_id: uuid.UUID
    balances: list[Balance]
    transactions: list[TxOut]
    disputes: list[DisputeOut]
    settleable: bool
    blockers: list[str]


class CommissionSummary(BaseModel):
    balances: list[Balance]
    open_disputes: int
    transactions: list[TxOut]
