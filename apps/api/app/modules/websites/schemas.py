import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SectionType = Literal["hero", "services", "about", "gallery", "contact", "cta"]
S = lambda n: Field(default=None, max_length=n)  # noqa: E731


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    industry: str
    name: str
    sections: list
    theme: dict


class BusinessFacts(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = S(120)
    tagline: str | None = S(200)
    description: str | None = S(2000)
    services: list[str] = Field(default_factory=list, max_length=12)
    city: str | None = S(120)
    address: str | None = S(300)
    country: str | None = S(2)
    phone: str | None = S(40)
    email: str | None = S(320)
    hours: str | None = S(200)
    whatsapp_number: str | None = S(40)
    whatsapp_authorized: bool = False  # only true when the business authorised WhatsApp contact


class GenerateIn(BaseModel):
    template_key: str = Field(max_length=60)
    name: str | None = S(200)
    business: BusinessFacts | None = None
    lead_id: uuid.UUID | None = None
    business_id: uuid.UUID | None = None
    use_ai: bool = True
    # Optional approved business images (owner-supplied / from the business's own website, permission confirmed).
    # Google Places photos are not accepted here (Maps Platform terms); see app.modules.pipeline.images.
    images: list[uuid.UUID] = Field(default_factory=list, max_length=12)


class Item(BaseModel):
    title: str | None = S(200)
    description: str | None = S(1000)


class Section(BaseModel):
    type: SectionType
    heading: str = Field(default="", max_length=200)
    body: str | None = S(5000)
    enabled: bool = True
    cta_label: str | None = S(60)
    items: list[Item] | None = Field(default=None, max_length=24)


class BusinessInfo(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry_label: str | None = S(120)
    tagline: str | None = S(200)
    description: str | None = S(2000)
    city: str | None = S(120)
    address: str | None = S(300)
    country: str | None = S(2)
    phone: str | None = S(40)
    email: str | None = S(320)
    hours: str | None = S(200)
    whatsapp_number: str | None = S(40)
    whatsapp_authorized: bool = False


class Seo(BaseModel):
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=300)


class Content(BaseModel):
    business: BusinessInfo
    seo: Seo = Field(default_factory=Seo)
    sections: list[Section] = Field(max_length=12)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    template_key: str | None = S(60)
    content: Content | None = None
    note: str | None = S(300)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    template_key: str
    status: str
    business_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    current_version_id: uuid.UUID | None
    approved_version_id: uuid.UUID | None
    published_version_id: uuid.UUID | None
    custom_domain: str | None
    domain_verification_status: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    current_version_number: int | None = None
    content: dict | None = None
    rendered_html: str | None = None
    generation_mode: str | None = None
    preview_path: str
    published_path: str | None = None


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    number: int
    note: str | None
    generation_mode: str
    created_by: uuid.UUID | None
    created_at: datetime


class VersionDetail(VersionOut):
    content: dict
    rendered_html: str


class RenderIn(BaseModel):
    content: Content
    template_key: str | None = S(60)


class PreviewLinkIn(BaseModel):
    rotate: bool = False


class PreviewLinkOut(BaseModel):
    token: str
    path: str


class RollbackIn(BaseModel):
    version_id: uuid.UUID


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version_id: uuid.UUID
    status: str
    target: str
    url: str
    deployed_at: datetime
    rolled_back_from: uuid.UUID | None


class FeedbackIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    approved: bool = False


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version_id: uuid.UUID | None
    name: str
    message: str
    approved: bool
    created_at: datetime


class DomainIn(BaseModel):
    domain: str = Field(min_length=3, max_length=255)


class DomainOut(BaseModel):
    domain: str | None
    status: str  # none|pending|verified
    verified_at: datetime | None = None
    record_type: str = "TXT"
    record_name: str | None = None
    record_value: str | None = None
    message: str | None = None
