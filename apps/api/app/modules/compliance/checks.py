"""OutreachGate extensions. Imported by compliance/router.py so they register at app start-up.

Each check returns blocking reasons; an empty list means pass. All checks fail closed.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.compliance.gate import register_check
from app.modules.compliance.jurisdictions import DEFAULT_PROFILES, jurisdiction_code
from app.modules.compliance.models import (
    CommunicationPreference,
    ConsentRecord,
    JurisdictionProfile,
    KillSwitch,
    SuppressionRecord,
)


def now() -> datetime:  # indirection so tests can pin the clock
    return utcnow()


def load_profile(db: Session, country: str | None) -> tuple[str | None, dict | None]:
    code = jurisdiction_code(country)
    if code is None:
        return None, None
    row = db.scalar(select(JurisdictionProfile).where(JurisdictionProfile.code == code))
    if row is not None:
        return code, row.rules
    fallback = DEFAULT_PROFILES.get(code)
    return code, (fallback["rules"] if fallback else None)


@register_check
def organization_active(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    from app.modules.identity.models import Organization

    org = db.get(Organization, org_id)
    return [] if org is not None and org.status == "active" else ["organization_suspended"]


@register_check
def kill_switches(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    rows = db.scalars(
        select(KillSwitch).where(
            KillSwitch.active.is_(True),
            or_(KillSwitch.organization_id.is_(None), KillSwitch.organization_id == org_id),
            KillSwitch.channel.in_([channel, "all"]),
        )
    ).all()
    return sorted({f"kill_switch_active:{r.scope}:{r.channel}" for r in rows})


@register_check
def suppression(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    conds = []
    if lead.email_normalized:
        conds.append(SuppressionRecord.email_normalized == lead.email_normalized)
    if lead.phone_normalized:
        conds.append(SuppressionRecord.phone_normalized == lead.phone_normalized)
    if not conds:
        return []
    hit = db.scalar(
        select(SuppressionRecord.id).where(
            SuppressionRecord.organization_id == org_id,
            SuppressionRecord.channel.in_([channel, "all"]),
            or_(*conds),
        ).limit(1)
    )
    return ["suppressed_contact"] if hit else []


@register_check
def preferences(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    pref = db.scalar(
        select(CommunicationPreference).where(
            CommunicationPreference.organization_id == org_id,
            CommunicationPreference.lead_id == lead.id,
            CommunicationPreference.channel == channel,
        )
    )
    return ["channel_opted_out"] if pref is not None and not pref.allowed else []


@register_check
def consent(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    _, rules = load_profile(db, country)
    required = True if rules is None else rules.get(channel, {}).get("requires_consent", True)
    if not required:
        return []
    records = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.organization_id == org_id,
            ConsentRecord.lead_id == lead.id,
            ConsentRecord.channel == channel,
        )
    ).all()
    if not records:
        return [f"no_consent_record:{channel}"]
    if all(r.withdrawn_at is not None for r in records):
        return [f"consent_withdrawn:{channel}"]
    return []


@register_check
def jurisdiction(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    if not country:
        return []  # the core gate already reports jurisdiction_unknown
    code, rules = load_profile(db, country)
    return [] if rules else [f"jurisdiction_profile_missing:{code}"]


def within_window(rules: dict, channel: str, at: datetime) -> tuple[bool, str | None]:
    chan = rules.get(channel) or {}
    window = chan.get("calling_window")
    if not window:
        return True, None
    offsets = rules.get("utc_offsets") or []
    if not offsets:
        return False, "calling_window_timezone_unknown"
    start, end = window
    for off in offsets:
        local = at + timedelta(hours=off)
        hour = local.hour + local.minute / 60
        if not (start <= hour < end):
            return False, "outside_calling_window"
    return True, None


@register_check
def calling_window(db: Session, org_id: uuid.UUID, lead, channel: str, country: str | None) -> list[str]:
    if channel not in {"voice", "sms"} or not country:
        return []
    _, rules = load_profile(db, country)
    if not rules:
        return []  # reported by the jurisdiction check
    ok, reason = within_window(rules, channel, now())
    return [] if ok else [reason]
