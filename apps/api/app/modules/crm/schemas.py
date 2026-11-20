import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LeadBase(BaseModel):
    industry: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)
    score: int | None = Field(default=None, ge=0, le=100)
    owner_user_id: uuid.UUID | None = None
    custom_fields: dict | None = None


class LeadCreate(LeadBase):
    business_name: str = Field(min_length=1, max_length=300)
    source: str = Field(default="manual", max_length=60)


class LeadUpdate(LeadBase):
    business_name: str | None = Field(default=None, min_length=1, max_length=300)
    source: str | None = Field(default=None, max_length=60)


class LeadOut(_ORM):
    id: uuid.UUID
    organization_id: uuid.UUID
    business_name: str
    industry: str | None
    country: str | None
    city: str | None
    phone: str | None
    email: str | None
    website: str | None
    source: str
    status: str
    score: int | None
    owner_user_id: uuid.UUID | None
    consent_reference: str | None
    custom_fields: dict | None
    created_at: datetime
    updated_at: datetime


class StatusChange(BaseModel):
    status: str = Field(max_length=40)
    consent_reference: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=500)
    admin_override: bool = False


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class NoteOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: datetime | None = None
    assignee_user_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    due_at: datetime | None = None
    assignee_user_id: uuid.UUID | None = None
    completed: bool | None = None


class TaskOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID
    title: str
    due_at: datetime | None
    completed_at: datetime | None
    assignee_user_id: uuid.UUID | None
    created_at: datetime


class ActivityOut(_ORM):
    id: uuid.UUID
    lead_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    type: str
    data: dict | None
    created_at: datetime


class DashboardSummary(BaseModel):
    total_leads: int
    by_status: dict[str, int]
    open_tasks: int
    overdue_tasks: int
