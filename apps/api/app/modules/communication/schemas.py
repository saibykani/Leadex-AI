import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmailAccountCreate(BaseModel):
    provider: Literal["smtp"] = "smtp"  # gmail/outlook are connected through OAuth
    address: EmailStr
    display_name: str | None = Field(None, max_length=200)


class EmailAccountOut(_Out):
    id: uuid.UUID
    provider: str
    address: str
    display_name: str | None
    status: str
    credentials_encrypted: bool
    last_error: str | None
    created_at: datetime


class ProviderStatus(BaseModel):
    gmail: str
    outlook: str
    smtp: str
    whatsapp: str
    outbound_mode: str


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=300)
    html: str = Field(min_length=1, max_length=200_000)
    text: str | None = Field(None, max_length=100_000)


class TemplatePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    subject: str | None = Field(None, min_length=1, max_length=300)
    html: str | None = Field(None, min_length=1, max_length=200_000)
    text: str | None = Field(None, max_length=100_000)


class TemplateOut(_Out):
    id: uuid.UUID
    name: str
    subject: str
    html: str
    text: str | None
    variables: list | None
    created_at: datetime
    updated_at: datetime


class PreviewIn(BaseModel):
    subject: str = Field(max_length=300)
    html: str = Field(max_length=200_000)
    text: str | None = Field(None, max_length=100_000)
    sample: dict[str, str] = Field(default_factory=dict)
    physical_address: str | None = Field(None, max_length=500)
    website_preview_url: str | None = Field(None, max_length=500)


class PreviewOut(BaseModel):
    subject: str
    html: str
    text: str
    variables: list[str]
    missing_variables: list[str]


class EmailMessageOut(_Out):
    id: uuid.UUID
    campaign_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    direction: str
    status: str
    step_index: int | None
    from_address: str | None
    to_address: str | None
    subject: str | None
    gate_reasons: list | None
    provider_message_id: str | None
    error: str | None
    created_at: datetime


class EmailAnalytics(BaseModel):
    total: int
    by_status: dict[str, int]
    sent: int
    delivered: int
    bounced: int
    replied: int
    simulated: int
    blocked: int
    inbound: int


class SuppressionIn(BaseModel):
    channel: Literal["email", "whatsapp"]
    value: str = Field(min_length=3, max_length=320)
    reason: str = Field("manual", max_length=60)


class SuppressionOut(_Out):
    id: uuid.UUID
    channel: str
    value: str
    reason: str
    source: str | None
    created_at: datetime


class WAAccountIn(BaseModel):
    phone_number_id: str = Field(min_length=3, max_length=64, pattern=r"^\d+$")
    display_phone: str | None = Field(None, max_length=40)
    business_account_id: str | None = Field(None, max_length=64)


class WAAccountOut(_Out):
    id: uuid.UUID
    phone_number_id: str
    display_phone: str | None
    business_account_id: str | None
    status: str
    created_at: datetime


class WATemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9_]+$")
    language: str = Field("en_US", max_length=10)
    category: Literal["marketing", "utility", "authentication"] = "marketing"
    body: str = Field(min_length=1, max_length=1024)


class WATemplateStatus(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class WATemplateOut(_Out):
    id: uuid.UUID
    name: str
    language: str
    category: str
    body: str
    status: str
    created_at: datetime


class ConversationOut(_Out):
    id: uuid.UUID
    contact_phone: str
    contact_name: str | None
    lead_id: uuid.UUID | None
    last_inbound_at: datetime | None
    last_message_at: datetime | None
    handoff_to_human: bool
    opted_out: bool


class ConversationPatch(BaseModel):
    handoff_to_human: bool | None = None
    lead_id: uuid.UUID | None = None


class WAMessageIn(BaseModel):
    text: str | None = Field(None, max_length=4096)
    template_id: uuid.UUID | None = None
    variables: list[str] = Field(default_factory=list, max_length=20)


class WAMessageOut(_Out):
    id: uuid.UUID
    conversation_id: uuid.UUID
    campaign_id: uuid.UUID | None
    direction: str
    status: str
    body: str | None
    gate_reasons: list | None
    provider_message_id: str | None
    error: str | None
    created_at: datetime


class InboundEmail(BaseModel):
    """Simulated/normalized inbound payload (a provider adapter or relay posts this shape).

    {"to": "sales@acme.example", "from": "owner@shop.example", "subject": "Re: ...", "text": "...",
     "in_reply_to": "<provider-message-id>"}
    """

    model_config = ConfigDict(populate_by_name=True)
    to: EmailStr
    from_: EmailStr = Field(alias="from")
    subject: str | None = Field(None, max_length=300)
    text: str | None = Field(None, max_length=100_000)
    in_reply_to: str | None = Field(None, max_length=255)


class EmailEvent(BaseModel):
    """{"account_address": "sales@acme.example", "provider_message_id": "...",
        "event": "delivered|bounced|complaint", "bounce_type": "hard|soft"}"""

    account_address: EmailStr
    provider_message_id: str = Field(max_length=255)
    event: Literal["delivered", "bounced", "complaint"]
    bounce_type: Literal["hard", "soft"] = "hard"
