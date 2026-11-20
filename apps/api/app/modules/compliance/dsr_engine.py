"""Data subject request execution: export (access/portability) and erasure.

Subjects are matched by the request's lead_id and/or normalized email/phone within ONE organization (RLS applies).

Erasure keeps only what the law allows or requires us to keep:
* a suppression record (phone/email) so the person is never contacted again,
* consent/withdrawal records (proof of lawful basis), with their free-text evidence redacted,
* billing usage and the append-only audit log (legal/security obligations; they hold no conversation content).
Conversation content (transcripts, messages, notes, outcomes, activities' payloads) is deleted or redacted.
Append-only tables are cleared through the narrow SECURITY DEFINER function privacy_erase_lead() (migration 0023).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from app.core.db import utcnow

REDACTED = "[erased]"


def _row(obj) -> dict:
    out = {}
    for c in inspect(obj).mapper.column_attrs:
        v = getattr(obj, c.key)
        if isinstance(v, uuid.UUID):
            v = str(v)
        elif isinstance(v, datetime | date):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = str(v)
        out[c.key] = v
    return out


def find_leads(db: Session, org: uuid.UUID, dsr) -> list:
    from app.modules.crm.models import Lead
    from app.modules.crm.service import normalize_phone

    conds = []
    if dsr.lead_id:
        conds.append(Lead.id == dsr.lead_id)
    if dsr.subject_email:
        conds.append(Lead.email_normalized == dsr.subject_email.strip().lower())
    if dsr.subject_phone and normalize_phone(dsr.subject_phone):
        p = normalize_phone(dsr.subject_phone)
        conds.append(or_(Lead.phone_normalized == p, Lead.phone_normalized.endswith(p[-10:])))
    if not conds:
        return []
    return list(db.scalars(select(Lead).where(Lead.organization_id == org, or_(*conds))))


def _children(db: Session, org: uuid.UUID, lead_id: uuid.UUID) -> dict[str, list]:
    from app.modules.campaigns.models import CampaignRecipient
    from app.modules.communication.models import EmailMessage, WhatsAppConversation, WhatsAppMessage
    from app.modules.compliance.models import CommunicationPreference, ConsentRecord
    from app.modules.crm.models import LeadActivity, LeadContact, LeadNote, LeadTask
    from app.modules.pipeline.models import ConversationOutcome
    from app.modules.voice.models import CallSession, CallSummary, CallTranscript

    def q(model, *extra):
        return list(db.scalars(select(model).where(model.organization_id == org, *extra)))

    calls = q(CallSession, CallSession.lead_id == lead_id)
    call_ids = [c.id for c in calls]
    convs = q(WhatsAppConversation, WhatsAppConversation.lead_id == lead_id)
    return {
        "contacts": q(LeadContact, LeadContact.lead_id == lead_id),
        "notes": q(LeadNote, LeadNote.lead_id == lead_id),
        "tasks": q(LeadTask, LeadTask.lead_id == lead_id),
        "activities": q(LeadActivity, LeadActivity.lead_id == lead_id),
        "consents": q(ConsentRecord, ConsentRecord.lead_id == lead_id),
        "preferences": q(CommunicationPreference, CommunicationPreference.lead_id == lead_id),
        "calls": calls,
        "call_transcripts": q(CallTranscript, CallTranscript.call_id.in_(call_ids)) if call_ids else [],
        "call_summaries": q(CallSummary, CallSummary.call_id.in_(call_ids)) if call_ids else [],
        "conversation_outcomes": q(ConversationOutcome, ConversationOutcome.lead_id == lead_id),
        "email_messages": q(EmailMessage, EmailMessage.lead_id == lead_id),
        "whatsapp_conversations": convs,
        "whatsapp_messages": q(WhatsAppMessage, WhatsAppMessage.conversation_id.in_([c.id for c in convs]))
        if convs else [],
        "campaign_recipients": q(CampaignRecipient, CampaignRecipient.lead_id == lead_id),
    }


def export_bundle(db: Session, org: uuid.UUID, dsr) -> dict:
    leads = find_leads(db, org, dsr)
    return {
        "request_id": str(dsr.id), "generated_at": utcnow().isoformat(), "organization_id": str(org),
        "subject": {"email": dsr.subject_email, "phone": dsr.subject_phone, "lead_id": str(dsr.lead_id or "")},
        "records": [{"lead": _row(lead), **{k: [_row(x) for x in v] for k, v in _children(db, org, lead.id).items()}}
                    for lead in leads],
        "note": "All personal data held about the subject in this workspace at the time of export.",
    }


def erase(db: Session, org: uuid.UUID, dsr, actor_id: uuid.UUID | None) -> dict:
    from app.modules.compliance.models import SuppressionRecord

    leads = find_leads(db, org, dsr)
    counts: dict[str, int] = {}
    for lead in leads:
        kids = _children(db, org, lead.id)
        # 1. never contact again (kept on legal basis: honoring the objection)
        db.add(SuppressionRecord(organization_id=org, channel="all", phone_normalized=lead.phone_normalized,
                                 email_normalized=lead.email_normalized,
                                 reason=f"Erasure request {dsr.id}: do not contact", created_by_user_id=actor_id))
        # 2. delete content-bearing rows
        for key in ("contacts", "notes", "tasks", "call_summaries", "conversation_outcomes", "preferences"):
            for obj in kids[key]:
                db.delete(obj)
            counts[key] = len(kids[key])
        for m in kids["email_messages"]:
            m.subject, m.html, m.text, m.to_address, m.from_address = REDACTED, None, None, None, None
        for m in kids["whatsapp_messages"]:
            if hasattr(m, "body"):
                m.body = None
        for cv in kids["whatsapp_conversations"]:
            cv.contact_phone, cv.contact_name = REDACTED, None
        for c in kids["consents"]:
            if hasattr(c, "evidence_text"):
                c.evidence_text = REDACTED
        for call in kids["calls"]:
            call.to_number = None
        counts["email_messages_redacted"] = len(kids["email_messages"])
        counts["whatsapp_messages_redacted"] = len(kids["whatsapp_messages"])
        # 3. append-only tables (transcripts, call events, lead activities) via the audited definer function
        db.flush()
        if db.bind.dialect.name == "postgresql":
            counts["append_only_rows"] = int(db.scalar(text("SELECT privacy_erase_lead(:l)"), {"l": lead.id}) or 0)
        else:  # SQLite test databases have no privilege separation
            for key in ("call_transcripts", "activities"):
                for obj in kids[key]:
                    db.delete(obj)
            counts["append_only_rows"] = len(kids["call_transcripts"]) + len(kids["activities"])
        # 4. the lead itself: identifying fields removed, row soft-deleted (keeps foreign keys valid)
        lead.business_name, lead.phone, lead.email, lead.website = REDACTED, None, None, None
        lead.phone_normalized = lead.email_normalized = lead.website_domain = None
        lead.custom_fields, lead.consent_reference, lead.city = None, None, None
        lead.deleted_at = lead.deleted_at or utcnow()
    return {"leads_erased": len(leads), **counts}
