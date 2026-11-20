"""Email + WhatsApp endpoints. Public/webhook routes live on `public_router` (exposed via extra_routers)."""
import hmac
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, set_actor, set_tenant, utcnow
from app.core.errors import AppError
from app.core.security import hash_token
from app.core.tenancy import TenantContext, audit, build_context, require_permission
from app.modules.communication import service as svc
from app.modules.communication.models import (
    CommunicationSuppression,
    EmailAccount,
    EmailMessage,
    EmailTemplate,
    UnsubscribeToken,
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)
from app.modules.communication.schemas import (
    ConversationOut,
    ConversationPatch,
    EmailAccountCreate,
    EmailAccountOut,
    EmailAnalytics,
    EmailEvent,
    EmailMessageOut,
    InboundEmail,
    PreviewIn,
    PreviewOut,
    ProviderStatus,
    SuppressionIn,
    SuppressionOut,
    TemplateIn,
    TemplateOut,
    TemplatePatch,
    WAAccountIn,
    WAAccountOut,
    WAMessageIn,
    WAMessageOut,
    WATemplateIn,
    WATemplateOut,
    WATemplateStatus,
)
from app.modules.crm.models import Lead
from app.modules.identity.models import User
from app.modules.identity.schemas import Page

router = APIRouter(tags=["communication"])
public_router = APIRouter(tags=["communication-public"])

READ = require_permission("leads:read")
WRITE = require_permission("campaigns:write")
INTEGRATIONS = require_permission("integrations:manage")
REPLY = require_permission("leads:write")


def _audit(db, ctx: TenantContext, action, etype, eid, request, data=None):
    audit(db, action, org_id=ctx.organization_id, user_id=ctx.user.id, entity_type=etype, entity_id=eid,
          data=data, request=request)


def _get(db: Session, model, ctx: TenantContext, obj_id: uuid.UUID, label: str):
    row = db.scalar(select(model).where(model.id == obj_id, model.organization_id == ctx.organization_id))
    if row is None:
        raise AppError(404, "not_found", f"{label} not found")
    return row


def _page(db, base, order, out, page, page_size):
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return Page[out](items=[out.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


# ================================================================ providers / accounts
@router.get("/communication/providers", response_model=ProviderStatus)
def provider_status(_: TenantContext = Depends(READ)):
    return ProviderStatus(
        gmail="configured" if svc.oauth_configured("gmail") else "not_configured",
        outlook="configured" if svc.oauth_configured("outlook") else "not_configured",
        smtp="configured" if svc.env("SMTP_HOST") else "not_configured",
        whatsapp="configured" if svc.wa_configured()[0] else "not_configured",
        outbound_mode="simulated" if get_settings().outbound_simulated else "live",
    )


@router.get("/email/accounts", response_model=list[EmailAccountOut])
def list_accounts(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(EmailAccount).where(EmailAccount.organization_id == ctx.organization_id)
                      .order_by(EmailAccount.created_at)).all()


@router.post("/email/accounts", response_model=EmailAccountOut, status_code=201)
def create_smtp_account(body: EmailAccountCreate, request: Request, ctx: TenantContext = Depends(INTEGRATIONS),
                        db: Session = Depends(get_db)):
    addr = body.address.lower()
    svc.set_route(db, "email_address", addr, ctx.organization_id)
    acc = EmailAccount(organization_id=ctx.organization_id, provider="smtp", address=addr,
                       display_name=body.display_name, created_by_user_id=ctx.user.id,
                       status="connected" if svc.env("SMTP_HOST") else "not_configured")
    db.add(acc)
    db.flush()
    _audit(db, ctx, "email_account.create", "email_account", acc.id, request, {"provider": "smtp"})
    db.commit()
    return acc


@router.delete("/email/accounts/{account_id}", status_code=204)
def delete_account(account_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(INTEGRATIONS),
                   db: Session = Depends(get_db)):
    acc = _get(db, EmailAccount, ctx, account_id, "Email account")
    db.delete(acc)
    _audit(db, ctx, "email_account.delete", "email_account", account_id, request)
    db.commit()


@router.get("/email/oauth/{provider}/authorize")
def oauth_authorize(provider: str, ctx: TenantContext = Depends(INTEGRATIONS)):
    if provider not in svc.OAUTH:
        raise AppError(404, "not_found", "Unknown provider")
    if not svc.oauth_configured(provider):
        raise AppError(503, "not_configured", f"{provider} OAuth is not configured on this server")
    s = get_settings()
    cfg = svc.OAUTH[provider]
    state = jwt.encode({"org": str(ctx.organization_id), "uid": str(ctx.user.id), "p": provider, "typ": "oauth",
                        "n": secrets.token_hex(8), "exp": utcnow() + timedelta(minutes=10)},
                       s.jwt_secret, algorithm=s.jwt_algorithm)
    q = {"client_id": svc.env(cfg["id"]), "redirect_uri": svc.oauth_redirect_uri(provider), "response_type": "code",
         "scope": cfg["scope"], "state": state, **cfg["extra"]}
    return {"authorization_url": f"{cfg['auth_url']()}?{urlencode(q)}"}


@public_router.get("/oauth/email/{provider}/callback")
def oauth_callback(provider: str, request: Request, code: str | None = None, state: str | None = None,
                   error: str | None = None, db: Session = Depends(get_db)):
    web = (svc.env("WEB_APP_URL") or "http://localhost:3000").rstrip("/")
    if provider not in svc.OAUTH or not state:
        raise AppError(400, "invalid_request", "Invalid OAuth callback")
    s = get_settings()
    try:
        st = jwt.decode(state, s.jwt_secret, algorithms=[s.jwt_algorithm])
        if st.get("typ") != "oauth" or st.get("p") != provider:
            raise ValueError
        org_id, uid = uuid.UUID(st["org"]), uuid.UUID(st["uid"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise AppError(400, "invalid_state", "OAuth state is invalid or expired") from e
    if error or not code:
        return RedirectResponse(f"{web}/email?oauth_error={provider}", status_code=302)
    user = db.get(User, uid)
    if user is None or not user.is_active:
        raise AppError(400, "invalid_state", "OAuth state is invalid or expired")
    set_actor(db, uid)
    ctx = build_context(db, user, org_id)
    ctx.require("integrations:manage")
    cfg = svc.OAUTH[provider]
    with svc.http_client() as c:
        r = c.post(cfg["token_url"](), data={
            "client_id": svc.env(cfg["id"]), "client_secret": svc.env(cfg["secret"]), "code": code,
            "grant_type": "authorization_code", "redirect_uri": svc.oauth_redirect_uri(provider)})
    if r.status_code != 200:
        return RedirectResponse(f"{web}/email?oauth_error={provider}", status_code=302)
    tok = r.json()
    address = svc.fetch_mailbox_address(provider, tok["access_token"])
    if not address:
        return RedirectResponse(f"{web}/email?oauth_error={provider}", status_code=302)
    address = address.lower()
    svc.set_route(db, "email_address", address, org_id)
    acc = db.scalar(select(EmailAccount).where(EmailAccount.organization_id == org_id,
                                               EmailAccount.provider == provider, EmailAccount.address == address))
    if acc is None:
        acc = EmailAccount(organization_id=org_id, provider=provider, address=address, created_by_user_id=uid)
        db.add(acc)
    acc.credentials_enc, acc.credentials_encrypted = svc.seal(
        {"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token"), "scope": tok.get("scope")})
    acc.token_expires_at = utcnow() + timedelta(seconds=int(tok.get("expires_in", 3600)))
    acc.status, acc.last_error = "connected", None
    db.flush()
    _audit(db, ctx, "email_account.oauth_connect", "email_account", acc.id, request,
           {"provider": provider, "credentials_encrypted": acc.credentials_encrypted})
    db.commit()
    return RedirectResponse(f"{web}/email?connected={provider}", status_code=302)


# ================================================================ templates
@router.get("/email/templates", response_model=list[TemplateOut])
def list_templates(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(EmailTemplate).where(EmailTemplate.organization_id == ctx.organization_id)
                      .order_by(EmailTemplate.created_at.desc())).all()


@router.post("/email/templates", response_model=TemplateOut, status_code=201)
def create_template(body: TemplateIn, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    t = EmailTemplate(organization_id=ctx.organization_id, name=body.name, subject=body.subject,
                      html=svc.sanitize_html(body.html), text=body.text,
                      variables=svc.template_variables(body.subject, body.html, body.text))
    db.add(t)
    db.flush()
    _audit(db, ctx, "email_template.create", "email_template", t.id, request)
    db.commit()
    return t


@router.get("/email/templates/{template_id}", response_model=TemplateOut)
def get_template(template_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _get(db, EmailTemplate, ctx, template_id, "Template")


@router.patch("/email/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: uuid.UUID, body: TemplatePatch, request: Request,
                    ctx: TenantContext = Depends(WRITE), db: Session = Depends(get_db)):
    t = _get(db, EmailTemplate, ctx, template_id, "Template")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None and k != "text":
            continue
        setattr(t, k, svc.sanitize_html(v) if k == "html" else v)
    t.variables = svc.template_variables(t.subject, t.html, t.text)
    _audit(db, ctx, "email_template.update", "email_template", t.id, request)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/email/templates/{template_id}", status_code=204)
def delete_template(template_id: uuid.UUID, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    db.delete(_get(db, EmailTemplate, ctx, template_id, "Template"))
    _audit(db, ctx, "email_template.delete", "email_template", template_id, request)
    db.commit()


@router.post("/email/templates/preview", response_model=PreviewOut)
def preview_template(body: PreviewIn, _: TenantContext = Depends(READ)):
    values = {"business_name": "Sunrise Dental", "city": "Pune", "industry": "dental",
              "website_preview_url": body.website_preview_url or "https://preview.example/site", **body.sample}
    variables = svc.template_variables(body.subject, body.html, body.text)
    html = svc.wrap_responsive(svc.render(svc.sanitize_html(body.html), values, escape=True),
                               unsubscribe_url="#unsubscribe", physical_address=body.physical_address)
    text = svc.text_footer(svc.render(body.text or "", values, escape=False), "#unsubscribe", body.physical_address)
    return PreviewOut(subject=svc.render(body.subject, values, escape=False), html=html, text=text,
                      variables=variables, missing_variables=[v for v in variables if v not in values])


# ================================================================ messages / analytics / suppressions
@router.get("/email/messages", response_model=Page[EmailMessageOut])
def list_messages(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                  campaign_id: uuid.UUID | None = None, status: str | None = Query(None, max_length=20),
                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    base = select(EmailMessage).where(EmailMessage.organization_id == ctx.organization_id)
    if campaign_id:
        base = base.where(EmailMessage.campaign_id == campaign_id)
    if status:
        base = base.where(EmailMessage.status == status)
    return _page(db, base, (EmailMessage.created_at.desc(), EmailMessage.id), EmailMessageOut, page, page_size)


@router.get("/email/analytics", response_model=EmailAnalytics)
def email_analytics(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                    campaign_id: uuid.UUID | None = None):
    q = select(EmailMessage.direction, EmailMessage.status, func.count()).where(
        EmailMessage.organization_id == ctx.organization_id)
    if campaign_id:
        q = q.where(EmailMessage.campaign_id == campaign_id)
    by: dict[str, int] = {}
    inbound = 0
    for direction, status, n in db.execute(q.group_by(EmailMessage.direction, EmailMessage.status)).all():
        if direction == "inbound":
            inbound += n
            continue
        by[status] = by.get(status, 0) + n
    # A delivered/bounced/replied message was necessarily sent first.
    sent = sum(by.get(k, 0) for k in ("sent", "delivered", "bounced", "replied"))
    return EmailAnalytics(total=sum(by.values()), by_status=by, sent=sent, delivered=by.get("delivered", 0),
                          bounced=by.get("bounced", 0), replied=by.get("replied", 0),
                          simulated=by.get("simulated", 0), blocked=by.get("blocked", 0), inbound=inbound)


@router.get("/communication/suppressions", response_model=Page[SuppressionOut])
def list_suppressions(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                      page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    base = select(CommunicationSuppression).where(CommunicationSuppression.organization_id == ctx.organization_id)
    return _page(db, base, (CommunicationSuppression.created_at.desc(), CommunicationSuppression.id),
                 SuppressionOut, page, page_size)


@router.post("/communication/suppressions", status_code=201)
def add_suppression(body: SuppressionIn, request: Request, ctx: TenantContext = Depends(WRITE),
                    db: Session = Depends(get_db)):
    added = svc.suppress(db, ctx.organization_id, body.channel, body.value, body.reason,
                         f"user:{ctx.user.id}")
    _audit(db, ctx, "suppression.add", "suppression", None, request, {"channel": body.channel})
    db.commit()
    return {"added": added}


# ================================================================ public unsubscribe
def _lookup_token(db: Session, token: str) -> UnsubscribeToken:
    try:
        org_hex = token.split(".", 1)[0]
        org_id = uuid.UUID(hex=org_hex)
    except (ValueError, IndexError) as e:
        raise AppError(404, "not_found", "Unsubscribe link not found") from e
    set_tenant(db, org_id)
    row = db.scalar(select(UnsubscribeToken).where(UnsubscribeToken.token_hash == hash_token(token),
                                                   UnsubscribeToken.organization_id == org_id))
    if row is None:
        raise AppError(404, "not_found", "Unsubscribe link not found")
    return row


def apply_unsubscribe(db: Session, org_id: uuid.UUID, channel: str, address: str, lead_id, source: str) -> None:
    from app.modules.campaigns.service import mark_lead_unsubscribed

    svc.suppress(db, org_id, channel, address, "unsubscribe", source)
    if lead_id:
        mark_lead_unsubscribed(db, org_id, lead_id, source)


def _unsubscribe(db: Session, token: str, request: Request) -> HTMLResponse:
    row = _lookup_token(db, token)
    if row.used_at is None:
        row.used_at = utcnow()
        apply_unsubscribe(db, row.organization_id, row.channel, row.address, row.lead_id, "unsubscribe_link")
        audit(db, "communication.unsubscribe", org_id=row.organization_id, user_id=None,
              entity_type="unsubscribe_token", entity_id=row.id, data={"channel": row.channel}, request=request)
        db.commit()
    return HTMLResponse(
        "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='font-family:-apple-system,Segoe UI,sans-serif;background:#f5f5f7;display:grid;"
        "place-items:center;min-height:90vh'><div style='background:#fff;padding:32px;border-radius:16px;"
        "max-width:420px;text-align:center'><h1 style='font-size:20px'>You have been unsubscribed</h1>"
        "<p style='color:#6e6e73'>You will not receive further messages from this sender.</p></div></body>")


@public_router.get("/public/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_get(token: str, request: Request, db: Session = Depends(get_db)):
    return _unsubscribe(db, token, request)


@public_router.post("/public/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_post(token: str, request: Request, db: Session = Depends(get_db)):
    """RFC 8058 one-click (List-Unsubscribe-Post)."""
    return _unsubscribe(db, token, request)


# ================================================================ email webhooks
def _require_inbound_secret(secret: str | None) -> None:
    expected = svc.env("EMAIL_WEBHOOK_SECRET")
    if not expected:
        raise AppError(503, "not_configured", "EMAIL_WEBHOOK_SECRET is not configured")
    if not secret or not hmac.compare_digest(secret, expected):
        raise AppError(401, "invalid_signature", "Invalid webhook secret")


@public_router.post("/webhooks/email/inbound", status_code=202)
def email_inbound(body: InboundEmail, request: Request, db: Session = Depends(get_db),
                  x_leadex_webhook_secret: str | None = Header(default=None)):
    """Inbound reply processing. Header `X-Leadex-Webhook-Secret` must equal EMAIL_WEBHOOK_SECRET.
    Routed to the workspace that connected the `to` mailbox. Payload: see InboundEmail."""
    from app.modules.campaigns.service import mark_lead_replied

    _require_inbound_secret(x_leadex_webhook_secret)
    org_id = svc.route_org(db, "email_address", body.to)
    if org_id is None:
        return {"accepted": False, "reason": "unknown_mailbox"}
    set_tenant(db, org_id)
    sender = body.from_.lower()
    original = None
    if body.in_reply_to:
        original = db.scalar(select(EmailMessage).where(EmailMessage.organization_id == org_id,
                                                        EmailMessage.provider_message_id == body.in_reply_to))
    lead_id = original.lead_id if original else db.scalar(select(Lead.id).where(
        Lead.organization_id == org_id, Lead.email_normalized == sender, Lead.deleted_at.is_(None)).limit(1))
    msg = EmailMessage(organization_id=org_id, direction="inbound", status="received", lead_id=lead_id,
                       campaign_id=original.campaign_id if original else None, from_address=sender,
                       to_address=body.to.lower(), subject=body.subject, text=body.text,
                       in_reply_to_id=original.id if original else None)
    db.add(msg)
    if original is not None and original.status in {"sent", "delivered"}:
        original.status = "replied"
    first_line = (body.text or "").strip().splitlines()[0] if (body.text or "").strip() else ""
    opted_out = svc.is_opt_out(first_line) or svc.is_opt_out(body.subject)
    if opted_out:
        apply_unsubscribe(db, org_id, "email", sender, lead_id, "reply_keyword")
    elif lead_id:
        mark_lead_replied(db, org_id, lead_id)
    db.flush()
    audit(db, "email.inbound", org_id=org_id, user_id=None, entity_type="email_message", entity_id=msg.id,
          data={"opt_out": opted_out}, request=request)
    db.commit()
    return {"accepted": True, "message_id": str(msg.id), "opt_out": opted_out}


@public_router.post("/webhooks/email/events", status_code=202)
def email_events(body: EmailEvent, request: Request, db: Session = Depends(get_db),
                 x_leadex_webhook_secret: str | None = Header(default=None)):
    """Delivery/bounce/complaint events. Hard bounces and complaints suppress the address."""
    _require_inbound_secret(x_leadex_webhook_secret)
    org_id = svc.route_org(db, "email_address", body.account_address)
    if org_id is None:
        return {"accepted": False, "reason": "unknown_mailbox"}
    set_tenant(db, org_id)
    msg = db.scalar(select(EmailMessage).where(EmailMessage.organization_id == org_id,
                                               EmailMessage.provider_message_id == body.provider_message_id))
    if msg is None:
        return {"accepted": False, "reason": "unknown_message"}
    if body.event == "delivered" and msg.status == "sent":
        msg.status = "delivered"
    elif body.event == "bounced":
        msg.status = "bounced"
        if body.bounce_type == "hard":
            svc.suppress(db, org_id, "email", msg.to_address, "bounce", f"message:{msg.id}")
    elif body.event == "complaint":
        svc.suppress(db, org_id, "email", msg.to_address, "complaint", f"message:{msg.id}")
    audit(db, f"email.event.{body.event}", org_id=org_id, user_id=None, entity_type="email_message",
          entity_id=msg.id, request=request)
    db.commit()
    return {"accepted": True, "status": msg.status}


# ================================================================ WhatsApp
@router.get("/whatsapp/accounts", response_model=list[WAAccountOut])
def wa_accounts(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == ctx.organization_id)).all()


@router.post("/whatsapp/accounts", response_model=WAAccountOut, status_code=201)
def wa_create_account(body: WAAccountIn, request: Request, ctx: TenantContext = Depends(INTEGRATIONS),
                      db: Session = Depends(get_db)):
    svc.set_route(db, "whatsapp_phone", body.phone_number_id, ctx.organization_id)
    acc = WhatsAppAccount(organization_id=ctx.organization_id, phone_number_id=body.phone_number_id,
                          display_phone=body.display_phone, business_account_id=body.business_account_id,
                          status="connected" if svc.wa_configured()[0] else "not_configured")
    db.add(acc)
    db.flush()
    _audit(db, ctx, "whatsapp_account.create", "whatsapp_account", acc.id, request)
    db.commit()
    return acc


@router.get("/whatsapp/templates", response_model=list[WATemplateOut])
def wa_templates(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(WhatsAppTemplate).where(WhatsAppTemplate.organization_id == ctx.organization_id)
                      .order_by(WhatsAppTemplate.created_at.desc())).all()


@router.post("/whatsapp/templates", response_model=WATemplateOut, status_code=201)
def wa_create_template(body: WATemplateIn, request: Request, ctx: TenantContext = Depends(WRITE),
                       db: Session = Depends(get_db)):
    exists = db.scalar(select(WhatsAppTemplate.id).where(
        WhatsAppTemplate.organization_id == ctx.organization_id, WhatsAppTemplate.name == body.name,
        WhatsAppTemplate.language == body.language))
    if exists:
        raise AppError(409, "duplicate_template", "A template with this name and language exists")
    t = WhatsAppTemplate(organization_id=ctx.organization_id, status="pending", **body.model_dump())
    db.add(t)
    db.flush()
    _audit(db, ctx, "whatsapp_template.create", "whatsapp_template", t.id, request)
    db.commit()
    return t


@router.post("/whatsapp/templates/{template_id}/status", response_model=WATemplateOut)
def wa_template_status(template_id: uuid.UUID, body: WATemplateStatus, request: Request,
                       ctx: TenantContext = Depends(INTEGRATIONS), db: Session = Depends(get_db)):
    """Records Meta's review outcome. Automated sync from the Business Management API is not implemented;
    an integrations admin mirrors the status shown in WhatsApp Manager."""
    t = _get(db, WhatsAppTemplate, ctx, template_id, "Template")
    old, t.status = t.status, body.status
    _audit(db, ctx, "whatsapp_template.status", "whatsapp_template", t.id, request, {"from": old, "to": t.status})
    db.commit()
    return t


@router.get("/whatsapp/conversations", response_model=Page[ConversationOut])
def wa_conversations(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db),
                     handoff: bool | None = None, page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=200)):
    base = select(WhatsAppConversation).where(WhatsAppConversation.organization_id == ctx.organization_id)
    if handoff is not None:
        base = base.where(WhatsAppConversation.handoff_to_human == handoff)
    return _page(db, base, (WhatsAppConversation.last_message_at.desc(), WhatsAppConversation.id),
                 ConversationOut, page, page_size)


@router.patch("/whatsapp/conversations/{conv_id}", response_model=ConversationOut)
def wa_patch_conversation(conv_id: uuid.UUID, body: ConversationPatch, request: Request,
                          ctx: TenantContext = Depends(REPLY), db: Session = Depends(get_db)):
    conv = _get(db, WhatsAppConversation, ctx, conv_id, "Conversation")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("lead_id"):
        _get(db, Lead, ctx, changes["lead_id"], "Lead")
    for k, v in changes.items():
        if k == "handoff_to_human" and v is None:
            continue
        setattr(conv, k, v)
    _audit(db, ctx, "whatsapp_conversation.update", "whatsapp_conversation", conv.id, request,
           {"fields": sorted(changes)})
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/whatsapp/conversations/{conv_id}/messages", response_model=list[WAMessageOut])
def wa_messages(conv_id: uuid.UUID, ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    _get(db, WhatsAppConversation, ctx, conv_id, "Conversation")
    return db.scalars(select(WhatsAppMessage).where(WhatsAppMessage.organization_id == ctx.organization_id,
                                                    WhatsAppMessage.conversation_id == conv_id)
                      .order_by(WhatsAppMessage.created_at, WhatsAppMessage.id).limit(500)).all()


@router.post("/whatsapp/conversations/{conv_id}/messages", response_model=WAMessageOut, status_code=201)
def wa_send(conv_id: uuid.UUID, body: WAMessageIn, request: Request, ctx: TenantContext = Depends(REPLY),
            db: Session = Depends(get_db)):
    conv = _get(db, WhatsAppConversation, ctx, conv_id, "Conversation")
    if not body.text and not body.template_id:
        raise AppError(422, "validation_error", "Provide text or template_id")
    template = _get(db, WhatsAppTemplate, ctx, body.template_id, "Template") if body.template_id else None
    account = db.scalar(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == ctx.organization_id)
                        .order_by(WhatsAppAccount.created_at).limit(1))
    msg = svc.send_whatsapp(db, org_id=ctx.organization_id, conv=conv, account=account, text=body.text,
                            template=template, variables=body.variables)
    _audit(db, ctx, "whatsapp.send", "whatsapp_message", msg.id, request,
           {"status": msg.status, "reasons": msg.gate_reasons})
    db.commit()
    return msg


@public_router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def wa_verify(hub_mode: str | None = Query(None, alias="hub.mode"),
              hub_token: str | None = Query(None, alias="hub.verify_token"),
              hub_challenge: str | None = Query(None, alias="hub.challenge")):
    expected = svc.env("WA_VERIFY_TOKEN")
    if not expected:
        raise AppError(503, "not_configured", "WA_VERIFY_TOKEN is not configured")
    if hub_mode == "subscribe" and hub_token and hmac.compare_digest(hub_token, expected) and hub_challenge:
        return hub_challenge
    raise AppError(403, "forbidden", "Verification failed")


_WA_STATUS_ORDER = {"sent": 1, "delivered": 2, "read": 3}


@public_router.post("/webhooks/whatsapp")
async def wa_receive(request: Request, db: Session = Depends(get_db),
                     x_hub_signature_256: str | None = Header(default=None)):
    raw = await request.body()
    if not svc.env("WA_APP_SECRET"):
        raise AppError(503, "not_configured", "WA_APP_SECRET is not configured")
    if not svc.verify_wa_signature(raw, x_hub_signature_256):
        raise AppError(401, "invalid_signature", "Invalid X-Hub-Signature-256")
    import json

    try:
        payload = json.loads(raw or b"{}")
    except ValueError as e:
        raise AppError(400, "invalid_payload", "Body must be JSON") from e
    processed = {"messages": 0, "statuses": 0, "opt_outs": 0}
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            phone_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
            org_id = svc.route_org(db, "whatsapp_phone", phone_id)
            if org_id is None:
                continue
            set_tenant(db, org_id)
            _wa_process(db, org_id, phone_id, value, processed)
    db.commit()
    return {"ok": True, **processed}


def _wa_process(db: Session, org_id: uuid.UUID, phone_id: str, value: dict, processed: dict) -> None:
    account = db.scalar(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == org_id,
                                                      WhatsAppAccount.phone_number_id == phone_id))
    names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}
    for m in value.get("messages", []) or []:
        sender = str(m.get("from") or "")
        if not sender:
            continue
        if m.get("id") and db.scalar(select(WhatsAppMessage.id).where(
                WhatsAppMessage.organization_id == org_id, WhatsAppMessage.provider_message_id == m["id"])):
            continue  # webhook retries are idempotent
        conv = svc.get_conversation(db, org_id, sender, account)
        conv.contact_name = names.get(sender) or conv.contact_name
        body = (m.get("text") or {}).get("body") if m.get("type") == "text" else f"[{m.get('type')}]"
        if m.get("type") == "button":
            body = (m.get("button") or {}).get("text")
        now = utcnow()
        conv.last_inbound_at = conv.last_message_at = now
        db.add(WhatsAppMessage(organization_id=org_id, conversation_id=conv.id, lead_id=conv.lead_id,
                               direction="inbound", status="received", body=body,
                               provider_message_id=m.get("id")))
        processed["messages"] += 1
        if svc.is_opt_out(body):
            conv.opted_out = True
            apply_unsubscribe(db, org_id, "whatsapp", sender, conv.lead_id, "whatsapp_keyword")
            processed["opt_outs"] += 1
        else:
            conv.handoff_to_human = True  # a human (or the AI agent module) must pick up the reply
            if conv.lead_id:
                from app.modules.campaigns.service import mark_lead_replied

                mark_lead_replied(db, org_id, conv.lead_id)
        db.flush()
    for st in value.get("statuses", []) or []:
        msg = db.scalar(select(WhatsAppMessage).where(WhatsAppMessage.organization_id == org_id,
                                                      WhatsAppMessage.provider_message_id == st.get("id")))
        new = st.get("status")
        if msg is None or new not in {"sent", "delivered", "read", "failed"}:
            continue
        if new == "failed":
            msg.status, msg.error = "failed", str((st.get("errors") or [{}])[0].get("title", "failed"))[:500]
        elif _WA_STATUS_ORDER.get(new, 0) > _WA_STATUS_ORDER.get(msg.status, 0):
            msg.status = new
        processed["statuses"] += 1


extra_routers = [public_router]
