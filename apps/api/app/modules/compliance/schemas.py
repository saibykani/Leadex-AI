import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Channel = Literal["voice", "email", "whatsapp", "sms"]
ChannelOrAll = Literal["voice", "email", "whatsapp", "sms", "all"]
Basis = Literal["express_consent", "written_consent", "existing_relationship", "legitimate_interest",
                "inbound_request"]


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ConsentCreate(BaseModel):
    lead_id: uuid.UUID
    channel: Channel
    basis: Basis
    evidence_text: str | None = Field(default=None, max_length=5000)
    evidence_url: str | None = Field(default=None, max_length=1000)
    captured_at: datetime | None = None

    @model_validator(mode="after")
    def need_evidence(self):
        if not (self.evidence_text or "").strip() and not (self.evidence_url or "").strip():
            raise ValueError("evidence_text or evidence_url is required")
        return self


class ConsentUpdate(BaseModel):
    basis: Basis | None = None
    evidence_text: str | None = Field(default=None, max_length=5000)
    evidence_url: str | None = Field(default=None, max_length=1000)


class WithdrawRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ConsentOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    basis: str
    evidence_text: str | None
    evidence_url: str | None
    captured_at: datetime
    withdrawn_at: datetime | None
    withdrawn_reason: str | None
    created_at: datetime


class SuppressionCreate(BaseModel):
    channel: ChannelOrAll = "all"
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def need_contact(self):
        if not (self.email or "").strip() and not (self.phone or "").strip():
            raise ValueError("email or phone is required")
        return self


class SuppressionOut(_ORM):
    id: uuid.UUID
    channel: str
    email_normalized: str | None
    phone_normalized: str | None
    reason: str
    created_at: datetime


class PreferenceSet(BaseModel):
    channel: Channel
    allowed: bool
    notes: str | None = Field(default=None, max_length=500)


class PreferenceOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    allowed: bool
    notes: str | None
    updated_at: datetime


class KillSwitchCreate(BaseModel):
    scope: Literal["global", "organization"] = "organization"
    channel: ChannelOrAll = "all"
    reason: str = Field(min_length=1, max_length=500)


class KillSwitchOut(_ORM):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    scope: str
    channel: str
    active: bool
    reason: str
    set_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CheckRequest(BaseModel):
    lead_id: uuid.UUID
    channel: str = Field(max_length=20)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class CheckResponse(BaseModel):
    allowed: bool
    simulated: bool
    reasons: list[str]
    jurisdiction: str | None


class JurisdictionOut(_ORM):
    code: str
    name: str
    rules: dict


DsrType = Literal["access", "correction", "deletion", "export", "withdrawal"]
DsrStatus = Literal["open", "in_progress", "completed", "rejected"]


class DsrCreate(BaseModel):
    type: DsrType
    subject_email: str | None = Field(default=None, max_length=320)
    subject_phone: str | None = Field(default=None, max_length=40)
    lead_id: uuid.UUID | None = None
    details: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def need_subject(self):
        if not (self.subject_email or self.subject_phone or self.lead_id):
            raise ValueError("subject_email, subject_phone or lead_id is required")
        return self


class DsrUpdate(BaseModel):
    status: DsrStatus
    resolution: str | None = Field(default=None, max_length=5000)


class DsrOut(_ORM):
    id: uuid.UUID
    type: str
    status: str
    subject_email: str | None
    subject_phone: str | None
    lead_id: uuid.UUID | None
    details: str | None
    resolution: str | None
    due_at: datetime
    completed_at: datetime | None
    created_at: datetime
