"""Public Twilio webhooks (no auth; mounted via voice.router.extra_routers under /api/v1).

Every request: rate limit -> resolve tenant from the call session id (SECURITY DEFINER `telephony_call_org` on
PostgreSQL, migration 0015) -> work inside `tenant_session(org)` -> validate X-Twilio-Signature with that org's auth
token over PUBLIC_WEBHOOK_BASE_URL + path + sorted POST params (invalid => 403). Only sessions dialled through Twilio
resolve, so simulated sessions and other tenants' data are unreachable.

  POST /telephony/twilio/voice/{id}   first TwiML: AI disclosure + greeting, then <Gather input="speech">
  POST /telephony/twilio/turn/{id}    one conversational turn (opt-out, escalation, LLM reply with an 8 s budget)
  POST /telephony/twilio/status/{id}  status callback: duration, billing, outcome extraction
"""
import logging
import math
import re
import time
import uuid
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from xml.sax.saxutils import escape, quoteattr

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, tenant_session, utcnow
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.modules.voice import telephony
from app.modules.voice.models import CallEvent, CallSession, CallSummary, CallTranscript

log = logging.getLogger(__name__)
public_router = APIRouter(tags=["telephony-webhooks"])

TERMINAL = {"completed", "busy", "no_answer", "failed", "canceled"}
STATUS_MAP = {"queued": "initiated", "initiated": "initiated", "ringing": "ringing", "in-progress": "in_progress",
              "answered": "in_progress", "completed": "completed", "busy": "busy", "no-answer": "no_answer",
              "failed": "failed", "canceled": "canceled"}
OPT_OUT = re.compile(r"\b(stop|don'?t call|do not call|not interested|remove me|remove my (number|name)|"
                     r"unsubscribe|take me off)\b", re.I)
HUMAN = re.compile(r"\b(human|person|representative|someone real|real people)\b", re.I)
FALLBACK = ("Sorry, I'm having trouble answering that right now. A member of our team can call you back with the "
            "details. Would that be okay?")
VOICE_RULES = ("This is a LIVE PHONE CALL. Reply in at most two short spoken sentences, no lists, no markdown, no "
               "citations. Never state a price, discount or figure unless it appears verbatim in the knowledge or "
               "business information above; otherwise say a specialist will confirm pricing. Ask one question at a "
               "time. Never claim to be human.")
_PRICE = re.compile(r"(₹|\$|€|£|\brs\.?\s*|\binr\s*|\busd\s*)\s*\d[\d,]*(\.\d+)?|\d[\d,]*(\.\d+)?\s*"
                    r"(rupees|dollars|lakhs?|crore|k\b)", re.I)


# ------------------------------------------------------------------ helpers
def _xml(*verbs: str) -> Response:
    body = '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(verbs) + "</Response>"
    return Response(content=body, media_type="application/xml")


_AGENT_VOICE: ContextVar[str | None] = ContextVar("agent_voice", default=None)  # set per webhook request


def _say(textv: str, lang: str) -> str:
    voice = telephony.say_voice(lang, _AGENT_VOICE.get())
    v = f" voice={quoteattr(voice)}" if voice else ""
    return f"<Say{v} language={quoteattr(lang)}>{escape(textv)}</Say>"


def _gather(call_id: uuid.UUID, lang: str, prompt: str | None = None) -> str:
    inner = _say(prompt, lang) if prompt else ""
    return (f'<Gather input="speech" speechTimeout="auto" method="POST" language={quoteattr(lang)} '
            f"action={quoteattr(telephony.webhook_url('turn', call_id))}>{inner}</Gather>")


def _no_input(lang: str) -> str:
    return _say("I didn't hear anything, so I'll let you go. Thank you for your time. Goodbye.", lang) + "<Hangup/>"


def _resolve_org(call_id: uuid.UUID) -> uuid.UUID | None:
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            return db.scalar(text("SELECT telephony_call_org(:a)"), {"a": str(call_id)})
        return db.scalar(select(CallSession.organization_id).where(CallSession.id == call_id,
                                                                   CallSession.provider == "twilio"))


async def _params(request: Request) -> list[tuple[str, str]]:
    form = await request.form()
    return [(k, str(v)) for k, v in form.multi_items()]


def _public_url(request: Request) -> str:
    base = telephony.telephony_settings().public_base or ""
    q = request.url.query
    return f"{base}{request.url.path}" + (f"?{q}" if q else "")


class _Ctx:
    """Minimal context for module services called outside a user request (acts as the call's initiator)."""

    def __init__(self, org_id: uuid.UUID, user_id: uuid.UUID | None):
        self.organization_id = org_id
        self.user = SimpleNamespace(id=user_id)
        self.role_name = "system"
        self.permissions: set[str] = set()


def _open(request: Request, call_id: uuid.UUID) -> uuid.UUID:
    ip = request.client.host if request.client else "unknown"
    if not limiter.hit(f"twilio:{ip}", 600):
        raise AppError(429, "rate_limited", "Too many requests")
    org = _resolve_org(call_id)
    if org is None:
        raise AppError(404, "not_found", "Not found")
    return org


def _load(db: Session, org: uuid.UUID, call_id: uuid.UUID, request: Request, params) -> tuple[CallSession, object]:
    call = db.scalar(select(CallSession).where(CallSession.id == call_id, CallSession.organization_id == org,
                                               CallSession.provider == "twilio"))
    if call is None:
        raise AppError(404, "not_found", "Not found")
    creds = telephony.load_twilio_creds(db, org)
    if creds is None or not telephony.valid_signature(creds.auth_token, _public_url(request), params,
                                                      request.headers.get("X-Twilio-Signature")):
        raise AppError(403, "invalid_signature", "Invalid Twilio signature")
    return call, creds


def _event(db: Session, call: CallSession, type_: str, data: dict | None = None) -> None:
    db.add(CallEvent(organization_id=call.organization_id, call_id=call.id, type=type_, data=data))


def _turns(db: Session, call: CallSession) -> list[CallTranscript]:
    return list(db.scalars(select(CallTranscript).where(CallTranscript.call_id == call.id,
                                                        CallTranscript.organization_id == call.organization_id)
                           .order_by(CallTranscript.seq)))


def _append(db: Session, call: CallSession, speaker: str, textv: str) -> None:
    seq = db.scalar(select(func.max(CallTranscript.seq)).where(CallTranscript.call_id == call.id,
                                                               CallTranscript.organization_id ==
                                                               call.organization_id))
    db.add(CallTranscript(organization_id=call.organization_id, call_id=call.id, seq=(seq if seq is not None
                                                                                       else -1) + 1,
                          speaker=speaker, text=textv[:4000], simulated=False))
    db.flush()


def _context(db: Session, call: CallSession):
    from app.modules.agents.models import AIAgent
    from app.modules.crm.models import Lead
    from app.modules.identity.models import Organization

    agent = db.get(AIAgent, call.agent_id)
    lead = db.get(Lead, call.lead_id)
    org = db.get(Organization, call.organization_id)
    lang = telephony.say_language(call.language, lead.country if lead else None)
    return agent, lead, org, lang


def disclosure_text(agent, org_name: str) -> str:
    d = (agent.compliance_disclosure or "").strip()
    mentions_ai = re.search(r"\b(AI|A\.I\.|artificial intelligence)\b", d, re.I)
    mentions_org = org_name and org_name.lower() in d.lower()
    if not (mentions_ai and mentions_org):
        d = f"This is an AI assistant calling on behalf of {org_name}. {d}".strip()
    return d


# ------------------------------------------------------------------ voice (first turn)
@public_router.post("/telephony/twilio/voice/{call_id}")
async def twilio_voice(call_id: uuid.UUID, request: Request):
    params = await _params(request)
    org = _open(request, call_id)
    with tenant_session(org) as db:
        call, _ = _load(db, org, call_id, request, params)
        agent, lead, o, lang = _context(db, call)
        _AGENT_VOICE.set(agent.voice)
        if params and dict(params).get("AnsweredBy", "").startswith("machine"):
            _event(db, call, "call.machine_detected", {"answered_by": dict(params).get("AnsweredBy")})
            db.commit()
            return _xml("<Hangup/>")
        from app.modules.learning import service as learning

        variant = learning.start_call(db, call)  # Thompson-sampled opening, if the agent has variants
        greeting = variant.opening if variant else (agent.greeting or "")
        opening = f"{disclosure_text(agent, o.name if o else 'our company')} {greeting.strip()}".strip()
        if not _turns(db, call):
            _append(db, call, "agent", opening)
        call.status = "in_progress"
        call.started_at = call.started_at or utcnow()
        _event(db, call, "call.answered", {})
        db.commit()
        return _xml(_gather(call.id, lang, opening), _no_input(lang))


# ------------------------------------------------------------------ turn
def _opt_out(db: Session, call: CallSession, lead, said: str) -> None:
    from app.modules.compliance.models import ConsentRecord, SuppressionRecord
    from app.modules.crm.models import LeadNote

    now = utcnow()
    if lead is not None:
        db.add(SuppressionRecord(organization_id=call.organization_id, channel="all",
                                 phone_normalized=lead.phone_normalized, email_normalized=lead.email_normalized,
                                 reason=f"Opted out during call {call.id}: \"{said[:300]}\"",
                                 created_by_user_id=call.initiated_by_user_id))
        for c in db.scalars(select(ConsentRecord).where(ConsentRecord.organization_id == call.organization_id,
                                                        ConsentRecord.lead_id == lead.id,
                                                        ConsentRecord.withdrawn_at.is_(None))):
            c.withdrawn_at, c.withdrawn_reason = now, f"do_not_contact: opted out on call {call.id}"
        db.add(LeadNote(organization_id=call.organization_id, lead_id=lead.id,
                        author_user_id=call.initiated_by_user_id,
                        body=f"DO NOT CONTACT - the contact opted out during an AI call: \"{said[:300]}\". "
                             "Added to the suppression list and consent withdrawn."))
    _event(db, call, "contact.opted_out", {"utterance": said[:300]})


def _clean_reply(reply: str, allowed_text: str) -> str:
    r = re.sub(r"\s*\[\d+\]", "", reply or "")
    r = re.sub(r"[*_#`>]", "", r)
    r = re.sub(r"\s+", " ", r).strip()
    sentences = re.split(r"(?<=[.!?])\s+", r)
    r = " ".join(sentences[:2]).strip()[:400]
    for m in _PRICE.finditer(r):
        if m.group(0).strip().lower() not in allowed_text.lower():
            return "A specialist will confirm exact pricing with you. Would a quick follow-up call work for you?"
    return r


def _generate(db: Session, call: CallSession, agent, history: list[CallTranscript]) -> tuple[str, str | None]:
    """Returns (reply, error). Never raises; errors => safe fallback text."""
    from app.modules.agents import service as agents_svc
    from app.modules.agents.config import timeout_budget
    from app.modules.agents.orchestrator import build_turn_graph
    from app.modules.agents.tools import ToolEnv

    budget = telephony.telephony_settings().telephony_llm_budget_s
    spec = agents_svc.model_spec(db, agent, None)
    from app.modules.agents.llm import fast_spec

    fast = fast_spec(spec.temperature if spec.provider != "simulated" else 0.4, 160)
    if fast is not None:  # live calls prefer the fast endpoint when one is configured
        spec = fast
    elif spec.provider == "simulated":  # template text must never be read to a real person
        spec = agents_svc.model_spec(db, agent, "ollama")
    msgs = [{"role": "assistant" if t.speaker == "agent" else "user", "content": t.text}
            for t in history if t.speaker in ("agent", "contact")]
    ctx = _Ctx(call.organization_id, call.initiated_by_user_id)
    from app.modules.learning import service as learning

    examples = learning.examples_prompt(learning.winning_examples(db, call.organization_id, call.agent_id))
    extra = f"{VOICE_RULES}\n\n{examples}" if examples else VOICE_RULES
    token = timeout_budget.set(budget)
    t0 = time.perf_counter()
    try:
        state = build_turn_graph().run({
            "agent": agent, "env": ToolEnv(db, ctx, agent, dry_run=True), "spec": spec, "messages": msgs,
            "use_knowledge": True, "requested_tools": [], "tool_calls": [], "logs": [], "extra_system": extra})
    except Exception as e:  # noqa: BLE001 - a live call must always get an answer
        log.exception("voice turn generation failed")
        return FALLBACK, f"exception:{type(e).__name__}"
    finally:
        timeout_budget.reset(token)
    if time.perf_counter() - t0 > budget:
        return FALLBACK, "llm_budget_exceeded"
    if state.get("error") or not (state.get("reply") or "").strip():
        return FALLBACK, state.get("error") or "empty_reply"
    allowed = (agent.business_info or "") + " " + " ".join(c.get("text", "") for c in state.get("citations", []))
    return _clean_reply(state["reply"], allowed) or FALLBACK, None


@public_router.post("/telephony/twilio/turn/{call_id}")
async def twilio_turn(call_id: uuid.UUID, request: Request):
    params = await _params(request)
    org = _open(request, call_id)
    with tenant_session(org) as db:
        call, creds = _load(db, org, call_id, request, params)
        agent, lead, _o, lang = _context(db, call)
        _AGENT_VOICE.set(agent.voice)
        said = (dict(params).get("SpeechResult") or "").strip()
        if call.status in TERMINAL:
            return _xml("<Hangup/>")
        if not said:
            db.commit()
            return _xml(_gather(call.id, lang, "Sorry, I didn't catch that. Could you say that again?"),
                        _no_input(lang))
        _append(db, call, "contact", said)
        if OPT_OUT.search(said):
            _opt_out(db, call, lead, said)
            bye = ("Understood. I've removed your number and we will not contact you again. "
                   "Sorry for the interruption. Goodbye.")
            _append(db, call, "agent", bye)
            db.commit()
            return _xml(_say(bye, lang), "<Hangup/>")
        if HUMAN.search(said):
            if creds.escalation_number:
                msg = "Of course. I'm connecting you to a member of our team now. Please hold."
                _append(db, call, "agent", msg)
                _event(db, call, "call.escalated", {"to": "dial"})
                db.commit()
                return _xml(_say(msg, lang), f"<Dial>{escape(creds.escalation_number)}</Dial>")
            msg = ("Of course. No one is available right now, so I'll ask a team member to call you back. "
                   "Is there anything you'd like me to pass on?")
            _append(db, call, "agent", msg)
            _event(db, call, "call.escalated", {"to": "callback_message",
                                                "policy": (agent.escalation_policy or "")[:300]})
            db.commit()
            return _xml(_gather(call.id, lang, msg), _no_input(lang))
        history = _turns(db, call)
        agent_turns = sum(1 for t in history if t.speaker == "agent")
        elapsed = (utcnow() - _aware(call.started_at)).total_seconds() if call.started_at else 0
        if agent_turns >= telephony.telephony_settings().telephony_max_turns or elapsed >= (agent.max_call_seconds
                                                                                             or 300):
            bye = "Thank you for your time today. A member of our team will follow up with you. Goodbye."
            _append(db, call, "agent", bye)
            _event(db, call, "call.limit_reached", {"agent_turns": agent_turns, "elapsed_s": int(elapsed)})
            db.commit()
            return _xml(_say(bye, lang), "<Hangup/>")
        reply, err = _generate(db, call, agent, history)
        if err:
            _event(db, call, "agent.fallback", {"error": str(err)[:300]})
        _append(db, call, "agent", reply)
        db.commit()
        return _xml(_gather(call.id, lang, reply), _no_input(lang))


def _aware(dt):
    from datetime import UTC

    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


# ------------------------------------------------------------------ status callback
def _finalize(db: Session, call: CallSession) -> None:
    from app.modules.billing import service as billing
    from app.modules.crm.models import Lead
    from app.modules.pipeline import extraction
    from app.modules.pipeline import service as pipeline

    minutes = math.ceil((call.duration_s or 0) / 60) if call.status == "completed" else 0
    try:
        billing.record_usage(db, call.organization_id, "voice_minutes", minutes, call.price or 0,
                             lead_id=call.lead_id, meta={"call_id": str(call.id), "simulated": False,
                                                         "status": call.status, "provider": "twilio",
                                                         "provider_call_id": call.provider_call_id,
                                                         "duration_s": call.duration_s})
    except AppError as e:  # e.g. budget hard stop reached after the fact: record it, never lose the callback
        _event(db, call, "billing.error", {"code": e.code, "message": e.message})
    from app.modules.learning import service as learning

    turns = [{"speaker": t.speaker, "text": t.text} for t in _turns(db, call)]
    opted_out = db.scalar(select(CallEvent.id).where(CallEvent.organization_id == call.organization_id,
                                                     CallEvent.call_id == call.id,
                                                     CallEvent.type == "contact.opted_out")) is not None
    talked = call.status == "completed" and any(t["speaker"] == "contact" for t in turns)
    o = extraction.extract(turns, "auto") if talked else None
    learning.record_outcome(db, call, interest=o.interest if o else None, next_step=o.next_step if o else None,
                            opted_out=opted_out, had_conversation=talked)
    if o is not None:
        lead = db.get(Lead, call.lead_id)
        pipeline.save_outcome(db, _Ctx(call.organization_id, call.initiated_by_user_id), o, transcript=turns,
                              source="call", lead=lead, agent_id=call.agent_id, call_id=call.id, simulated=False)
    else:
        db.add(CallSummary(organization_id=call.organization_id, call_id=call.id, simulated=False,
                           summary=f"Call ended with status '{call.status}'; no conversation to analyse."))
    call.finalized_at = utcnow()


@public_router.post("/telephony/twilio/status/{call_id}")
async def twilio_status(call_id: uuid.UUID, request: Request):
    params = await _params(request)
    org = _open(request, call_id)
    with tenant_session(org) as db:
        call, _ = _load(db, org, call_id, request, params)
        p = dict(params)
        raw = p.get("CallStatus", "")
        new = STATUS_MAP.get(raw)
        _event(db, call, "provider.status", {k: p.get(k) for k in ("CallStatus", "CallDuration", "ErrorCode",
                                                                     "ErrorMessage", "AnsweredBy") if p.get(k)})
        if call.finalized_at is not None or new is None:  # idempotent: Twilio retries / late events
            db.commit()
            return Response(status_code=204)
        if p.get("CallSid") and not call.provider_call_id:
            call.provider_call_id = p["CallSid"][:64]
        call.status = new
        if new in TERMINAL:
            try:
                call.duration_s = int(p.get("CallDuration") or 0)
            except ValueError:
                call.duration_s = 0
            if p.get("Price"):
                try:
                    call.price = abs(Decimal(p["Price"]))
                    call.price_unit = (p.get("PriceUnit") or "")[:8] or None
                except InvalidOperation:
                    pass
            if p.get("ErrorMessage") or p.get("ErrorCode"):
                call.error_message = f"Twilio error {p.get('ErrorCode', '')}: {p.get('ErrorMessage', '')}".strip()
            call.ended_at = utcnow()
            _finalize(db, call)
        db.commit()
        return Response(status_code=204)
