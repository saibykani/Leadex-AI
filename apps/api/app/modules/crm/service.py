"""CRM domain rules: lead lifecycle, duplicate detection, activity timeline."""

import re
import uuid
from urllib.parse import urlsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.crm.models import Lead, LeadActivity
from app.modules.identity.models import OrganizationMembership

STATUSES: tuple[str, ...] = (
    "discovered", "unverified", "verified", "pending_consent", "approved_for_outreach", "contacted",
    "interested", "qualified", "meeting_scheduled", "proposal_sent", "negotiation", "converted", "lost",
    "callback_requested", "not_interested", "do_not_contact", "suppressed",
)
TERMINAL = frozenset({"do_not_contact", "suppressed"})
CONSENT_REQUIRED = frozenset({"approved_for_outreach"})
ADMIN_ROLES = frozenset({"Owner", "Admin"})

_T: dict[str, set[str]] = {
    "discovered": {"unverified", "verified", "lost"},
    "unverified": {"verified", "lost"},
    "verified": {"pending_consent", "approved_for_outreach", "lost"},
    "pending_consent": {"approved_for_outreach", "not_interested", "lost"},
    "approved_for_outreach": {"contacted", "lost"},
    "contacted": {"interested", "callback_requested", "not_interested", "qualified", "lost"},
    "callback_requested": {"contacted", "interested", "not_interested", "lost"},
    "interested": {"qualified", "meeting_scheduled", "not_interested", "lost"},
    "qualified": {"meeting_scheduled", "proposal_sent", "not_interested", "lost"},
    "meeting_scheduled": {"qualified", "proposal_sent", "not_interested", "lost"},
    "proposal_sent": {"negotiation", "converted", "lost"},
    "negotiation": {"proposal_sent", "converted", "lost"},
    "converted": set(),
    "lost": {"verified"},
    "not_interested": {"callback_requested", "lost"},
    "do_not_contact": set(),
    "suppressed": set(),
}
# Any non-terminal lead may always be opted out / suppressed.
TRANSITIONS: dict[str, frozenset[str]] = {
    s: frozenset(nxt | (set() if s in TERMINAL else TERMINAL - {s})) for s, nxt in _T.items()
}


def normalize_email(v: str | None) -> str | None:
    return v.strip().lower() if v and v.strip() else None


def normalize_phone(v: str | None) -> str | None:
    if not v:
        return None
    digits = re.sub(r"\D", "", v)
    return digits or None


def website_domain(v: str | None) -> str | None:
    if not v or not v.strip():
        return None
    s = v.strip().lower()
    host = urlsplit(s if "://" in s else f"http://{s}").hostname or ""
    host = host.removeprefix("www.")
    return host or None


def apply_contact_fields(lead: Lead) -> None:
    lead.email_normalized = normalize_email(lead.email)
    lead.phone_normalized = normalize_phone(lead.phone)
    lead.website_domain = website_domain(lead.website)


def check_duplicates(db: Session, lead: Lead) -> None:
    conds = []
    if lead.email_normalized:
        conds.append(Lead.email_normalized == lead.email_normalized)
    if lead.phone_normalized:
        conds.append(Lead.phone_normalized == lead.phone_normalized)
    if lead.website_domain:
        conds.append(Lead.website_domain == lead.website_domain)
    if not conds:
        return
    q = select(Lead).where(Lead.organization_id == lead.organization_id, Lead.deleted_at.is_(None), or_(*conds))
    if lead.id is not None:
        q = q.where(Lead.id != lead.id)
    dup = db.scalars(q.limit(1)).first()
    if dup is not None:
        fields = [f for f, a, b in (
            ("email", dup.email_normalized, lead.email_normalized),
            ("phone", dup.phone_normalized, lead.phone_normalized),
            ("website", dup.website_domain, lead.website_domain),
        ) if b and a == b]
        raise AppError(409, "duplicate_lead", "A lead with the same contact data already exists",
                       {"existing_lead_id": str(dup.id), "fields": fields})


def ensure_member(db: Session, org_id: uuid.UUID, user_id: uuid.UUID | None, field: str) -> None:
    if user_id is None:
        return
    m = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "active",
    ))
    if m is None:
        raise AppError(422, "invalid_user", f"{field} must be an active member of this organization")


def get_lead(db: Session, ctx: TenantContext, lead_id: uuid.UUID) -> Lead:
    lead = db.scalar(select(Lead).where(
        Lead.id == lead_id, Lead.organization_id == ctx.organization_id, Lead.deleted_at.is_(None)
    ))
    if lead is None:
        raise AppError(404, "not_found", "Lead not found")
    return lead


def record_activity(db: Session, ctx: TenantContext, lead: Lead, type_: str, data: dict | None = None) -> None:
    db.add(LeadActivity(organization_id=ctx.organization_id, lead_id=lead.id, actor_user_id=ctx.user.id,
                        type=type_, data=data))


def change_status(
    ctx: TenantContext, lead: Lead, new: str, consent_reference: str | None, reason: str | None,
    admin_override: bool,
) -> dict:
    old = lead.status
    if new not in TRANSITIONS:
        raise AppError(422, "invalid_status", f"Unknown status '{new}'", {"allowed": list(STATUSES)})
    if new == old:
        raise AppError(409, "status_unchanged", f"Lead is already '{old}'")
    consent = (consent_reference or "").strip() or None
    if new in CONSENT_REQUIRED and not consent:
        raise AppError(422, "consent_required",
                       "A consent_reference documenting the recorded consent is required for this status")
    overridden = False
    if new not in TRANSITIONS.get(old, frozenset()):
        if not admin_override:
            raise AppError(409, "invalid_transition", f"Cannot move lead from '{old}' to '{new}'",
                           {"from": old, "to": new, "allowed": sorted(TRANSITIONS.get(old, ()))})
        if ctx.role_name not in ADMIN_ROLES:
            raise AppError(403, "forbidden", "Only Owners and Admins may override the status lifecycle")
        if not (reason or "").strip():
            raise AppError(422, "reason_required", "A reason is required for an admin status override")
        overridden = True
    lead.status = new
    if consent:
        lead.consent_reference = consent
    data = {"from": old, "to": new}
    if consent:
        data["consent_reference"] = consent
    if reason:
        data["reason"] = reason
    if overridden:
        data["admin_override"] = True
    return data
