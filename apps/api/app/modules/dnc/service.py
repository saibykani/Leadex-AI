"""National do-not-call registry checks (OutreachGate extension).

Applies to phone channels (voice, sms, whatsapp) for countries with a national registry (REGISTRY_COUNTRIES).
Sources, in order:
  1. A registry API, if DNC_API_URL is configured (generic contract: GET {url}?country=IN&phone=+91...,
     Bearer DNC_API_KEY, JSON {"listed": bool}). Any error => block ("dnc_registry_unavailable").
  2. The organization's own imported registry file, if one for that country is newer than DNC_MAX_AGE_DAYS.
  3. Otherwise the registry status is unknown. When enforcement is on (production by default, DNC_ENFORCE to
     override) the call is blocked ("dnc_registry_not_checked:<CC>"): uncertain eligibility => block.
Registry access itself requires the organization's own registration (TRAI telemarketer/DLT, FTC SAN, ...).
"""
import os
import uuid
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.modules.compliance.gate import register_check
from app.modules.dnc.models import DncEntry, DncImport

REGISTRY_COUNTRIES = {"IN": "TRAI NCPR", "US": "National DNC Registry", "GB": "TPS", "CA": "National DNCL",
                      "AU": "Do Not Call Register"}
PHONE_CHANNELS = {"voice", "sms", "whatsapp"}
http_transport: httpx.BaseTransport | None = None  # tests inject a MockTransport


def max_age_days() -> int:
    try:
        return int(os.getenv("DNC_MAX_AGE_DAYS") or 31)
    except ValueError:
        return 31


def enforced() -> bool:
    v = (os.getenv("DNC_ENFORCE") or "").strip().lower()
    if v in {"true", "1", "yes"}:
        return True
    if v in {"false", "0", "no"}:
        return False
    return get_settings().is_production


def e164(phone: str | None, country: str | None) -> str | None:
    from app.modules.voice.telephony import to_e164

    return to_e164(phone, country)


def latest_import(db: Session, org_id: uuid.UUID, country: str) -> DncImport | None:
    return db.scalar(select(DncImport).where(DncImport.organization_id == org_id, DncImport.country == country)
                     .order_by(DncImport.created_at.desc()).limit(1))


def _api_listed(country: str, number: str) -> bool | None:
    url = os.getenv("DNC_API_URL")
    if not url:
        return None
    key = os.getenv("DNC_API_KEY")
    try:
        with httpx.Client(transport=http_transport, timeout=5) as c:
            r = c.get(url, params={"country": country, "phone": number},
                      headers={"Authorization": f"Bearer {key}"} if key else {})
        if r.status_code != 200:
            raise ValueError(r.status_code)
        return bool(r.json()["listed"])
    except Exception:  # noqa: BLE001 - any failure is "unknown", which the caller turns into a block
        raise RuntimeError("dnc_api_error") from None


@register_check
def dnc_registry(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    cc = (country or "").upper()
    if channel not in PHONE_CHANNELS or cc not in REGISTRY_COUNTRIES:
        return []
    number = e164(getattr(lead, "phone", None), cc)
    if not number:
        return []  # no dialable number: other checks / the dialer reject it
    try:
        listed = _api_listed(cc, number)
    except RuntimeError:
        return ["dnc_registry_unavailable"]
    if listed is not None:
        return [f"dnc_registry_listed:{cc}"] if listed else []
    imp = latest_import(db, org_id, cc)
    created = imp.created_at if imp and imp.created_at.tzinfo else (imp.created_at.replace(tzinfo=utcnow().tzinfo)
                                                                      if imp else None)
    fresh = created is not None and utcnow() - created <= timedelta(days=max_age_days())
    if imp is not None:
        hit = db.scalar(select(DncEntry.id).where(DncEntry.organization_id == org_id, DncEntry.country == cc,
                                                  DncEntry.phone_e164 == number).limit(1))
        if hit:
            return [f"dnc_registry_listed:{cc}"]
    if not fresh and enforced():
        return [f"dnc_registry_not_checked:{cc}" if imp is None else f"dnc_registry_stale:{cc}"]
    return []
