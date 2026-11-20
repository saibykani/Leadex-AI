import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

InquiryType = Literal["talk_to_sales", "demo_request", "partnership", "support", "general"]
TeamSize = Literal["1", "2-10", "11-50", "51-200", "201-1000", "1000+"]
INTERESTS = {"lead_generation", "ai_agents", "voice_agents", "website_studio", "campaigns", "whatsapp", "crm",
             "marketplace", "white_label", "compliance", "other"}
Status = Literal["new", "contacted", "qualified", "closed"]


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if any(ord(c) < 32 and c not in "\n\t" for c in v):
        raise ValueError("control characters are not allowed")
    return v or None


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: InquiryType
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    role: str | None = Field(None, max_length=120)
    team_size: TeamSize | None = None
    country: str | None = Field(None, pattern=r"^[A-Za-z]{2}$")
    phone: str | None = Field(None, max_length=40, pattern=r"^[0-9+()\-. ]{6,40}$")
    interests: list[str] = Field(default_factory=list, max_length=12)
    message: str | None = Field(None, max_length=4000)
    preferred_time: str | None = Field(None, max_length=120)
    timezone: str | None = Field(None, max_length=64)
    marketing_consent: bool = False
    privacy_ack: bool
    # anti-spam
    website: str | None = Field(None, max_length=200)  # honeypot: humans never see/fill it
    form_started_at: int = Field(description="client epoch milliseconds when the form was rendered")

    _strip = field_validator("name", "company", "role", "message", "preferred_time", "timezone")(_clean)

    @field_validator("interests")
    @classmethod
    def _interests(cls, v: list[str]) -> list[str]:
        bad = [i for i in v if i not in INTERESTS]
        if bad:
            raise ValueError(f"unknown interests: {bad}")
        return sorted(set(v))


class BookIn(ContactIn):
    type: Literal["demo_request"] = "demo_request"
    slot_start: datetime


class ContactOut(BaseModel):
    reference: str
    duplicate: bool = False
    ics_url: str | None = None
    slot_start: datetime | None = None


class PlanDisplayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_code: str = Field(max_length=40)
    price_monthly: Decimal | None = Field(None, ge=0, le=1_000_000)
    price_annual: Decimal | None = Field(None, ge=0, le=1_000_000)
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    contact_sales: bool = False
    highlight: bool = False
    badge: str | None = Field(None, max_length=40)
    tagline: str | None = Field(None, max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("bullets")
    @classmethod
    def _b(cls, v):
        v = [b.strip() for b in v if b and b.strip()]
        if any(len(b) > 120 for b in v):
            raise ValueError("bullets must be at most 120 characters")
        return v


class PlanDisplayBulk(BaseModel):
    items: list[PlanDisplayIn] = Field(max_length=20)


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: str = Field(max_length=64)
    weekdays: list[int] = Field(max_length=7)
    day_start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    day_end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    slot_minutes: int = Field(ge=10, le=240)
    buffer_minutes: int = Field(ge=0, le=120)
    min_notice_hours: int = Field(ge=0, le=168)
    horizon_days: int = Field(ge=1, le=180)
    booking_enabled: bool = True


class InquiryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reference: str
    type: str
    status: str
    name: str
    email: str
    company: str
    role: str | None
    team_size: str | None
    country: str | None
    phone: str | None
    interests: list | None
    message: str | None
    preferred_time: str | None
    timezone: str | None
    marketing_consent: bool
    booking_start: datetime | None
    lead_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None
    created_at: datetime


class InquiryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status | None = None
    assignee_user_id: uuid.UUID | None = None
    clear_assignee: bool = False
