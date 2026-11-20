import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _strong(v: str) -> str:
    if len(v) < 10 or not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("Password must be at least 10 characters and contain letters and digits")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=2, max_length=200)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _strong(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    otp_code: str | None = Field(default=None, max_length=8)


class RefreshRequest(BaseModel):
    # Browsers send the refresh token as the httpOnly `lx_refresh` cookie instead; API clients may send it here.
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationOut(_ORM):
    id: uuid.UUID
    name: str
    slug: str
    country_code: str | None
    is_platform_owner: bool
    status: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class MembershipOut(BaseModel):
    organization: OrganizationOut
    role: str
    permissions: list[str]


class UserOut(_ORM):
    id: uuid.UUID
    email: str
    full_name: str
    is_superadmin: bool
    mfa_enabled: bool
    email_verified_at: datetime | None = None


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str


class MemberAdd(BaseModel):
    email: EmailStr
    role: str = "Viewer"


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    is_system: bool
    permissions: list[str]


class AuditLogOut(_ORM):
    id: uuid.UUID
    action: str
    entity_type: str | None
    entity_id: str | None
    actor_user_id: uuid.UUID | None
    data: dict | None
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
