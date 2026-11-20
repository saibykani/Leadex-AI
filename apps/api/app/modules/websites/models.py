import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class WebsiteTemplate(IdMixin, TimestampMixin, Base):
    """Global (not tenant-scoped) catalogue of design templates."""

    __tablename__ = "website_templates"
    key: Mapped[str] = mapped_column(String(60), unique=True)
    industry: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    sections: Mapped[list] = mapped_column(JSON)
    theme: Mapped[dict] = mapped_column(JSON)


class WebsiteProject(IdMixin, TimestampMixin, Base):
    __tablename__ = "website_projects"
    __table_args__ = (Index("ix_website_projects_org_created", "organization_id", "created_at"),
                      Index("uq_website_projects_custom_domain", "custom_domain", unique=True))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    business_id: Mapped[uuid.UUID | None] = mapped_column()
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    template_key: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|preview|approved|published
    preview_token: Mapped[str] = mapped_column(String(64), unique=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column()
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column()
    published_version_id: Mapped[uuid.UUID | None] = mapped_column()
    custom_domain: Mapped[str | None] = mapped_column(String(255))
    domain_verification_status: Mapped[str] = mapped_column(String(20), default="none")  # none|pending|verified
    domain_verification_token: Mapped[str | None] = mapped_column(String(64))
    domain_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class WebsiteVersion(IdMixin, Base):
    """Immutable snapshot. Never updated after insert."""

    __tablename__ = "website_versions"
    __table_args__ = (Index("ix_website_versions_org_project", "organization_id", "project_id", "number"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("website_projects.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    rendered_html: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(300))
    generation_mode: Mapped[str] = mapped_column(String(20), default="template")  # template|ai|manual|restore
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WebsiteDeployment(IdMixin, Base):
    __tablename__ = "website_deployments"
    __table_args__ = (Index("ix_website_deployments_org_project", "organization_id", "project_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("website_projects.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("website_versions.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="live")  # live|superseded
    target: Mapped[str] = mapped_column(String(20), default="local")
    url: Mapped[str] = mapped_column(String(500))
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    deployed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    rolled_back_from: Mapped[uuid.UUID | None] = mapped_column()


class WebsiteFeedback(IdMixin, Base):
    __tablename__ = "website_feedback"
    __table_args__ = (Index("ix_website_feedback_org_project", "organization_id", "project_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("website_projects.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID | None] = mapped_column()
    name: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
