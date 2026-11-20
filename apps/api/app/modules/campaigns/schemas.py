import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SendWindow(BaseModel):
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=24)


class EmailStep(BaseModel):
    template_id: uuid.UUID
    delay_hours: int = Field(0, ge=0, le=24 * 60)


class EmailConfig(BaseModel):
    account_id: uuid.UUID | None = None
    steps: list[EmailStep] = Field(default_factory=list, max_length=10)
    physical_address: str | None = Field(None, max_length=500)
    website_preview_base_url: str | None = Field(None, max_length=500)
    personalize_with_ai: bool = False


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    channel: Literal["email", "whatsapp", "voice"]
    spend_limit: Decimal | None = Field(None, ge=0)
    cost_per_message: Decimal = Field(Decimal(0), ge=0)
    send_window: SendWindow | None = None
    whatsapp_template_id: uuid.UUID | None = None
    email: EmailConfig | None = None
    voice_agent_id: uuid.UUID | None = None
    max_concurrent_calls: int = Field(3, ge=1, le=50)


class CampaignPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    spend_limit: Decimal | None = Field(None, ge=0)
    cost_per_message: Decimal | None = Field(None, ge=0)
    send_window: SendWindow | None = None
    whatsapp_template_id: uuid.UUID | None = None
    email: EmailConfig | None = None
    voice_agent_id: uuid.UUID | None = None
    max_concurrent_calls: int | None = Field(None, ge=1, le=50)


class CampaignOut(_Out):
    id: uuid.UUID
    name: str
    channel: str
    status: str
    spend_limit: Decimal | None
    cost_per_message: Decimal
    spent: Decimal
    send_window: dict | None
    whatsapp_template_id: uuid.UUID | None
    voice_agent_id: uuid.UUID | None = None
    max_concurrent_calls: int | None = None
    created_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class CampaignDetail(CampaignOut):
    email: EmailConfig | None = None
    recipient_counts: dict[str, int] = Field(default_factory=dict)


class RecipientsAdd(BaseModel):
    lead_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
    filter_status: list[str] | None = None
    filter_city: str | None = Field(None, max_length=120)
    filter_industry: str | None = Field(None, max_length=120)
    filter_country: str | None = Field(None, max_length=2)


class RecipientOut(_Out):
    id: uuid.UUID
    lead_id: uuid.UUID
    status: str
    gate_allowed: bool | None
    gate_simulated: bool | None
    gate_reasons: list | None
    current_step: int
    next_due_at: datetime | None
    last_sent_at: datetime | None
    business_name: str | None = None


class ApprovalIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=2000)


class ApprovalOut(_Out):
    id: uuid.UUID
    approver_user_id: uuid.UUID | None
    decision: str
    note: str | None
    created_at: datetime


class EventOut(_Out):
    id: uuid.UUID
    type: str
    data: dict | None
    actor_user_id: uuid.UUID | None
    created_at: datetime
