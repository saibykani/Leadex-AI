import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class OrganizationBranding(IdMixin, TimestampMixin, Base):
    """White-label settings. One row per organization (RLS). app_domain lets the web app show this brand on a
    custom domain's login page; public lookup goes through branding_for_domain() (SECURITY DEFINER)."""

    __tablename__ = "organization_branding"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"),
                                                       unique=True)
    app_name: Mapped[str | None] = mapped_column(String(80))
    logo_url: Mapped[str | None] = mapped_column(String(1000))
    primary_color: Mapped[str | None] = mapped_column(String(7))  # #RRGGBB
    support_email: Mapped[str | None] = mapped_column(String(320))
    app_domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    hide_powered_by: Mapped[bool] = mapped_column(Boolean, default=False)
