import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CallCreate(BaseModel):
    lead_id: uuid.UUID
    agent_id: uuid.UUID
    direction: Literal["outbound"] = "outbound"
    record: bool = False
    recording_consent_reference: str | None = Field(default=None, max_length=255)


class CallOut(_ORM):
    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: uuid.UUID
    agent_id: uuid.UUID
    agent_version: int | None
    direction: str
    status: str
    gate_reasons: list | None
    provider: str
    language: str
    simulated: bool
    started_at: datetime | None
    ended_at: datetime | None
    duration_s: int | None
    created_at: datetime
    provider_call_id: str | None = None
    to_number: str | None = None
    error_message: str | None = None
    price: float | None = None
    price_unit: str | None = None


class EventOut(_ORM):
    id: uuid.UUID
    type: str
    data: dict | None
    created_at: datetime


class TranscriptOut(_ORM):
    seq: int
    speaker: str
    text: str
    simulated: bool
    created_at: datetime


class SummaryOut(_ORM):
    summary: str
    simulated: bool
    created_at: datetime


class DispositionOut(_ORM):
    disposition: str
    notes: str | None
    created_at: datetime


class RecordingOut(_ORM):
    enabled: bool
    consent_reference: str | None
    storage_key: str | None
    duration_s: int | None


class OutcomeOut(_ORM):
    interest: str
    budget_min: float | None
    budget_max: float | None
    budget_currency: str | None
    budget_evidence: str | None
    timeline: str | None
    timeline_evidence: str | None
    decision_maker: str | None
    next_step: str | None
    summary: str
    extraction_mode: str
    created_at: datetime


class TelephonyStatusOut(BaseModel):
    provider: str
    status: str  # not_configured | needs_public_url | configured
    mode: str  # not_configured | needs_public_url | simulated | test_allowlist | live
    detail: str
    credential_source: str | None
    from_number: str | None
    public_base_url: str | None
    app_env: str
    allow_test_calls: bool
    test_allowlist: list[str]
    voice_webhook_example: str | None


class CallDetail(CallOut):
    events: list[EventOut] = []
    transcript: list[TranscriptOut] = []
    summary: SummaryOut | None = None
    disposition: DispositionOut | None = None
    recording: RecordingOut | None = None
    outcome: OutcomeOut | None = None
