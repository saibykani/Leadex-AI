"""Call placement. Order of checks: agent blockers (kill switches, publish state, language evaluation) +
compliance.OutreachGate. Any reason => persisted `blocked` session. Allowed calls go to the telephony adapter
(voice.telephony, Twilio today) ONLY when:
  * APP_ENV=production, or
  * ALLOW_TEST_CALLS=true and the lead's E.164 number is in TEST_CALL_ALLOWLIST (local testing on your own phone).
Otherwise:
  * non-production: status `simulated_completed`, simulated=True, no one is contacted and the transcript holds ONLY
    a labelled system note (no invented conversation);
  * real dialing intended but the adapter is not configured / has no public webhook URL: status `not_configured`.
Twilio REST errors (e.g. trial accounts calling unverified numbers) are stored verbatim in `error_message`.
"""
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.tenancy import TenantContext
from app.modules.agents import service as agents
from app.modules.agents.models import AIAgent
from app.modules.compliance.gate import check_outreach
from app.modules.crm.models import Lead
from app.modules.voice import telephony
from app.modules.voice.models import CallEvent, CallRecording, CallSession, CallSummary, CallTranscript
from app.modules.voice.schemas import CallCreate

SIM_NOTE = ("[SIMULATION] No telephony provider is configured and/or this is not a production environment. "
            "No call was placed and nobody was contacted. This session only records that the compliance gate "
            "allowed the call.")


def _event(db: Session, call: CallSession, type_: str, data: dict | None = None) -> None:
    db.add(CallEvent(organization_id=call.organization_id, call_id=call.id, type=type_, data=data))


def place_call(db: Session, ctx: TenantContext, body: CallCreate, agent: AIAgent, idem_key: str) -> CallSession:
    reasons = agents.live_call_blockers(db, ctx.organization_id, agent)
    decision = check_outreach(db, ctx.organization_id, body.lead_id, "voice")
    reasons += decision.reasons
    call = CallSession(organization_id=ctx.organization_id, lead_id=body.lead_id, agent_id=agent.id,
                       agent_version=agent.published_version, direction=body.direction, language=agent.language,
                       status="queued", simulated=True, provider="simulated", idempotency_key=idem_key,
                       initiated_by_user_id=ctx.user.id, gate_reasons=[])
    db.add(call)
    db.flush()
    _event(db, call, "call.requested", {"agent_version": agent.published_version})
    if reasons:
        call.status, call.gate_reasons = "blocked", reasons
        _event(db, call, "call.blocked", {"reasons": reasons})
        return call
    _event(db, call, "gate.allowed", {"simulated": decision.simulated})
    recording_on = bool(body.record and (body.recording_consent_reference or "").strip())
    db.add(CallRecording(organization_id=ctx.organization_id, call_id=call.id, enabled=recording_on,
                         consent_reference=body.recording_consent_reference))
    lead = db.get(Lead, body.lead_id)
    to = telephony.to_e164(lead.phone, lead.country) if lead else None
    mode = telephony.dial_mode(to)
    if mode != "simulated":
        return _dial(db, call, to, mode, recording_on)
    if not decision.simulated:  # defensive: production always dials above
        call.status, call.simulated, call.provider = "not_configured", False, "none"
        call.gate_reasons = ["telephony_not_configured"]
        return call
    now = utcnow()
    call.status, call.started_at, call.ended_at, call.duration_s = "simulated_completed", now, now, 0
    db.add(CallTranscript(organization_id=ctx.organization_id, call_id=call.id, seq=0, speaker="system",
                          text=SIM_NOTE, simulated=True))
    db.add(CallSummary(organization_id=ctx.organization_id, call_id=call.id, simulated=True,
                       summary="Simulated call: gate allowed; no conversation took place."))
    _event(db, call, "call.simulated_completed", {})
    return call


def _dial(db: Session, call: CallSession, to: str | None, mode: str, record: bool) -> CallSession:
    call.simulated, call.to_number = False, to
    if not to:
        call.status, call.provider, call.gate_reasons = "blocked", "none", ["invalid_phone_number"]
        _event(db, call, "call.blocked", {"reasons": call.gate_reasons})
        return call
    adapter = telephony.adapter_for(db, call.organization_id)
    st = adapter.status()
    if st.status != "configured":
        reason = "telephony_needs_public_url" if st.status == "needs_public_url" else "telephony_not_configured"
        call.status, call.provider, call.gate_reasons = "not_configured", "none", [reason]
        call.error_message = st.detail
        _event(db, call, "call.not_configured", {"adapter_status": st.status, "detail": st.detail})
        return call
    call.provider = adapter.name
    db.flush()  # the session id must exist before Twilio fetches the webhook URL
    res = adapter.place_call(call_id=call.id, to=to, record=record)
    if not res.ok:
        call.status, call.error_message, call.ended_at = "failed", res.error, utcnow()
        call.finalized_at = call.ended_at
        _event(db, call, "call.dial_failed", {"error": res.error, "mode": mode})
        return call
    call.status, call.provider_call_id, call.started_at = "initiated", res.provider_call_id, utcnow()
    _event(db, call, "call.dialed", {"provider": adapter.name, "provider_call_id": res.provider_call_id,
                                     "mode": mode, "credential_source": st.credential_source})
    return call
