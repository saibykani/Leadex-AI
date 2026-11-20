import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- MFA
class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str


class MfaCode(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaDisable(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    password: str = Field(max_length=128)


class MfaStatus(BaseModel):
    mfa_enabled: bool


# ---- super admin
class AdminOrgOut(_ORM):
    id: uuid.UUID
    name: str
    slug: str
    country_code: str | None
    status: str
    is_platform_owner: bool
    created_at: datetime
    deleted_at: datetime | None


class AdminUserOut(_ORM):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime


class SuspendRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class OrgUsage(BaseModel):
    organization_id: uuid.UUID
    name: str
    status: str
    members: int
    leads: int


class UsageSummary(BaseModel):
    organizations: int
    active_organizations: int
    users: int
    leads: int
    per_organization: list[OrgUsage]


class AdminAuditOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: str | None
    data: dict | None
    ip_address: str | None
    created_at: datetime


# ---- integrations
class IntegrationOut(BaseModel):
    provider: str
    label: str
    status: str
    config: dict
    credential_names: list[str]
    required_credentials: list[str]
    updated_at: datetime | None


class IntegrationUpdate(BaseModel):
    config: dict[str, str | int | bool | None] | None = None
    credentials: dict[str, str] | None = None


# ---- notifications / support
class NotificationOut(_ORM):
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class TicketOut(_ORM):
    id: uuid.UUID
    subject: str
    body: str
    priority: str
    status: str
    created_by_user_id: uuid.UUID | None
    created_at: datetime
