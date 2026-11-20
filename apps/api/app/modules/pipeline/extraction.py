"""Structured conversation outcome extraction.

Two modes, always labelled:
  * `llm`   - Ollama /api/chat with `format: "json"`. Every budget/timeline/decision-maker value must be backed by
              an evidence quote that actually appears in what the PROSPECT said; otherwise it is dropped (null).
  * `rules` - deterministic regex/keyword extractor over the prospect's lines. Used when Ollama is not configured
              or fails, or when explicitly requested.

Budget is never inferred or invented: it is set only when the prospect stated an amount.
"""
import json
import re
from dataclasses import asdict, dataclass, field

import httpx

from app.modules.agents.config import ai_settings, http_client

INTEREST = ("high", "medium", "low", "none", "unknown")
PROSPECT_ROLES = ("user", "contact", "prospect", "customer")


@dataclass
class Outcome:
    interest: str = "unknown"
    budget_min: float | None = None
    budget_max: float | None = None
    budget_currency: str | None = None
    budget_evidence: str | None = None
    timeline: str | None = None
    timeline_evidence: str | None = None
    decision_maker: str | None = None
    decision_maker_evidence: str | None = None
    objections: list[dict] = field(default_factory=list)  # [{objection, evidence}]
    next_step: str | None = None
    summary: str = ""
    extraction_mode: str = "rules"
    model: str | None = None
    warnings: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def prospect_lines(transcript: list[dict]) -> list[str]:
    out = []
    for t in transcript:
        text = str(t.get("text") or "").strip()
        if text and str(t.get("role") or t.get("speaker") or "").lower() in PROSPECT_ROLES:
            out.append(text)
    return out


# ------------------------------------------------------------------ rules
_CUR = {"$": "USD", "usd": "USD", "dollars": "USD", "dollar": "USD", "₹": "INR", "rs": "INR", "rs.": "INR",
        "inr": "INR", "rupees": "INR", "rupee": "INR", "€": "EUR", "eur": "EUR", "euros": "EUR", "£": "GBP",
        "gbp": "GBP", "pounds": "GBP", "aed": "AED", "dirhams": "AED"}
_MULT = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "m": 1_000_000,
         "million": 1_000_000, "crore": 10_000_000}
_CUR_RE = r"(\$|₹|€|£|\brs\.?|\binr|\busd|\beur|\bgbp|\baed)"
_NUM = (rf"{_CUR_RE}?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lac|m|million|crore)?\b\s*"
        r"(dollars?|rupees?|euros?|pounds|dirhams|usd|inr|eur|gbp|aed)?")
_AMOUNT = re.compile(_NUM, re.I)
_BUDGET_CTX = re.compile(r"\b(budget|spend|afford|pay|paying|invest|price|cost|around|between|max(imum)?|up to|"
                         r"under|at most|at least|minimum)\b", re.I)
_RANGE = re.compile(rf"{_NUM}\s*(?:-|–|to|and)\s*{_NUM}", re.I)
_UPPER = re.compile(r"\b(up to|under|below|at most|max(imum)?|no more than|less than)\b", re.I)
_LOWER = re.compile(r"\b(at least|minimum|more than|over)\b", re.I)

_TIMELINE = re.compile(r"\b(asap|as soon as possible|immediately|right away|this (week|month|quarter|year)|"
                       r"next (week|month|quarter|year)|in (a|one|two|three|four|six|\d+) (days?|weeks?|months?)|"
                       r"within (a|one|two|three|\d+) (days?|weeks?|months?)|by (january|february|march|april|may|"
                       r"june|july|august|september|october|november|december|the end of \w+)|"
                       r"(before|after) (diwali|christmas|the holidays|new year))\b", re.I)
_DM_SELF = re.compile(r"\b(i('m| am) the (owner|founder|director|decision[- ]maker|proprietor|ceo|md)|"
                      r"i (make|take) (the|all the) decisions?|i decide|it'?s my (call|decision)|i own)\b", re.I)
_DM_OTHER = re.compile(r"\b(my|our) (partner|boss|manager|owner|wife|husband|brother|father|son|director|"
                       r"accountant|team)\b[^.?!]{0,40}\b(decides?|decision|approve|handles?|discuss|ask|check)\b|"
                       r"\b(discuss|check|talk) (it )?with (my|our) (partner|boss|manager|owner|wife|husband|"
                       r"brother|father|son|director|accountant|team)\b", re.I)
_OBJECTIONS = [
    ("price", re.compile(r"\b(too expensive|too costly|can'?t afford|out of (my|our) budget|cheaper|costly)\b", re.I)),
    ("already_has_website", re.compile(r"\b(already (have|got) a (website|site)|we have a (website|site))\b", re.I)),
    ("no_time", re.compile(r"\b(no time|too busy|busy right now|not a good time)\b", re.I)),
    ("not_needed", re.compile(r"\b(don'?t need|do not need|no need|get enough customers)\b", re.I)),
    ("needs_to_think", re.compile(r"\b(think about it|need to think|not sure|let me think)\b", re.I)),
    ("trust", re.compile(r"\b(scam|is this real|how do i know|trust)\b", re.I)),
]
_NONE = re.compile(r"\b(not interested|no thanks|no thank you|stop calling|don'?t call|do not call|remove (me|my)|"
                   r"never call)\b", re.I)
_HIGH = re.compile(r"\b(very interested|sounds (great|good)|let'?s do it|let'?s go ahead|go ahead|sign me up|"
                   r"send (me )?(the |a )?(proposal|quote|details)|book (a|the) (meeting|call)|when can you start|"
                   r"i'?m interested|we'?re interested|yes,? please)\b", re.I)
_LOW = re.compile(r"\b(maybe later|not now|not right now|maybe next year|call (me )?(back )?later|not sure)\b", re.I)
_NEXT = [
    ("Send proposal / quote", re.compile(r"\b(send|email|share) (me )?(the |a )?(proposal|quote|quotation|details|"
                                         r"pricing|options)\b", re.I)),
    ("Schedule a meeting", re.compile(r"\b(meeting|meet|demo|appointment)\b", re.I)),
    ("Call back later", re.compile(r"\b(call (me )?back|call later|call me (next|tomorrow|on))\b", re.I)),
    ("Do not contact again", _NONE),
]


def _amount(m: tuple) -> tuple[float, str | None] | None:
    cur1, num, mult, cur2 = m
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    if mult:
        v *= _MULT.get(mult.lower(), 1)
    cur = _CUR.get((cur1 or "").lower()) or _CUR.get((cur2 or "").lower())
    return v, cur


def rules_extract(transcript: list[dict]) -> Outcome:
    lines = prospect_lines(transcript)
    o = Outcome(extraction_mode="rules")
    if not lines:
        o.summary = "No prospect speech in the transcript; nothing to extract."
        o.warnings.append("no_prospect_speech")
        return o
    # budget: only from a sentence that names a currency or talks about budget/spend.
    for line in lines:
        for sent in re.split(r"(?<=[.?!])\s+", line):
            has_cur = re.search(_CUR_RE + r"|\b(dollars?|rupees?|euros?|pounds|dirhams)\b", sent, re.I)
            if not (has_cur or _BUDGET_CTX.search(sent)):
                continue
            rm = _RANGE.search(sent)
            if rm:
                g = rm.groups()
                a, b = _amount(g[0:4]), _amount(g[4:8])
                if a and b:
                    cur = a[1] or b[1]
                    if cur or _BUDGET_CTX.search(sent):
                        o.budget_min, o.budget_max = min(a[0], b[0]), max(a[0], b[0])
                        o.budget_currency, o.budget_evidence = cur, sent
                        break
            amounts = [x for x in (_amount(m) for m in _AMOUNT.findall(sent)) if x and x[0] >= 10]
            if amounts and (has_cur or _BUDGET_CTX.search(sent)):
                v, cur = amounts[0]
                if _UPPER.search(sent):
                    o.budget_max = v
                elif _LOWER.search(sent):
                    o.budget_min = v
                else:
                    o.budget_min = o.budget_max = v
                o.budget_currency, o.budget_evidence = cur, sent
                break
        if o.budget_evidence:
            break
    for line in lines:
        m = _TIMELINE.search(line)
        if m and not o.timeline:
            o.timeline, o.timeline_evidence = m.group(0), line
        if not o.decision_maker:
            if _DM_SELF.search(line):
                o.decision_maker, o.decision_maker_evidence = "prospect (self)", line
            else:
                dm = _DM_OTHER.search(line)
                if dm:
                    who = re.search(r"\b(partner|boss|manager|owner|wife|husband|brother|father|son|director|"
                                    r"accountant|team)\b", dm.group(0), re.I)
                    o.decision_maker = f"someone else ({who.group(0).lower() if who else 'unspecified'})"
                    o.decision_maker_evidence = line
        for key, rx in _OBJECTIONS:
            if rx.search(line) and key not in {x["objection"] for x in o.objections}:
                o.objections.append({"objection": key, "evidence": line})
    text = " ".join(lines)
    if _NONE.search(text):
        o.interest = "none"
    elif _HIGH.search(text):
        o.interest = "high"
    elif _LOW.search(text) or any(x["objection"] in ("price", "not_needed") for x in o.objections):
        o.interest = "low"
    else:
        o.interest = "medium" if len(lines) >= 2 or o.budget_evidence or o.timeline else "unknown"
    for label, rx in _NEXT:
        if rx.search(lines[-1]) or rx.search(text):
            o.next_step = label
            break
    o.summary = _summary(o, len(lines))
    return o


def _money(o: Outcome) -> str:
    cur = o.budget_currency or ""
    if o.budget_min is not None and o.budget_max is not None and o.budget_min != o.budget_max:
        return f"{cur} {o.budget_min:,.0f}–{o.budget_max:,.0f}".strip()
    if o.budget_min is not None and o.budget_max is not None:
        return f"{cur} {o.budget_min:,.0f}".strip()
    if o.budget_max is not None:
        return f"up to {cur} {o.budget_max:,.0f}".replace("  ", " ")
    if o.budget_min is not None:
        return f"at least {cur} {o.budget_min:,.0f}".replace("  ", " ")
    return "not stated"


def _summary(o: Outcome, n: int) -> str:
    parts = [f"Interest: {o.interest}.", f"Budget: {_money(o)}."]
    parts.append(f"Timeline: {o.timeline or 'not stated'}.")
    if o.decision_maker:
        parts.append(f"Decision maker: {o.decision_maker}.")
    if o.objections:
        parts.append("Objections: " + ", ".join(x["objection"] for x in o.objections) + ".")
    parts.append(f"Next step: {o.next_step or 'none agreed'}.")
    parts.append(f"({n} prospect utterance{'s' if n != 1 else ''}; rule-based extraction)" if o.extraction_mode ==
                 "rules" else "")
    return " ".join(p for p in parts if p)


# ------------------------------------------------------------------ LLM (Ollama JSON mode)
SYSTEM = """You extract facts from a sales conversation transcript about a website offer.
Return ONLY a JSON object with keys:
interest ("high"|"medium"|"low"|"none"|"unknown"), budget_min (number|null), budget_max (number|null),
budget_currency (ISO 4217 code|null), budget_evidence (exact quote from the PROSPECT|null),
timeline (string|null), timeline_evidence (exact quote|null), decision_maker (string|null),
decision_maker_evidence (exact quote|null), objections (list of {"objection": string, "evidence": exact quote}),
next_step (string|null), summary (2 sentences).
Rules: use ONLY what the PROSPECT said. If the prospect did not state a budget amount, budget fields MUST be null.
Never guess prices. Evidence must be copied verbatim from the prospect's lines."""


class LLMExtractionFailed(Exception):
    pass


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w₹$€£.,\s-]", "", (s or "").lower())).strip()


def _quoted(evidence, lines_norm: str) -> bool:
    e = _norm(str(evidence or ""))
    return bool(e) and len(e) >= 3 and e in lines_norm


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def llm_extract(transcript: list[dict], model: str | None = None) -> Outcome:
    s = ai_settings()
    if not s.ollama_base_url:
        raise LLMExtractionFailed("OLLAMA_BASE_URL is not configured")
    lines = prospect_lines(transcript)
    if not lines:
        raise LLMExtractionFailed("no prospect speech")
    model = model or s.ollama_chat_model
    convo = "\n".join(f"{'PROSPECT' if str(t.get('role') or t.get('speaker')).lower() in PROSPECT_ROLES else 'AGENT'}:"
                      f" {t.get('text')}" for t in transcript if t.get("text"))
    payload = {"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": f"Transcript:\n{convo[:12000]}"}]}
    try:
        with http_client(timeout=60) as c:
            r = c.post(f"{s.ollama_base_url}/api/chat", json=payload)
        if r.status_code != 200:
            raise LLMExtractionFailed(f"Ollama HTTP {r.status_code}")
        data = json.loads((r.json().get("message") or {}).get("content") or "")
    except (httpx.HTTPError, ValueError) as e:
        raise LLMExtractionFailed(type(e).__name__) from e
    if not isinstance(data, dict):
        raise LLMExtractionFailed("model did not return a JSON object")
    ln = _norm(" ".join(lines))
    o = Outcome(extraction_mode="llm", model=model)
    o.interest = data.get("interest") if data.get("interest") in INTEREST else "unknown"
    if _quoted(data.get("budget_evidence"), ln):
        o.budget_min, o.budget_max = _num(data.get("budget_min")), _num(data.get("budget_max"))
        cur = str(data.get("budget_currency") or "").upper()[:3]
        o.budget_currency = cur if re.fullmatch(r"[A-Z]{3}", cur) else None
        o.budget_evidence = str(data["budget_evidence"])[:500] if (o.budget_min or o.budget_max) else None
        if not o.budget_evidence:
            o.budget_min = o.budget_max = o.budget_currency = None
    elif data.get("budget_min") is not None or data.get("budget_max") is not None:
        o.warnings.append("budget_dropped_no_verbatim_evidence")
    for k in ("timeline", "decision_maker"):
        if data.get(k) and _quoted(data.get(f"{k}_evidence"), ln):
            setattr(o, k, str(data[k])[:200])
            setattr(o, f"{k}_evidence", str(data[f"{k}_evidence"])[:500])
    for ob in data.get("objections") or []:
        if isinstance(ob, dict) and ob.get("objection") and _quoted(ob.get("evidence"), ln):
            o.objections.append({"objection": str(ob["objection"])[:120], "evidence": str(ob["evidence"])[:500]})
    o.next_step = str(data["next_step"])[:300] if data.get("next_step") else None
    o.summary = str(data.get("summary") or "")[:2000] or _summary(o, len(lines))
    return o


def extract(transcript: list[dict], mode: str = "auto", model: str | None = None) -> Outcome:
    """mode: auto (LLM if available, else rules) | llm | rules."""
    if mode == "rules":
        return rules_extract(transcript)
    try:
        o = llm_extract(transcript, model)
    except LLMExtractionFailed as e:
        o = rules_extract(transcript)
        o.warnings.append(f"llm_unavailable: {e}")
        return o
    # Small models often paraphrase instead of quoting, so their fields fail the verbatim-evidence check.
    # Backfill those fields from the rule extractor, which only reads amounts/dates the prospect literally said.
    r = rules_extract(transcript)
    backfilled = []
    if o.budget_min is None and o.budget_max is None and (r.budget_min is not None or r.budget_max is not None):
        o.budget_min, o.budget_max, o.budget_currency, o.budget_evidence = (
            r.budget_min, r.budget_max, r.budget_currency, r.budget_evidence)
        backfilled.append("budget")
    for k in ("timeline", "decision_maker"):
        if not getattr(o, k) and getattr(r, k):
            setattr(o, k, getattr(r, k))
            setattr(o, f"{k}_evidence", getattr(r, f"{k}_evidence"))
            backfilled.append(k)
    if backfilled:
        o.warnings.append("backfilled_by_rules: " + ",".join(backfilled))
    return o
