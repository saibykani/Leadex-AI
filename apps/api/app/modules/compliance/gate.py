"""OutreachGate — the ONLY path by which any module may trigger an external side effect toward a person/business
(voice call, email, WhatsApp, SMS). Contract (stable; other modules depend on it):

    decision = check_outreach(db, organization_id, lead_id, channel, country_code=None)
    if not decision.allowed: raise / record block with decision.reasons
    decision.simulated -> True means the adapter MUST NOT contact anyone for real.

Default is BLOCK whenever eligibility is uncertain. The compliance module extends `_EXTRA_CHECKS`
(suppression lists, kill switches, jurisdiction profiles, calling windows, consent records).
"""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings

CHANNELS = {"voice", "email", "whatsapp", "sms"}


@dataclass
class GateDecision:
    allowed: bool
    simulated: bool
    reasons: list[str] = field(default_factory=list)


# Each check returns a list of blocking reasons (empty list = pass).
ExtraCheck = Callable[[Session, uuid.UUID, object, str, str | None], list[str]]
_EXTRA_CHECKS: list[ExtraCheck] = []


def register_check(fn: ExtraCheck) -> ExtraCheck:
    _EXTRA_CHECKS.append(fn)
    return fn


def check_outreach(
    db: Session, organization_id: uuid.UUID, lead_id: uuid.UUID, channel: str, country_code: str | None = None
) -> GateDecision:
    from app.modules.crm.models import Lead

    reasons: list[str] = []
    if channel not in CHANNELS:
        return GateDecision(False, True, [f"unknown_channel:{channel}"])
    lead = db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id or getattr(lead, "deleted_at", None):
        return GateDecision(False, True, ["lead_not_found"])
    if lead.status != "approved_for_outreach" and lead.status not in {"contacted", "interested", "qualified",
                                                                       "meeting_scheduled", "proposal_sent",
                                                                       "negotiation", "callback_requested"}:
        reasons.append(f"lead_status_not_eligible:{lead.status}")
    if not getattr(lead, "consent_reference", None):
        reasons.append("no_consent_reference")
    country = country_code or getattr(lead, "country", None)
    if not country:
        reasons.append("jurisdiction_unknown")
    for check in _EXTRA_CHECKS:
        reasons.extend(check(db, organization_id, lead, channel, country))
    return GateDecision(allowed=not reasons, simulated=get_settings().outbound_simulated, reasons=reasons)
