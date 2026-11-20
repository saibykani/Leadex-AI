"""Communication domain services: template rendering, suppression, provider adapters, gated dispatch.

Send rule (never relaxed): a real provider call happens ONLY when
    gate.allowed and not gate.simulated and the provider is configured/connected.
Otherwise the message row is recorded as `blocked` (gate refused) or `simulated` (with the reason),
and nothing is claimed as delivered. `sent` means the provider accepted it; `delivered` only comes
from a provider event/webhook.
"""
from __future__ import annotations

import hashlib
import hmac
import html as htmlmod
import importlib
import json
import logging
import os
import re
import secrets
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.security import hash_token
from app.modules.communication.models import (
    CommunicationRoute,
    CommunicationSuppression,
    EmailAccount,
    EmailMessage,
    UnsubscribeToken,
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)
from app.modules.compliance.gate import GateDecision, check_outreach
from app.modules.crm.models import Lead

log = logging.getLogger(__name__)

WA_GRAPH = "https://graph.facebook.com/v21.0"
OPT_OUT_KEYWORDS = {"stop", "unsubscribe", "stopall", "cancel", "end", "quit", "opt out", "optout"}
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def env(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else None


def smtp_user() -> str | None:
    """SMTP_USER is canonical; SMTP_USERNAME is accepted as a legacy fallback."""
    return env("SMTP_USER") or env("SMTP_USERNAME")


def public_base_url() -> str:
    return (env("PUBLIC_API_URL") or "http://localhost:8000").rstrip("/")


# ------------------------------------------------------------------ HTTP (tests swap the transport)
_transport: httpx.BaseTransport | None = None


def set_transport(t: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = t


def http_client() -> httpx.Client:
    return httpx.Client(timeout=15.0, transport=_transport)


# ------------------------------------------------------------------ credentials at rest
def _crypto():
    try:
        return importlib.import_module("app.modules.compliance.crypto")
    except ModuleNotFoundError:
        return None


def seal(data: dict) -> tuple[str, bool]:
    raw = json.dumps(data)
    c = _crypto()
    fn = c and (getattr(c, "encrypt_str", None) or getattr(c, "encrypt", None))
    if fn:
        return fn(raw), True
    # TODO(security): compliance.crypto (Fernet) not available yet -> stored unencrypted. Flagged via
    # credentials_encrypted=False so a backfill job can re-seal rows once the helper ships.
    return raw, False


def unseal(blob: str | None, encrypted: bool) -> dict:
    if not blob:
        return {}
    if encrypted:
        c = _crypto()
        fn = c and (getattr(c, "decrypt_str", None) or getattr(c, "decrypt", None))
        if not fn:
            raise AppError(503, "crypto_unavailable", "Credential decryption helper unavailable")
        blob = fn(blob)
    return json.loads(blob)


# ------------------------------------------------------------------ templates
_SCRIPT = re.compile(r"<\s*(script|iframe|object|embed)\b.*?(<\s*/\s*\1\s*>|$)", re.I | re.S)
_ON_ATTR = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_URL = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.I)


def sanitize_html(src: str) -> str:
    """Strip active content from author-supplied HTML (scripts, event handlers, javascript: URLs)."""
    out = _SCRIPT.sub("", src)
    out = _ON_ATTR.sub("", out)
    return _JS_URL.sub(r'\1="#"', out)


def template_variables(*parts: str | None) -> list[str]:
    found: list[str] = []
    for p in parts:
        for m in _VAR.finditer(p or ""):
            if m.group(1) not in found:
                found.append(m.group(1))
    return found


def render(src: str, values: dict, *, escape: bool) -> str:
    def sub(m):
        v = values.get(m.group(1))
        v = "" if v is None else str(v)
        return htmlmod.escape(v, quote=True) if escape else v

    return _VAR.sub(sub, src or "")


def lead_values(lead: Lead | None, extra: dict | None = None) -> dict:
    vals = {}
    if lead is not None:
        vals = {"business_name": lead.business_name, "city": lead.city or "", "industry": lead.industry or "",
                "website": lead.website or "", "email": lead.email or "", "country": lead.country or ""}
    vals.update(extra or {})
    return vals


def wrap_responsive(body_html: str, *, unsubscribe_url: str | None, physical_address: str | None) -> str:
    addr = htmlmod.escape(physical_address) if physical_address else "[Physical mailing address required]"
    unsub = (f'<a href="{htmlmod.escape(unsubscribe_url, quote=True)}" style="color:#6e6e73">Unsubscribe</a>'
             if unsubscribe_url else "Unsubscribe link added at send time")
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f5f5f7;font-family:-apple-system,Segoe UI,Helvetica,Arial,'
        'sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" '
        'style="padding:24px 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;background:#ffffff;border-radius:14px"><tr><td style="padding:28px;'
        f'font-size:15px;line-height:1.55;color:#1d1d1f">{body_html}</td></tr></table>'
        '<p style="max-width:600px;font-size:12px;color:#6e6e73;line-height:1.5;padding:12px">'
        f"{addr}<br>{unsub}</p></td></tr></table></body></html>"
    )


def text_footer(text: str, unsubscribe_url: str | None, physical_address: str | None) -> str:
    addr = physical_address or "[Physical mailing address required]"
    return f"{text}\n\n--\n{addr}\nUnsubscribe: {unsubscribe_url or '(link added at send time)'}"


def personalize(text: str, lead: Lead | None) -> str:
    """Optional local-LLM polish via Ollama (OLLAMA_BASE_URL; legacy OLLAMA_URL).
    Falls back to the template text on any problem."""
    url = env("OLLAMA_BASE_URL") or env("OLLAMA_URL")
    if not url or lead is None:
        return text
    prompt = ("Rewrite this short business email opening to sound natural for "
              f"{lead.business_name}. Keep it under 60 words, no claims, plain text only:\n\n{text}")
    try:
        with http_client() as c:
            r = c.post(f"{url.rstrip('/')}/api/generate",
                       json={"model": env("OLLAMA_MODEL") or "llama3.1", "prompt": prompt, "stream": False})
            r.raise_for_status()
            out = (r.json().get("response") or "").strip()
            return out or text
    except Exception:  # noqa: BLE001 - personalization is best effort
        return text


# ------------------------------------------------------------------ suppression
def suppress(db: Session, org_id: uuid.UUID, channel: str, value: str | None, reason: str,
             source: str | None = None) -> bool:
    if not value:
        return False
    value = value.strip().lower() if channel == "email" else re.sub(r"\D", "", value)
    exists = db.scalar(select(CommunicationSuppression).where(
        CommunicationSuppression.organization_id == org_id, CommunicationSuppression.channel == channel,
        CommunicationSuppression.value == value))
    if exists:
        return False
    db.add(CommunicationSuppression(organization_id=org_id, channel=channel, value=value, reason=reason,
                                    source=source))
    _mirror_to_compliance(db, org_id, channel, value, reason)
    db.flush()
    return True


def _mirror_to_compliance(db: Session, org_id: uuid.UUID, channel: str, value: str, reason: str) -> None:
    """Keep the compliance module's central suppression list in sync (its gate check reads it too)."""
    try:
        from app.modules.compliance.models import SuppressionRecord
    except ModuleNotFoundError:
        return
    db.add(SuppressionRecord(organization_id=org_id, channel=channel, reason=f"communication:{reason}",
                             email_normalized=value if channel == "email" else None,
                             phone_normalized=value if channel != "email" else None))


def is_opt_out(text: str | None) -> bool:
    t = (text or "").strip().lower().strip(".!")
    return t in OPT_OUT_KEYWORDS


# ------------------------------------------------------------------ unsubscribe tokens
def new_unsubscribe_token(db: Session, org_id: uuid.UUID, address: str, lead_id=None, campaign_id=None,
                          channel: str = "email") -> str:
    # The org id prefix lets the public endpoint bind the tenant (RLS) before the lookup; a forged prefix
    # simply finds no row because only the hash of the full token is stored.
    token = f"{org_id.hex}.{secrets.token_urlsafe(24)}"
    db.add(UnsubscribeToken(organization_id=org_id, token_hash=hash_token(token), lead_id=lead_id,
                            channel=channel, address=address, campaign_id=campaign_id))
    return token


def unsubscribe_url(token: str) -> str:
    return f"{public_base_url()}/api/v1/public/unsubscribe/{token}"


# ------------------------------------------------------------------ routes (public id -> org)
def set_route(db: Session, kind: str, external_id: str, org_id: uuid.UUID) -> None:
    ext = external_id.strip().lower()
    row = db.scalar(select(CommunicationRoute).where(CommunicationRoute.kind == kind,
                                                     CommunicationRoute.external_id == ext))
    if row is not None and row.organization_id != org_id:
        raise AppError(409, "already_connected", "This identifier is connected to another workspace")
    if row is None:
        db.add(CommunicationRoute(kind=kind, external_id=ext, organization_id=org_id))
        try:
            db.flush()
        except IntegrityError as e:
            raise AppError(409, "already_connected", "This identifier is connected to another workspace") from e


def route_org(db: Session, kind: str, external_id: str | None) -> uuid.UUID | None:
    if not external_id:
        return None
    return db.scalar(select(CommunicationRoute.organization_id).where(
        CommunicationRoute.kind == kind, CommunicationRoute.external_id == external_id.strip().lower()))


# ------------------------------------------------------------------ email providers
def provider_configured(account: EmailAccount | None) -> tuple[bool, str | None]:
    if account is None:
        return False, "no_email_account"
    if account.provider == "smtp":
        return (True, None) if env("SMTP_HOST") else (False, "smtp_not_configured")
    if account.status != "connected" or not account.credentials_enc:
        return False, f"{account.provider}_not_connected"
    keys = {"gmail": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"), "outlook": ("MS_CLIENT_ID", "MS_CLIENT_SECRET")}
    if not all(env(k) for k in keys.get(account.provider, ("_missing_",))):
        return False, f"{account.provider}_oauth_not_configured"
    return True, None


def _mime(account: EmailAccount, to: str, subject: str, html: str, text: str, unsub: str | None) -> MimeMessage:
    m = MimeMessage()
    m["From"] = f"{account.display_name} <{account.address}>" if account.display_name else account.address
    m["To"] = to
    m["Subject"] = subject
    m["Message-ID"] = make_msgid(domain=account.address.split("@")[-1])
    if unsub:
        m["List-Unsubscribe"] = f"<{unsub}>"
        m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    m.set_content(text)
    m.add_alternative(html, subtype="html")
    return m


def _access_token(db: Session, account: EmailAccount) -> str:
    creds = unseal(account.credentials_enc, account.credentials_encrypted)
    exp = account.token_expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=utcnow().tzinfo)
    if exp is not None and exp > utcnow() + timedelta(seconds=60):
        return creds["access_token"]
    if not creds.get("refresh_token"):
        return creds.get("access_token", "")
    cfg = OAUTH[account.provider]
    with http_client() as c:
        r = c.post(cfg["token_url"](), data={
            "client_id": env(cfg["id"]), "client_secret": env(cfg["secret"]), "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"]})
    if r.status_code != 200:
        account.status, account.last_error = "error", f"token_refresh_failed:{r.status_code}"
        raise RuntimeError("token refresh failed")
    tok = r.json()
    creds["access_token"] = tok["access_token"]
    creds["refresh_token"] = tok.get("refresh_token", creds["refresh_token"])
    account.credentials_enc, account.credentials_encrypted = seal(creds)
    account.token_expires_at = utcnow() + timedelta(seconds=int(tok.get("expires_in", 3600)))
    return creds["access_token"]


def provider_send(db: Session, account: EmailAccount, to: str, subject: str, html: str, text: str,
                  unsub: str | None) -> str:
    """Perform the real send. Returns provider message id. Raises on failure."""
    mime = _mime(account, to, subject, html, text, unsub)
    if account.provider == "smtp":
        host, port = env("SMTP_HOST"), int(env("SMTP_PORT") or 587)
        with smtplib.SMTP(host, port, timeout=20) as s:
            if (env("SMTP_STARTTLS") or "true").lower() != "false":
                s.starttls()
            if smtp_user():
                s.login(smtp_user(), env("SMTP_PASSWORD") or "")
            s.send_message(mime)
        return mime["Message-ID"]
    token = _access_token(db, account)
    headers = {"Authorization": f"Bearer {token}"}
    with http_client() as c:
        if account.provider == "gmail":
            import base64

            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            r = c.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", headers=headers,
                       json={"raw": raw})
            r.raise_for_status()
            return r.json().get("id") or mime["Message-ID"]
        r = c.post("https://graph.microsoft.com/v1.0/me/sendMail", headers=headers, json={
            "message": {"subject": subject, "body": {"contentType": "HTML", "content": html},
                        "toRecipients": [{"emailAddress": {"address": to}}],
                        "internetMessageHeaders": [{"name": "X-Leadex-Id", "value": mime["Message-ID"]}]},
            "saveToSentItems": True})
        r.raise_for_status()  # Graph returns 202 with no id
        return mime["Message-ID"]


@dataclass
class SendResult:
    status: str
    reasons: list[str] = field(default_factory=list)
    message_id: uuid.UUID | None = None


def send_email(db: Session, *, org_id: uuid.UUID, lead: Lead, account: EmailAccount | None, subject: str,
               body_html: str, body_text: str, physical_address: str | None, campaign_id=None,
               step_index: int | None = None, decision: GateDecision | None = None) -> SendResult:
    decision = decision or check_outreach(db, org_id, lead.id, "email")
    to = lead.email_normalized
    token = new_unsubscribe_token(db, org_id, to or "", lead.id, campaign_id) if to else None
    unsub = unsubscribe_url(token) if token else None
    html = wrap_responsive(sanitize_html(body_html), unsubscribe_url=unsub, physical_address=physical_address)
    text = text_footer(body_text, unsub, physical_address)
    msg = EmailMessage(organization_id=org_id, campaign_id=campaign_id, lead_id=lead.id,
                       account_id=account.id if account else None, direction="outbound", step_index=step_index,
                       from_address=account.address if account else None, to_address=to, subject=subject,
                       html=html, text=text, gate_reasons=list(decision.reasons))
    if not decision.allowed:
        msg.status = "blocked"
    elif decision.simulated:
        msg.status, msg.gate_reasons = "simulated", ["outbound_simulated_environment"]
    else:
        ok, why = provider_configured(account)
        if not ok:
            msg.status, msg.gate_reasons = "simulated", [why]
        else:
            try:
                msg.provider_message_id = provider_send(db, account, to, subject, html, text, unsub)
                msg.status = "sent"
            except Exception as e:  # noqa: BLE001
                log.warning("email send failed: %s", type(e).__name__)
                msg.status, msg.error = "failed", f"{type(e).__name__}"[:500]
    db.add(msg)
    db.flush()
    return SendResult(msg.status, list(msg.gate_reasons or []), msg.id)


# ------------------------------------------------------------------ OAuth (Gmail / Microsoft Graph)
def _ms_tenant() -> str:
    return env("MS_TENANT_ID") or "common"


OAUTH = {
    "gmail": {
        "id": "GOOGLE_CLIENT_ID", "secret": "GOOGLE_CLIENT_SECRET",
        "auth_url": lambda: "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": lambda: "https://oauth2.googleapis.com/token",
        "scope": "openid email https://www.googleapis.com/auth/gmail.send",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "outlook": {
        "id": "MS_CLIENT_ID", "secret": "MS_CLIENT_SECRET",
        "auth_url": lambda: f"https://login.microsoftonline.com/{_ms_tenant()}/oauth2/v2.0/authorize",
        "token_url": lambda: f"https://login.microsoftonline.com/{_ms_tenant()}/oauth2/v2.0/token",
        "scope": "offline_access openid email User.Read Mail.Send",
        "extra": {},
    },
}


def oauth_configured(provider: str) -> bool:
    cfg = OAUTH.get(provider)
    return bool(cfg and env(cfg["id"]) and env(cfg["secret"]))


def oauth_redirect_uri(provider: str) -> str:
    return f"{public_base_url()}/api/v1/oauth/email/{provider}/callback"


def fetch_mailbox_address(provider: str, access_token: str) -> str | None:
    h = {"Authorization": f"Bearer {access_token}"}
    with http_client() as c:
        if provider == "gmail":
            r = c.get("https://gmail.googleapis.com/gmail/v1/users/me/profile", headers=h)
            return r.json().get("emailAddress") if r.status_code == 200 else None
        r = c.get("https://graph.microsoft.com/v1.0/me", headers=h)
        if r.status_code != 200:
            return None
        j = r.json()
        return j.get("mail") or j.get("userPrincipalName")


# ------------------------------------------------------------------ WhatsApp Cloud API
def wa_configured() -> tuple[bool, str | None]:
    return (True, None) if env("WA_ACCESS_TOKEN") else (False, "whatsapp_not_configured")


def verify_wa_signature(body: bytes, header: str | None) -> bool:
    secret = env("WA_APP_SECRET")
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def wa_provider_send(phone_number_id: str, to: str, payload: dict) -> str:
    with http_client() as c:
        r = c.post(f"{WA_GRAPH}/{phone_number_id}/messages",
                   headers={"Authorization": f"Bearer {env('WA_ACCESS_TOKEN')}"},
                   json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **payload})
    r.raise_for_status()
    return r.json()["messages"][0]["id"]


def get_conversation(db: Session, org_id: uuid.UUID, phone: str, account: WhatsAppAccount | None = None,
                     lead: Lead | None = None) -> WhatsAppConversation:
    digits = re.sub(r"\D", "", phone)
    conv = db.scalar(select(WhatsAppConversation).where(WhatsAppConversation.organization_id == org_id,
                                                        WhatsAppConversation.contact_phone == digits))
    if conv is None:
        if lead is None:
            lead = db.scalar(select(Lead).where(Lead.organization_id == org_id, Lead.phone_normalized == digits,
                                                Lead.deleted_at.is_(None)).limit(1))
        conv = WhatsAppConversation(organization_id=org_id, contact_phone=digits,
                                    account_id=account.id if account else None,
                                    lead_id=lead.id if lead else None)
        db.add(conv)
        db.flush()
    return conv


def send_whatsapp(db: Session, *, org_id: uuid.UUID, conv: WhatsAppConversation, account: WhatsAppAccount | None,
                  text: str | None = None, template: WhatsAppTemplate | None = None,
                  variables: list[str] | None = None, campaign_id=None,
                  decision: GateDecision | None = None) -> WhatsAppMessage:
    """Free-form text is only allowed inside the 24h customer-service window; otherwise an APPROVED template."""
    reasons: list[str] = []
    if conv.lead_id is None:
        decision = decision or GateDecision(False, True, ["no_linked_lead"])
    else:
        decision = decision or check_outreach(db, org_id, conv.lead_id, "whatsapp")
    reasons.extend(decision.reasons)
    if conv.opted_out:
        reasons.append("contact_opted_out")
    if template is not None:
        if template.status != "approved":
            reasons.append(f"template_not_approved:{template.status}")
        body = render(template.body, {str(i + 1): v for i, v in enumerate(variables or [])}, escape=False)
    else:
        last = conv.last_inbound_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=utcnow().tzinfo)
        if last is None or utcnow() - last > timedelta(hours=24):
            reasons.append("outside_24h_window_template_required")
        body = text or ""
    msg = WhatsAppMessage(organization_id=org_id, conversation_id=conv.id, campaign_id=campaign_id,
                          lead_id=conv.lead_id, template_id=template.id if template else None, direction="outbound",
                          body=body, gate_reasons=reasons)
    if reasons:
        msg.status = "blocked"
    elif decision.simulated:
        msg.status, msg.gate_reasons = "simulated", ["outbound_simulated_environment"]
    else:
        ok, why = wa_configured()
        if not ok or account is None:
            msg.status, msg.gate_reasons = "simulated", [why or "no_whatsapp_account"]
        else:
            if template is not None:
                payload = {"type": "template", "template": {
                    "name": template.name, "language": {"code": template.language},
                    "components": [{"type": "body", "parameters": [{"type": "text", "text": v}
                                                                   for v in (variables or [])]}] if variables else []}}
            else:
                payload = {"type": "text", "text": {"preview_url": False, "body": body}}
            try:
                msg.provider_message_id = wa_provider_send(account.phone_number_id, conv.contact_phone, payload)
                msg.status = "sent"
            except Exception as e:  # noqa: BLE001
                msg.status, msg.error = "failed", type(e).__name__
    conv.last_message_at = utcnow()
    db.add(msg)
    db.flush()
    return msg
