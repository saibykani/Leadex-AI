"""System (transactional) email: password reset, verification, invitations.

Outside production nothing is sent: the message is logged and reported as simulated, and callers may
return the action link to the client so flows can be tested locally. In production SMTP must be configured.
"""
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger("leadex.mailer")


@dataclass
class MailResult:
    status: str  # sent | simulated | not_configured | failed
    simulated: bool


def _env(name: str, *fallbacks: str) -> str:
    for n in (name, *fallbacks):
        v = os.getenv(n)
        if v:
            return v
    return ""


def web_url(path: str) -> str:
    base = (_env("WEB_APP_URL") or "http://localhost:3010").rstrip("/")
    return f"{base}{path}"


def send_system_email(to: str, subject: str, body: str) -> MailResult:
    if get_settings().outbound_simulated:
        log.info("SIMULATED system email to=%s subject=%s", to, subject)
        return MailResult("simulated", True)
    host = _env("SMTP_HOST")
    if not host:
        log.error("System email not sent: SMTP_HOST is not configured")
        return MailResult("not_configured", False)
    msg = EmailMessage()
    msg["From"] = _env("SMTP_FROM", "SMTP_USER", "SMTP_USERNAME") or "no-reply@localhost"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(_env("SMTP_PORT") or 587), timeout=15) as s:
            if (_env("SMTP_STARTTLS") or "true").lower() != "false":
                s.starttls()
            user = _env("SMTP_USER", "SMTP_USERNAME")
            if user:
                s.login(user, _env("SMTP_PASSWORD"))
            s.send_message(msg)
        return MailResult("sent", False)
    except Exception as e:  # noqa: BLE001 - delivery failure must not crash the request
        log.error("System email failed: %s", type(e).__name__)
        return MailResult("failed", False)
