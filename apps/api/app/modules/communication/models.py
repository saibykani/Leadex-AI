"""Communication: email + WhatsApp accounts, templates, messages, unsubscribe tokens, suppressions.

`communication_routes` is the ONLY table here without row-level security: it maps a public external
identifier (WhatsApp phone_number_id, inbound email address) to an organization so unauthenticated
webhooks can bind the correct tenant before touching any tenant data. It holds no secrets or content.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


def _org():
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))


class CommunicationRoute(IdMixin, Base):
    __tablename__ = "communication_routes"
    __table_args__ = (UniqueConstraint("kind", "external_id", name="uq_comm_route_kind_ext"),)
    kind: Mapped[str] = mapped_column(String(30))  # whatsapp_phone | email_address
    external_id: Mapped[str] = mapped_column(String(320))
    organization_id: Mapped[uuid.UUID] = _org()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailAccount(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_accounts"
    __table_args__ = (Index("ix_email_accounts_org", "organization_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    provider: Mapped[str] = mapped_column(String(20))  # gmail | outlook | smtp
    address: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="not_configured")  # connected|not_configured|error
    credentials_enc: Mapped[str | None] = mapped_column(Text)  # OAuth token blob (encrypted when crypto exists)
    credentials_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class EmailTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_templates"
    __table_args__ = (Index("ix_email_templates_org", "organization_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    variables: Mapped[list | None] = mapped_column(JSON)


class EmailCampaign(IdMixin, TimestampMixin, Base):
    """Email configuration of a campaign: sender, follow-up sequence, CAN-SPAM postal address."""

    __tablename__ = "email_campaigns"
    __table_args__ = (UniqueConstraint("campaign_id", name="uq_email_campaign_campaign"),)
    organization_id: Mapped[uuid.UUID] = _org()
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_accounts.id", ondelete="SET NULL"))
    steps: Mapped[list] = mapped_column(JSON)  # [{"template_id": str, "delay_hours": int}]
    physical_address: Mapped[str | None] = mapped_column(String(500))
    website_preview_base_url: Mapped[str | None] = mapped_column(String(500))
    personalize_with_ai: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        Index("ix_email_messages_org_created", "organization_id", "created_at"),
        Index("ix_email_messages_org_campaign", "organization_id", "campaign_id"),
        Index("ix_email_messages_provider_id", "provider_message_id"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_accounts.id", ondelete="SET NULL"))
    direction: Mapped[str] = mapped_column(String(10))  # outbound | inbound
    # queued|simulated|blocked|sent|delivered|bounced|replied|failed|received
    status: Mapped[str] = mapped_column(String(20))
    step_index: Mapped[int | None] = mapped_column(Integer)
    from_address: Mapped[str | None] = mapped_column(String(320))
    to_address: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(300))
    html: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    gate_reasons: Mapped[list | None] = mapped_column(JSON)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    in_reply_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_messages.id", ondelete="SET NULL"))
    error: Mapped[str | None] = mapped_column(String(500))


class UnsubscribeToken(IdMixin, Base):
    __tablename__ = "unsubscribe_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_unsub_token_hash"),)
    organization_id: Mapped[uuid.UUID] = _org()
    token_hash: Mapped[str] = mapped_column(String(64))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(20), default="email")
    address: Mapped[str] = mapped_column(String(320))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommunicationSuppression(IdMixin, Base):
    __tablename__ = "communication_suppressions"
    __table_args__ = (UniqueConstraint("organization_id", "channel", "value", name="uq_comm_suppr"),)
    organization_id: Mapped[uuid.UUID] = _org()
    channel: Mapped[str] = mapped_column(String(20))  # email | whatsapp
    value: Mapped[str] = mapped_column(String(320))  # normalized email or phone digits
    reason: Mapped[str] = mapped_column(String(60))  # unsubscribe | bounce | complaint | opt_out_keyword | manual
    source: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WhatsAppAccount(IdMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_accounts"
    __table_args__ = (Index("ix_whatsapp_accounts_org", "organization_id"),)
    organization_id: Mapped[uuid.UUID] = _org()
    phone_number_id: Mapped[str] = mapped_column(String(64))
    display_phone: Mapped[str | None] = mapped_column(String(40))
    business_account_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="not_configured")


class WhatsAppTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_templates"
    __table_args__ = (UniqueConstraint("organization_id", "name", "language", name="uq_wa_template"),)
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(20))  # marketing | utility | authentication
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected


class WhatsAppConversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (UniqueConstraint("organization_id", "contact_phone", name="uq_wa_conv_contact"),)
    organization_id: Mapped[uuid.UUID] = _org()
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"))
    contact_phone: Mapped[str] = mapped_column(String(40))  # digits only
    contact_name: Mapped[str | None] = mapped_column(String(200))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handoff_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)


class WhatsAppMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        Index("ix_wa_messages_org_conv", "organization_id", "conversation_id", "created_at"),
        Index("ix_wa_messages_provider_id", "provider_message_id"),
    )
    organization_id: Mapped[uuid.UUID] = _org()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_templates.id", ondelete="SET NULL"))
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))  # simulated|blocked|sent|delivered|read|failed|received
    body: Mapped[str | None] = mapped_column(Text)
    gate_reasons: Mapped[list | None] = mapped_column(JSON)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(String(500))


def _register_gate_check() -> None:
    """Suppression list check plugged into the OutreachGate (blocks suppressed email/phone per channel)."""
    from sqlalchemy import select

    from app.modules.compliance.gate import register_check

    def check(db, org_id, lead, channel, _country):
        if channel == "email":
            value = getattr(lead, "email_normalized", None)
            if not value:
                return ["no_email_address"]
        elif channel == "whatsapp":
            value = getattr(lead, "phone_normalized", None)
            if not value:
                return ["no_phone_number"]
        else:
            return []
        hit = db.scalar(select(CommunicationSuppression.reason).where(
            CommunicationSuppression.organization_id == org_id, CommunicationSuppression.channel == channel,
            CommunicationSuppression.value == value).limit(1))
        return [f"suppressed:{hit}"] if hit else []

    register_check(check)


_register_gate_check()
