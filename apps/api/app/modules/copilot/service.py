"""'Ask your pipeline' copilot.

Safety model:
- Only the read-only, tenant-scoped query functions in TOOLS can run. They take validated, typed arguments and
  never write. There is no SQL / free-form execution path.
- Tool selection: Ollama (JSON tool choice) when configured and reachable, else a deterministic rule parser.
- The answer TEXT is always composed from the tool result by code (the model never writes numbers), and every
  answer cites the rows / links it used.
"""
import json
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.campaigns.models import Campaign
from app.modules.crm.models import Lead
from app.modules.crm.service import STATUSES
from app.modules.discovery.models import Business
from app.modules.insights import service as ins
from app.modules.websites.models import WebsiteProject

MAX_ROWS = 25


@dataclass
class Result:
    answer: str
    tool: str | None
    args: dict
    rows: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    refused: bool = False


def _label(s: str) -> str:
    return s.replace("_", " ")


# ------------------------------------------------------------------ tools (read-only)
def _lead_query(org, status=None, city=None, industry=None):
    q = select(Lead).where(Lead.organization_id == org, Lead.deleted_at.is_(None))
    if status:
        q = q.where(Lead.status == status)
    if city:
        q = q.where(func.lower(Lead.city) == city.lower())
    if industry:
        q = q.where(func.lower(Lead.industry) == industry.lower())
    return q


def _lead_row(lead: Lead, extra: dict | None = None) -> dict:
    return {"type": "lead", "id": str(lead.id), "label": lead.business_name, "href": f"/leads/{lead.id}",
            "status": lead.status, "city": lead.city, "industry": lead.industry, **(extra or {})}


def _where(args: dict) -> str:
    bits = []
    if args.get("status"):
        bits.append(f"in stage “{_label(args['status'])}”")
    if args.get("industry"):
        bits.append(f"in {args['industry']}")
    if args.get("city"):
        bits.append(f"in {args['city']}")
    return (" " + " ".join(bits)) if bits else ""


def t_count_leads(db: Session, org, status=None, city=None, industry=None) -> Result:
    args = {"status": status, "city": city, "industry": industry}
    base = _lead_query(org, status, city, industry)
    n = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    sample = db.scalars(base.order_by(Lead.created_at.desc()).limit(8)).all()
    return Result(f"You have {n} lead{'s' if n != 1 else ''}{_where(args)}.", "count_leads", args,
                  [_lead_row(x) for x in sample],
                  [{"label": "Open leads list", "href": "/leads" + (f"?status={status}" if status else "")}])


def t_list_leads(db: Session, org, status=None, city=None, industry=None, interest=None, min_budget=None,
                 limit=10) -> Result:
    args = {k: v for k, v in {"status": status, "city": city, "industry": industry, "interest": interest,
                              "min_budget": min_budget, "limit": limit}.items() if v is not None}
    leads = db.scalars(_lead_query(org, status, city, industry).order_by(Lead.created_at.desc())).all()
    outs = ins.latest_outcomes(db, org) if (interest or min_budget is not None) else {}
    rows = []
    for lead in leads:
        extra = {}
        if interest or min_budget is not None:
            o = outs.get(lead.id)
            if o is None:
                continue
            if interest and o.interest != interest:
                continue
            bm = ins.budget_mid(o)
            if min_budget is not None and (bm is None or bm[0] < min_budget):
                continue
            extra = {"interest": o.interest}
            if bm:
                extra |= {"budget_mid": round(bm[0], 2), "currency": bm[1]}
        rows.append(_lead_row(lead, extra))
    total = len(rows)
    rows = rows[: max(1, min(limit, MAX_ROWS))]
    desc = []
    if interest:
        desc.append(f"with {interest} interest")
    if min_budget is not None:
        desc.append(f"with a stated budget of at least {min_budget:,.0f}")
    what = f"lead{'s' if total != 1 else ''}{_where(args)}{(' ' + ' and '.join(desc)) if desc else ''}"
    ans = f"Found {total} {what}." + (f" Showing the first {len(rows)}." if total > len(rows) else "")
    if total == 0:
        ans = f"No {what.replace('lead ', 'leads ', 1) if total != 1 else what} found."
    return Result(ans, "list_leads", args, rows, [{"label": "Leads", "href": "/leads"}])


def t_businesses(db: Session, org, city=None, industry=None, website_status=None) -> Result:
    args = {k: v for k, v in {"city": city, "industry": industry, "website_status": website_status}.items() if v}
    q = select(Business).where(Business.organization_id == org, Business.deleted_at.is_(None))
    if city:
        q = q.where(func.lower(Business.city) == city.lower())
    if industry:
        q = q.where(func.lower(Business.industry) == industry.lower())
    if website_status:
        q = q.where(Business.website_status == website_status)
    n = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    sample = db.scalars(q.order_by(Business.created_at.desc()).limit(8)).all()
    ws = f" with website status “{_label(website_status)}”" if website_status else ""
    loc = (f" in {industry}" if industry else "") + (f" in {city}" if city else "")
    return Result(f"{n} discovered business{'es' if n != 1 else ''}{loc}{ws}.", "count_businesses", args,
                  [{"type": "business", "id": str(b.id), "label": b.name or "(name purged)",
                    "href": f"/businesses/{b.id}", "city": b.city, "website_status": b.website_status}
                   for b in sample],
                  [{"label": "Businesses", "href": "/businesses"}])


def t_campaigns(db: Session, org, status=None) -> Result:
    q = select(Campaign).where(Campaign.organization_id == org)
    if status:
        q = q.where(Campaign.status == status)
    rows = db.scalars(q.order_by(Campaign.created_at.desc()).limit(MAX_ROWS)).all()
    n = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    return Result(f"{n} {status + ' ' if status else ''}campaign{'s' if n != 1 else ''}.", "campaigns",
                  {"status": status} if status else {},
                  [{"type": "campaign", "id": str(c.id), "label": c.name, "href": f"/campaigns/{c.id}",
                    "status": c.status, "channel": c.channel} for c in rows],
                  [{"label": "Campaigns", "href": "/campaigns"}])


def t_websites(db: Session, org, status=None) -> Result:
    q = select(WebsiteProject).where(WebsiteProject.organization_id == org)
    if status:
        q = q.where(WebsiteProject.status == status)
    rows = db.scalars(q.order_by(WebsiteProject.updated_at.desc()).limit(MAX_ROWS)).all()
    n = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    return Result(f"{n} {status + ' ' if status else ''}website{'s' if n != 1 else ''}.", "websites",
                  {"status": status} if status else {},
                  [{"type": "website", "id": str(w.id), "label": w.name, "href": f"/websites/{w.id}",
                    "status": w.status} for w in rows],
                  [{"label": "Website Studio", "href": "/websites"}])


def t_pipeline_value(db: Session, org) -> Result:
    pv = ins.pipeline_value(db, org)
    if not pv["open_value"]:
        ans = "No open leads have a stated budget yet, so pipeline value is 0."
    else:
        money = ", ".join(f"{c} {v:,.0f}" for c, v in sorted(pv["open_value"].items()))
        ans = f"Open pipeline value (midpoint of stated budgets): {money}."
    if pv["leads_without_budget"]:
        ans += f" {pv['leads_without_budget']} open leads have no stated budget and are not valued."
    rows = [{"type": "stage", "id": s["stage"], "label": _label(s["stage"]), "leads": s["leads"],
             "with_budget": s["with_budget"], "value": s["value"], "href": f"/leads?status={s['stage']}"}
            for s in pv["stages"]]
    return Result(ans, "pipeline_value", {}, rows, [{"label": "Insights", "href": "/insights"}])


def t_conversion(db: Session, org) -> Result:
    by = dict(db.execute(select(Lead.status, func.count()).where(Lead.organization_id == org,
                                                                 Lead.deleted_at.is_(None))
                         .group_by(Lead.status)).all())
    total = sum(by.values())
    won = by.get("converted", 0)
    closed = won + by.get("lost", 0) + by.get("not_interested", 0)
    if total == 0:
        ans = "There are no leads yet, so there is no conversion rate."
    else:
        ans = f"{won} of {total} leads converted ({won / total:.1%} overall)."
        if closed:
            ans += f" Win rate on closed deals: {won}/{closed} ({won / closed:.1%})."
    return Result(ans, "conversion_rate", {}, [{"type": "stat", "id": k, "label": _label(k), "count": v}
                                               for k, v in sorted(by.items(), key=lambda kv: -kv[1])],
                  [{"label": "Analytics", "href": "/analytics"}])


TOOLS = {
    "count_leads": (t_count_leads, {"status": "status", "city": "str", "industry": "str"}),
    "list_leads": (t_list_leads, {"status": "status", "city": "str", "industry": "str", "interest": "interest",
                                  "min_budget": "num", "limit": "int"}),
    "count_businesses": (t_businesses, {"city": "str", "industry": "str", "website_status": "str"}),
    "campaigns": (t_campaigns, {"status": "str"}),
    "websites": (t_websites, {"status": "str"}),
    "pipeline_value": (t_pipeline_value, {}),
    "conversion_rate": (t_conversion, {}),
}
TOOL_DOCS = {
    "count_leads": "Count leads, optionally filtered by status, city, industry.",
    "list_leads": "List leads; filters: status, city, industry, interest (high|medium|low|none), min_budget, limit.",
    "count_businesses": "Count discovered businesses; filters: city, industry, website_status (none|has_website|..).",
    "campaigns": "List campaigns; optional status (draft|pending_approval|approved|running|paused|completed).",
    "websites": "List generated websites; optional status (draft|preview|approved|published).",
    "pipeline_value": "Open pipeline value from stated budgets, by stage and currency.",
    "conversion_rate": "Lead conversion and win rate.",
}


def _clean_args(tool: str, raw: dict) -> dict:
    spec = TOOLS[tool][1]
    out: dict = {}
    for k, v in (raw or {}).items():
        kind = spec.get(k)
        if kind is None or v in (None, ""):
            continue
        if kind == "status":
            v = str(v).lower().replace(" ", "_")
            if v not in STATUSES:
                continue
        elif kind == "interest":
            v = str(v).lower()
            if v not in ("high", "medium", "low", "none", "unknown"):
                continue
        elif kind == "num":
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
        elif kind == "int":
            try:
                v = max(1, min(int(v), MAX_ROWS))
            except (TypeError, ValueError):
                continue
        else:
            v = str(v)[:120]
        out[k] = v
    return out


# ------------------------------------------------------------------ intent parsing
WRITE_VERBS = re.compile(r"\b(delete|remove|drop|send|create|add|update|change|edit|modify|publish|call|email|"
                         r"message|text|assign|move|mark|approve|cancel|pay|refund|import|insert|truncate)\b", re.I)
QUESTION_START = re.compile(r"^\s*(how|what|which|who|show|list|count|give|find|tell|are|is|do|does|top|any)\b",
                            re.I)
STATUS_SYNONYMS = {
    "won": "converted", "converted": "converted", "closed won": "converted", "lost": "lost",
    "proposal": "proposal_sent", "proposals": "proposal_sent", "negotiating": "negotiation",
    "meeting": "meeting_scheduled", "meetings": "meeting_scheduled", "qualified": "qualified",
    "interested": "interested", "contacted": "contacted", "new": "discovered", "discovered": "discovered",
    "callback": "callback_requested", "verified": "verified",
}


def _amount(s: str) -> float | None:
    m = re.search(r"(?:over|above|more than|greater than|at least|>=?|min(?:imum)?)\s*(?:[a-z]{3}\s*|[$₹€£]\s*)?"
                  r"([\d,.]+)\s*(k|m|lakh|lakhs|lac|cr|crore)?", s, re.I)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    mult = {"k": 1e3, "m": 1e6, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "cr": 1e7, "crore": 1e7}
    return v * mult.get((m.group(2) or "").lower(), 1)


def _known(db: Session, org, col_lead, col_biz) -> list[str]:
    vals = {v for v in db.scalars(select(col_lead).where(col_lead.is_not(None), Lead.organization_id == org)
                                  .distinct()) if v}
    vals |= {v for v in db.scalars(select(col_biz).where(col_biz.is_not(None), Business.organization_id == org)
                                   .distinct()) if v}
    return sorted(vals, key=len, reverse=True)


def parse_rules(db: Session, org, q: str) -> tuple[str, dict] | None:
    s = q.lower()
    args: dict = {}
    for city in _known(db, org, Lead.city, Business.city):
        if re.search(rf"\b{re.escape(city.lower())}\b", s):
            args["city"] = city
            break
    for ind in _known(db, org, Lead.industry, Business.industry):
        if re.search(rf"\b{re.escape(ind.lower())}\b", s):
            args["industry"] = ind
            break
    for st in sorted(STATUSES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(st.replace('_', ' '))}\b", s) or st in s:
            args["status"] = st
            break
    else:
        for word, st in STATUS_SYNONYMS.items():
            if re.search(rf"\b{word}\b", s):
                args["status"] = st
                break
    if re.search(r"\b(pipeline value|pipeline worth|worth|total value|how much .*pipeline)\b", s):
        return "pipeline_value", {}
    if re.search(r"\b(conversion|win rate|close rate|convert)\b", s):
        return "conversion_rate", {}
    if re.search(r"\bcampaigns?\b", s):
        st = next((x for x in ("running", "draft", "paused", "completed", "approved") if x in s), None)
        return "campaigns", ({"status": st} if st else {})
    if re.search(r"\b(websites?|sites?)\b", s) and "without" not in s and "no website" not in s:
        st = next((x for x in ("published", "draft", "preview", "approved") if x in s), None)
        return "websites", ({"status": st} if st else {})
    if re.search(r"\b(business|businesses|compan(y|ies)|shops?)\b", s):
        a = {k: v for k, v in args.items() if k in ("city", "industry")}
        if re.search(r"\b(without|no|missing)\b.*\bwebsite", s):
            a["website_status"] = "none"
        return "count_businesses", a
    hot = bool(re.search(r"\b(hot|high[- ]interest|very interested|most interested|warm)\b", s))
    budget = _amount(s)
    wants_budget = bool(re.search(r"\b(budget|biggest|largest|top|best|opportunit)", s))
    if re.search(r"\b(leads?|prospects?|deals?|opportunit(y|ies)|clients?)\b", s) or hot or args:
        if hot:
            args["interest"] = "high"
            args.pop("status", None) if args.get("status") == "interested" else None
        if budget is not None:
            args["min_budget"] = budget
        elif wants_budget and not hot:
            args["min_budget"] = 0.0
        if hot or "min_budget" in args or re.search(r"\b(list|show|which|who|top|give)\b", s):
            return "list_leads", args
        return "count_leads", {k: v for k, v in args.items() if k in ("status", "city", "industry")}
    return None


def _llm_select(q: str) -> tuple[str, dict, str] | None:
    from app.modules.agents.config import ai_settings
    from app.modules.agents.llm import LLMUnavailable, ModelSpec, chat

    s = ai_settings()
    if not s.ollama_base_url:
        return None
    sys = ("You route questions about a sales pipeline to ONE read-only tool. Reply with JSON only: "
           '{"tool": "<name>", "args": {...}} or {"tool": null} if the question is not about leads, businesses, '
           "campaigns, websites, pipeline value or conversion, or if it asks to change/send/delete anything.\n"
           "Tools:\n" + "\n".join(f"- {k}: {v}" for k, v in TOOL_DOCS.items())
           + f"\nValid lead statuses: {', '.join(STATUSES)}.")
    try:
        r = chat(ModelSpec("ollama", s.ollama_chat_model, 0.0, 200),
                 [{"role": "system", "content": sys}, {"role": "user", "content": q}])
    except LLMUnavailable:
        return None
    m = re.search(r"\{.*\}", r.text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    tool = data.get("tool")
    if tool is None:
        return ("__refuse__", {}, r.model)
    if tool not in TOOLS or not isinstance(data.get("args", {}), dict):
        return None
    return tool, _clean_args(tool, data.get("args") or {}), r.model


SUGGESTIONS = [
    "How many leads do I have?",
    "Show hot leads with high interest",
    "Which leads have a budget over 50k?",
    "What is my pipeline value?",
    "What is my conversion rate?",
    "Businesses without a website",
    "Which campaigns are running?",
    "How many websites are published?",
]


def ask(db: Session, org: uuid.UUID, question: str, mode: str = "auto") -> dict:
    q = question.strip()
    used_mode, model = "rules", None
    if WRITE_VERBS.search(q) and not QUESTION_START.search(q):
        r = Result("I'm a read-only copilot: I can answer questions about your pipeline but I never create, change, "
                   "send or delete anything. Use the relevant page to make changes.", None, {}, refused=True)
        return _out(r, "guardrail", None)
    picked = None
    if mode in ("auto", "llm"):
        sel = _llm_select(q)
        if sel and sel[0] == "__refuse__":
            picked, used_mode, model = None, "ollama", sel[2]
        elif sel:
            picked, used_mode, model = (sel[0], sel[1]), "ollama", sel[2]
    if picked is None and used_mode == "rules":
        p = parse_rules(db, org, q)
        if p:
            picked = (p[0], _clean_args(p[0], p[1]))
    if picked is None:
        r = Result("That's outside what I can answer. I can count and list your leads, businesses, campaigns and "
                   "websites, and report pipeline value and conversion — try one of the suggestions.", None, {},
                   refused=True)
        return _out(r, used_mode, model)
    fn = TOOLS[picked[0]][0]
    return _out(fn(db, org, **picked[1]), used_mode, model)


def _out(r: Result, mode: str, model: str | None) -> dict:
    return {"answer": r.answer, "tool": r.tool, "args": r.args, "rows": r.rows, "citations": r.citations,
            "refused": r.refused, "mode": mode, "model": model, "read_only": True}
