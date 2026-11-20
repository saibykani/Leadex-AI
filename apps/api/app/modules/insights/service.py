"""Read-only growth analytics computed from real tenant rows. Nothing here is estimated or invented: every
number is a count/sum over stored data, and anything model-like (forecast) states its formula and refuses to
produce a value when there is not enough history."""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.agents.models import AgentRun, AIAgent
from app.modules.billing.models import Invoice
from app.modules.campaigns.models import Campaign
from app.modules.crm.models import Lead, LeadActivity, LeadTask
from app.modules.crm.service import STATUSES
from app.modules.discovery.models import Business
from app.modules.marketplace.models import CommissionTransaction, Referral
from app.modules.pipeline.models import ConversationOutcome
from app.modules.voice.models import CallSession
from app.modules.websites.models import WebsiteProject

CLOSED_WON = "converted"
CLOSED_LOST = frozenset({"lost", "not_interested"})
EXCLUDED = frozenset({"do_not_contact", "suppressed"})
OPEN_STAGES = tuple(s for s in STATUSES if s not in CLOSED_LOST | EXCLUDED | {CLOSED_WON})
FUNNEL = ("discovered", "verified", "approved_for_outreach", "contacted", "interested", "qualified",
          "meeting_scheduled", "proposal_sent", "negotiation", "converted")
MIN_CLOSED_FOR_FORECAST = 5
MIN_STAGE_SAMPLE = 3


def _day(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).date()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _leads(db: Session, org: uuid.UUID) -> list[Lead]:
    return list(db.scalars(select(Lead).where(Lead.organization_id == org, Lead.deleted_at.is_(None))))


def latest_outcomes(db: Session, org: uuid.UUID) -> dict[uuid.UUID, ConversationOutcome]:
    """Most recent conversation outcome per lead."""
    out: dict[uuid.UUID, ConversationOutcome] = {}
    rows = db.scalars(select(ConversationOutcome).where(ConversationOutcome.organization_id == org,
                                                        ConversationOutcome.lead_id.is_not(None))
                      .order_by(ConversationOutcome.created_at))
    for o in rows:
        out[o.lead_id] = o
    return out


def budget_mid(o: ConversationOutcome | None) -> tuple[float, str] | None:
    if o is None or o.budget_currency is None or (o.budget_min is None and o.budget_max is None):
        return None
    lo = _f(o.budget_min if o.budget_min is not None else o.budget_max)
    hi = _f(o.budget_max if o.budget_max is not None else o.budget_min)
    return (lo + hi) / 2, o.budget_currency


# ------------------------------------------------------------------ overview (time series)
SERIES = ("leads", "conversions", "outcomes_with_budget", "websites", "agent_runs", "calls")


def overview(db: Session, org: uuid.UUID, days: int = 30) -> dict:
    today = utcnow().date()
    start = today - timedelta(days=days - 1)
    since = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    axis = [start + timedelta(days=i) for i in range(days)]
    buckets: dict[str, dict[date, float]] = {k: defaultdict(float) for k in SERIES}
    revenue: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))

    def add(key, dts):
        for d in dts:
            dd = _day(d)
            if dd is not None and dd >= start:
                buckets[key][dd] += 1

    add("leads", db.scalars(select(Lead.created_at).where(Lead.organization_id == org, Lead.deleted_at.is_(None),
                                                         Lead.created_at >= since)))
    for a in db.scalars(select(LeadActivity).where(LeadActivity.organization_id == org,
                                                   LeadActivity.type == "status.changed",
                                                   LeadActivity.created_at >= since)):
        if (a.data or {}).get("to") == CLOSED_WON:
            add("conversions", [a.created_at])
    add("outcomes_with_budget", db.scalars(
        select(ConversationOutcome.created_at).where(ConversationOutcome.organization_id == org,
                                                     ConversationOutcome.budget_currency.is_not(None),
                                                     ConversationOutcome.created_at >= since)))
    add("websites", db.scalars(select(WebsiteProject.created_at).where(WebsiteProject.organization_id == org,
                                                                       WebsiteProject.created_at >= since)))
    add("agent_runs", db.scalars(select(AgentRun.created_at).where(AgentRun.organization_id == org,
                                                                   AgentRun.created_at >= since)))
    add("calls", db.scalars(select(CallSession.created_at).where(CallSession.organization_id == org,
                                                                 CallSession.created_at >= since)))
    for inv in db.scalars(select(Invoice).where(Invoice.organization_id == org, Invoice.status == "paid",
                                                Invoice.paid_at.is_not(None), Invoice.paid_at >= since)):
        d = _day(inv.paid_at)
        if d and d >= start:
            revenue[f"invoices_paid:{inv.currency}"][d] += _f(inv.total)
    for t in db.scalars(select(CommissionTransaction).where(CommissionTransaction.organization_id == org,
                                                            CommissionTransaction.kind == "settlement",
                                                            CommissionTransaction.created_at >= since)):
        d = _day(t.created_at)
        if d and d >= start:
            revenue[f"commissions_settled:{t.currency}"][d] += _f(t.amount)

    points = []
    for d in axis:
        p: dict = {"date": d.isoformat()}
        for k in SERIES:
            p[k] = buckets[k].get(d, 0)
        points.append(p)
    totals = {k: sum(p[k] for p in points) for k in SERIES}
    # Previous-period comparison (same window length) so the UI can show honest deltas.
    prev_since = since - timedelta(days=days)
    prev = {
        "leads": db.scalar(select(func.count()).select_from(Lead).where(
            Lead.organization_id == org, Lead.deleted_at.is_(None), Lead.created_at >= prev_since,
            Lead.created_at < since)) or 0,
    }
    rev_series = []
    for key, by_day in revenue.items():
        kind, cur = key.split(":")
        rev_series.append({"kind": kind, "currency": cur, "total": round(sum(by_day.values()), 2),
                           "points": [{"date": d.isoformat(), "value": round(by_day.get(d, 0), 2)} for d in axis]})
    return {"days": days, "start": start.isoformat(), "end": today.isoformat(), "points": points, "totals": totals,
            "previous": prev, "revenue": rev_series,
            "notes": {"revenue": "Paid platform invoices and settled marketplace commissions only. "
                                 "Nothing is projected."}}


# ------------------------------------------------------------------ pipeline value
def pipeline_value(db: Session, org: uuid.UUID) -> dict:
    leads = _leads(db, org)
    outs = latest_outcomes(db, org)
    stages: dict[str, dict] = {}
    totals: dict[str, float] = defaultdict(float)
    without = 0
    for lead in leads:
        if lead.status in EXCLUDED:
            continue
        st = stages.setdefault(lead.status, {"stage": lead.status, "leads": 0, "with_budget": 0, "value": {}})
        st["leads"] += 1
        bm = budget_mid(outs.get(lead.id))
        if bm is None:
            if lead.status not in CLOSED_LOST:
                without += 1
            continue
        mid, cur = bm
        st["with_budget"] += 1
        st["value"][cur] = round(st["value"].get(cur, 0) + mid, 2)
        if lead.status not in CLOSED_LOST and lead.status != CLOSED_WON:
            totals[cur] += mid
    order = {s: i for i, s in enumerate(STATUSES)}
    return {"stages": sorted(stages.values(), key=lambda s: order.get(s["stage"], 99)),
            "open_value": {k: round(v, 2) for k, v in totals.items()},
            "leads_without_budget": without,
            "method": "Sum of the midpoint of each lead's most recent stated budget (conversation outcomes), "
                      "grouped by lead stage and currency. Leads with no stated budget are counted, not valued."}


# ------------------------------------------------------------------ forecast
def _stage_history(db: Session, org: uuid.UUID, leads: list[Lead]) -> dict[uuid.UUID, set[str]]:
    seen: dict[uuid.UUID, set[str]] = {lead.id: {lead.status} for lead in leads}
    for a in db.scalars(select(LeadActivity).where(LeadActivity.organization_id == org,
                                                   LeadActivity.type == "status.changed")):
        d = a.data or {}
        if a.lead_id in seen:
            for k in ("from", "to"):
                if d.get(k):
                    seen[a.lead_id].add(d[k])
    return seen


def forecast(db: Session, org: uuid.UUID) -> dict:
    leads = _leads(db, org)
    won = sum(1 for lead in leads if lead.status == CLOSED_WON)
    lost = sum(1 for lead in leads if lead.status in CLOSED_LOST)
    closed = won + lost
    formula = ("forecast[currency] = Σ over open leads with a stated budget of budget_midpoint × "
               "P(converted | lead reached its current stage); P = converted ÷ closed among historical leads that "
               f"reached that stage (stage sample < {MIN_STAGE_SAMPLE} closed ⇒ overall win rate is used).")
    base = {"formula": formula, "closed_deals": closed, "won": won, "lost": lost,
            "min_closed_required": MIN_CLOSED_FOR_FORECAST}
    if closed < MIN_CLOSED_FOR_FORECAST:
        return {**base, "status": "insufficient_data", "win_rate": None, "stages": [], "forecast": {},
                "message": f"Need at least {MIN_CLOSED_FOR_FORECAST} closed deals (won or lost) to forecast; "
                           f"you have {closed}."}
    win_rate = won / closed
    seen = _stage_history(db, org, leads)
    status_of = {lead.id: lead.status for lead in leads}
    rates: dict[str, tuple[float, int, str]] = {}
    for stage in OPEN_STAGES:
        reached = [lid for lid, s in seen.items() if stage in s]
        c = [lid for lid in reached if status_of[lid] == CLOSED_WON or status_of[lid] in CLOSED_LOST]
        w = sum(1 for lid in c if status_of[lid] == CLOSED_WON)
        rates[stage] = (w / len(c), len(c), "stage") if len(c) >= MIN_STAGE_SAMPLE else (win_rate, len(c), "overall")
    outs = latest_outcomes(db, org)
    fc: dict[str, float] = defaultdict(float)
    stage_rows: dict[str, dict] = {}
    for lead in leads:
        if lead.status not in OPEN_STAGES:
            continue
        bm = budget_mid(outs.get(lead.id))
        if bm is None:
            continue
        mid, cur = bm
        rate, n, src = rates[lead.status]
        fc[cur] += mid * rate
        row = stage_rows.setdefault(lead.status, {"stage": lead.status, "rate": round(rate, 4), "sample": n,
                                                   "rate_source": src, "value": {}, "weighted": {}})
        row["value"][cur] = round(row["value"].get(cur, 0) + mid, 2)
        row["weighted"][cur] = round(row["weighted"].get(cur, 0) + mid * rate, 2)
    order = {s: i for i, s in enumerate(STATUSES)}
    return {**base, "status": "ok", "win_rate": round(win_rate, 4),
            "stages": sorted(stage_rows.values(), key=lambda r: order.get(r["stage"], 99)),
            "forecast": {k: round(v, 2) for k, v in fc.items()}, "message": None}


# ------------------------------------------------------------------ dashboard facts / briefing
def facts(db: Session, org: uuid.UUID) -> dict:
    now = utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    leads = _leads(db, org)
    outs = latest_outcomes(db, org)
    by_status: dict[str, int] = defaultdict(int)
    for lead in leads:
        by_status[lead.status] += 1
    new_24h = sum(1 for lead in leads if (_aware(lead.created_at) or now) >= day_ago)
    new_7d = sum(1 for lead in leads if (_aware(lead.created_at) or now) >= week_ago)
    hot = [lead for lead in leads if (o := outs.get(lead.id)) is not None and o.interest == "high"
           and lead.status not in CLOSED_LOST | EXCLUDED | {CLOSED_WON}]
    overdue = db.scalar(select(func.count()).select_from(LeadTask).join(Lead, Lead.id == LeadTask.lead_id).where(
        LeadTask.organization_id == org, LeadTask.completed_at.is_(None), LeadTask.due_at.is_not(None),
        LeadTask.due_at < now, Lead.deleted_at.is_(None))) or 0
    open_tasks = db.scalar(select(func.count()).select_from(LeadTask).join(Lead, Lead.id == LeadTask.lead_id).where(
        LeadTask.organization_id == org, LeadTask.completed_at.is_(None), Lead.deleted_at.is_(None))) or 0
    campaigns_running = db.scalar(select(func.count()).select_from(Campaign).where(
        Campaign.organization_id == org, Campaign.status == "running")) or 0
    sites = dict(db.execute(select(WebsiteProject.status, func.count()).where(
        WebsiteProject.organization_id == org).group_by(WebsiteProject.status)).all())
    businesses = db.scalar(select(func.count()).select_from(Business).where(
        Business.organization_id == org, Business.deleted_at.is_(None))) or 0
    agents = db.scalar(select(func.count()).select_from(AIAgent).where(
        AIAgent.organization_id == org, AIAgent.deleted_at.is_(None))) or 0
    referrals = db.scalar(select(func.count()).select_from(Referral).where(Referral.organization_id == org)) or 0
    pv = pipeline_value(db, org)
    return {"total_leads": len(leads), "by_status": dict(by_status), "new_leads_24h": new_24h,
            "new_leads_7d": new_7d, "hot_leads": len(hot), "overdue_tasks": overdue, "open_tasks": open_tasks,
            "campaigns_running": campaigns_running, "websites_published": sites.get("published", 0),
            "websites_total": sum(sites.values()), "businesses": businesses, "agents": agents,
            "referrals": referrals, "converted": by_status.get(CLOSED_WON, 0),
            "pipeline_open_value": pv["open_value"], "leads_without_budget": pv["leads_without_budget"]}


def _money(values: dict[str, float]) -> str:
    if not values:
        return ""
    return ", ".join(f"{cur} {Decimal(str(v)).quantize(Decimal('1')):,}" for cur, v in sorted(values.items()))


def briefing_text(f: dict) -> list[str]:
    """Deterministic sentences. Each one is a direct restatement of a counted fact."""
    lines: list[str] = []
    if f["total_leads"] == 0 and f["businesses"] == 0:
        return ["Your workspace is empty. Run a discovery search or import a CSV to start building pipeline."]
    lines.append(f"{f['new_leads_24h']} new lead{'s' if f['new_leads_24h'] != 1 else ''} in the last 24 hours "
                 f"({f['new_leads_7d']} this week, {f['total_leads']} total).")
    if f["hot_leads"]:
        lines.append(f"{f['hot_leads']} open lead{'s' if f['hot_leads'] != 1 else ''} showed high interest in "
                     f"their latest conversation — prioritise these today.")
    if f["pipeline_open_value"]:
        lines.append(f"Open pipeline with stated budgets: {_money(f['pipeline_open_value'])}"
                     + (f"; {f['leads_without_budget']} open leads have no stated budget yet."
                        if f["leads_without_budget"] else "."))
    if f["overdue_tasks"]:
        lines.append(f"{f['overdue_tasks']} follow-up task{'s are' if f['overdue_tasks'] != 1 else ' is'} overdue.")
    elif f["open_tasks"]:
        lines.append(f"No overdue follow-ups; {f['open_tasks']} open task{'s' if f['open_tasks'] != 1 else ''}.")
    if f["campaigns_running"]:
        lines.append(f"{f['campaigns_running']} campaign{'s' if f['campaigns_running'] != 1 else ''} running.")
    if f["websites_total"]:
        lines.append(f"{f['websites_published']} of {f['websites_total']} generated websites are published.")
    return lines


def briefing(db: Session, org: uuid.UUID, polish: bool = False) -> dict:
    f = facts(db, org)
    lines = briefing_text(f)
    text = " ".join(lines)
    mode, model = "deterministic", None
    if polish:
        from app.modules.agents.config import ai_settings
        from app.modules.agents.llm import LLMUnavailable, ModelSpec, chat

        s = ai_settings()
        try:
            r = chat(ModelSpec("ollama", s.ollama_chat_model, 0.2, 220), [
                {"role": "system", "content": "Rewrite the following business facts as a crisp 2-3 sentence morning "
                                              "briefing for a sales team. Do NOT add, change or infer any number or "
                                              "fact. Output plain text only."},
                {"role": "user", "content": text}])
            if r.text.strip():
                text, mode, model = r.text.strip(), "ollama", r.model
        except LLMUnavailable:
            pass
    return {"text": text, "lines": lines, "mode": mode, "model": model, "facts": f, "generated_at": utcnow()}


# ------------------------------------------------------------------ deeper analytics
def analytics(db: Session, org: uuid.UUID, weeks: int = 8) -> dict:
    leads = _leads(db, org)
    outs = latest_outcomes(db, org)
    now = utcnow()
    week0 = (now - timedelta(days=now.weekday())).date() - timedelta(weeks=weeks - 1)
    cohorts: dict[date, dict] = {week0 + timedelta(weeks=i): {"week": (week0 + timedelta(weeks=i)).isoformat(),
                                                               "created": 0, "engaged": 0, "converted": 0}
                                 for i in range(weeks)}
    engaged_states = {"contacted", "interested", "qualified", "meeting_scheduled", "proposal_sent", "negotiation",
                      "callback_requested", "converted"}
    by_ind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_city: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for lead in leads:
        d = _day(lead.created_at)
        if d:
            wk = d - timedelta(days=d.weekday())
            if wk in cohorts:
                c = cohorts[wk]
                c["created"] += 1
                c["engaged"] += lead.status in engaged_states
                c["converted"] += lead.status == CLOSED_WON
        for key, bucket in ((lead.industry, by_ind), (lead.city, by_city)):
            b = bucket[(key or "Unknown").strip() or "Unknown"]
            b[0] += 1
            b[1] += lead.status == CLOSED_WON

    def top(bucket):
        rows = [{"key": k, "leads": v[0], "converted": v[1], "rate": round(v[1] / v[0], 4) if v[0] else 0}
                for k, v in bucket.items()]
        return sorted(rows, key=lambda r: (-r["leads"], r["key"]))[:10]

    interest: dict[str, int] = defaultdict(int)
    for o in db.scalars(select(ConversationOutcome).where(ConversationOutcome.organization_id == org)):
        interest[o.interest] += 1
    mids = [(bm[0], bm[1]) for o in outs.values() if (bm := budget_mid(o))]
    hist: list[dict] = []
    if mids:
        cur = max({c for _, c in mids}, key=lambda c: sum(1 for _, x in mids if x == c))
        vals = sorted(v for v, c in mids if c == cur)
        edges = [0, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
        for i, lo in enumerate(edges):
            hi = edges[i + 1] if i + 1 < len(edges) else None
            n = sum(1 for v in vals if v >= lo and (hi is None or v < hi))
            hist.append({"from": lo, "to": hi, "count": n, "currency": cur})
        while hist and hist[-1]["count"] == 0:
            hist.pop()
    agents = {a.id: a.name for a in db.scalars(select(AIAgent).where(AIAgent.organization_id == org))}
    perf: dict[uuid.UUID, dict] = {}
    for r in db.scalars(select(AgentRun).where(AgentRun.organization_id == org)):
        p = perf.setdefault(r.agent_id, {"agent_id": str(r.agent_id), "name": agents.get(r.agent_id, "Agent"),
                                         "runs": 0, "errors": 0, "latency_total": 0, "outcomes": defaultdict(int)})
        p["runs"] += 1
        p["errors"] += bool(r.error)
        p["latency_total"] += r.latency_ms or 0
    for o in db.scalars(select(ConversationOutcome).where(ConversationOutcome.organization_id == org,
                                                          ConversationOutcome.agent_id.is_not(None))):
        p = perf.setdefault(o.agent_id, {"agent_id": str(o.agent_id), "name": agents.get(o.agent_id, "Agent"),
                                         "runs": 0, "errors": 0, "latency_total": 0, "outcomes": defaultdict(int)})
        p["outcomes"][o.interest] += 1
    agent_rows = [{"agent_id": p["agent_id"], "name": p["name"], "runs": p["runs"], "errors": p["errors"],
                   "avg_latency_ms": round(p["latency_total"] / p["runs"]) if p["runs"] else None,
                   "outcomes": dict(p["outcomes"])} for p in perf.values()]
    funnel = []
    seen = _stage_history(db, org, leads)
    for s in FUNNEL:
        funnel.append({"stage": s, "count": sum(1 for st in seen.values() if s in st or
                                                (s == "discovered"))})
    return {"cohorts": list(cohorts.values()), "by_industry": top(by_ind), "by_city": top(by_city),
            "interest": dict(interest), "budget_histogram": hist,
            "agents": sorted(agent_rows, key=lambda r: -r["runs"]), "funnel": funnel}


def top_opportunities(db: Session, org: uuid.UUID, limit: int = 6) -> list[dict]:
    leads = {lead.id: lead for lead in _leads(db, org)}
    rank = {"high": 0, "medium": 1, "low": 2, "unknown": 3, "none": 4}
    rows = []
    for lid, o in latest_outcomes(db, org).items():
        lead = leads.get(lid)
        bm = budget_mid(o)
        if lead is None or bm is None or lead.status in CLOSED_LOST | EXCLUDED | {CLOSED_WON}:
            continue
        rows.append({"lead_id": str(lead.id), "business_name": lead.business_name, "status": lead.status,
                     "city": lead.city, "interest": o.interest, "budget_mid": round(bm[0], 2), "currency": bm[1],
                     "budget_min": _f(o.budget_min) if o.budget_min is not None else None,
                     "budget_max": _f(o.budget_max) if o.budget_max is not None else None,
                     "timeline": o.timeline, "next_step": o.next_step})
    rows.sort(key=lambda r: (rank.get(r["interest"], 9), -r["budget_mid"]))
    return rows[:limit]
