"""Billing domain: plan catalog, lazy subscriptions, metering, plan limits, budgets, proration, invoices.

Public helpers other modules should adopt (see `limit_guard` for the FastAPI form):

    enforce_limit(db, org_id, "leads")                 # before creating a lead  -> 402 plan_limit_reached
    record_usage(db, org_id, "voice_minutes", 3.5, cost=Decimal("0.42"), lead_id=..., campaign_id=...)
    check_budget(db, org_id, cost)                     # before a paid operation -> 402 budget_exceeded (hard stop)

Callers own the transaction (they commit).
"""
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, get_tenant
from app.modules.billing.models import (
    BillingUsage,
    Budget,
    BudgetAlert,
    Invoice,
    InvoiceLine,
    Plan,
    Subscription,
)

RESOURCES = ("users", "leads", "searches", "ai_conversations", "voice_minutes", "email_campaigns", "websites",
             "workflows", "active_agents", "storage_mb")
PERIOD_DAYS = 30
TRIAL_DAYS = 14
CENT = Decimal("0.01")
INACTIVE = {"past_due", "cancelled"}


def _l(users, leads, searches, ai, voice, email, websites, workflows, agents, storage):
    return dict(zip(RESOURCES, (users, leads, searches, ai, voice, email, websites, workflows, agents, storage),
                    strict=True))


# None = unlimited. Prices are list prices in USD and configurable (edit rows in `plans`).
PLAN_CATALOG: list[dict] = [
    {"code": "free_trial", "name": "Free Trial", "price": "0.00", "trial_days": TRIAL_DAYS, "public": False,
     "limits": _l(2, 100, 50, 100, 30, 2, 1, 3, 1, 500)},
    {"code": "starter", "name": "Starter", "price": "49.00", "limits": _l(3, 1000, 500, 1000, 200, 10, 3, 10, 3, 5000)},
    {"code": "professional", "name": "Professional", "price": "149.00",
     "limits": _l(10, 10000, 3000, 10000, 1000, 50, 10, 50, 10, 25000)},
    {"code": "business", "name": "Business", "price": "399.00",
     "limits": _l(25, 50000, 10000, 50000, 5000, 200, 50, 200, 25, 100000)},
    {"code": "enterprise", "name": "Enterprise", "price": "999.00",
     "limits": _l(100, 500000, 50000, 250000, 25000, 1000, 250, 1000, 100, 1000000)},
    {"code": "white_label", "name": "White Label", "price": "1999.00",
     "limits": _l(None, None, None, None, None, None, None, None, None, None)},
]


def plan_uuid(code: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"leadex:plan:{code}")


def ensure_plans(db: Session) -> None:
    """Idempotent seed (migration 0012 seeds the same rows on PostgreSQL; this covers SQLite/tests)."""
    have = set(db.scalars(select(Plan.code)))
    missing = [p for p in PLAN_CATALOG if p["code"] not in have]
    if not missing:
        return
    for i, p in enumerate(PLAN_CATALOG):  # PostgreSQL rows come from migration 0012; this path is SQLite/tests
        if p in missing:
            db.add(Plan(id=plan_uuid(p["code"]), code=p["code"], name=p["name"], price_monthly=Decimal(p["price"]),
                        currency="USD", limits=p["limits"], trial_days=p.get("trial_days", 0), sort_order=i,
                        is_public=p.get("public", True)))
    db.flush()


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def get_plan(db: Session, code: str) -> Plan:
    ensure_plans(db)
    p = db.scalar(select(Plan).where(Plan.code == code))
    if p is None:
        raise AppError(404, "not_found", "Plan not found")
    return p


def _money(v) -> Decimal:
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def _new_invoice(db, org_id, lines: list[tuple[str, Decimal]], *, period_start=None, period_end=None,
                 notes=None) -> Invoice:
    n = (db.scalar(select(func.count()).select_from(Invoice).where(Invoice.organization_id == org_id)) or 0) + 1
    subtotal = _money(sum((a for _, a in lines), Decimal("0")))
    total = max(subtotal, Decimal("0.00"))
    inv = Invoice(organization_id=org_id, number=f"INV-{str(org_id)[:8].upper()}-{n:05d}",
                  status="paid" if total == 0 else "open", currency="USD", subtotal=subtotal, total=total,
                  period_start=period_start, period_end=period_end, due_at=utcnow() + timedelta(days=7),
                  paid_at=utcnow() if total == 0 else None, notes=notes)
    db.add(inv)
    db.flush()
    for desc, amount in lines:
        db.add(InvoiceLine(organization_id=org_id, invoice_id=inv.id, description=desc, quantity=Decimal("1"),
                           unit_amount=_money(amount), amount=_money(amount)))
    return inv


def get_subscription(db: Session, org_id: uuid.UUID) -> Subscription:
    """Lazily creates a Free Trial; applies trial expiry and period renewal on read."""
    sub = db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    now = utcnow()
    if sub is None:
        trial = get_plan(db, "free_trial")
        sub = Subscription(organization_id=org_id, plan_id=trial.id, status="trialing", current_period_start=now,
                           current_period_end=now + timedelta(days=trial.trial_days or TRIAL_DAYS),
                           trial_end=now + timedelta(days=trial.trial_days or TRIAL_DAYS))
        db.add(sub)
        db.flush()
        return sub
    if sub.status == "trialing" and sub.trial_end and _aware(sub.trial_end) <= now:
        sub.status = "past_due"  # trial expired: choose a paid plan to continue creating resources
    elif sub.status == "active":
        plan = db.get(Plan, sub.plan_id)
        for _ in range(12):  # catch up at most a year of missed renewals
            if _aware(sub.current_period_end) > now:
                break
            start, end = _aware(sub.current_period_end), _aware(sub.current_period_end) + timedelta(days=PERIOD_DAYS)
            if sub.cancel_at_period_end:
                sub.status = "cancelled"
                break
            inv = _new_invoice(db, org_id, [(f"{plan.name} plan ({start:%Y-%m-%d} - {end:%Y-%m-%d})",
                                             plan.price_monthly)], period_start=start, period_end=end)
            sub.current_period_start, sub.current_period_end = start, end
            if inv.status == "open" and _aware(inv.due_at) <= now:
                sub.status = "past_due"
    return sub


def plan_of(db: Session, sub: Subscription) -> Plan:
    return db.get(Plan, sub.plan_id)


# ---------------------------------------------------------------- usage counting
Counter = Callable[[Session, uuid.UUID], int]
_COUNTERS: dict[str, Counter] = {}


def register_counter(resource: str, fn: Counter) -> Counter:
    """Modules owning a 'stock' resource (e.g. agents -> active_agents, websites) may register an exact counter."""
    _COUNTERS[resource] = fn
    return fn


def _count_leads(db, org_id):
    from app.modules.crm.models import Lead

    return db.scalar(select(func.count()).select_from(Lead).where(Lead.organization_id == org_id,
                                                                  Lead.deleted_at.is_(None))) or 0


def _count_users(db, org_id):
    from app.modules.identity.models import OrganizationMembership

    return db.scalar(select(func.count()).select_from(OrganizationMembership).where(
        OrganizationMembership.organization_id == org_id, OrganizationMembership.status == "active")) or 0


def _count_workflows(db, org_id):
    from app.modules.automation.models import Workflow

    return db.scalar(select(func.count()).select_from(Workflow).where(Workflow.organization_id == org_id,
                                                                      Workflow.deleted_at.is_(None))) or 0


register_counter("leads", _count_leads)
register_counter("users", _count_users)
register_counter("workflows", _count_workflows)
CUMULATIVE = {"storage_mb"}  # metered but not reset per period


def month_bounds(period: str | None = None) -> tuple[datetime, datetime, str]:
    if period:
        try:
            start = datetime.strptime(period, "%Y-%m").replace(tzinfo=UTC)
        except ValueError as e:
            raise AppError(422, "invalid_period", "period must be YYYY-MM") from e
    else:
        n = utcnow()
        start = datetime(n.year, n.month, 1, tzinfo=UTC)
    end = datetime(start.year + (start.month == 12), start.month % 12 + 1, 1, tzinfo=UTC)
    return start, end, start.strftime("%Y-%m")


def current_usage(db: Session, org_id: uuid.UUID, resource: str, period: str | None = None) -> Decimal:
    if resource in _COUNTERS and period is None:
        return Decimal(_COUNTERS[resource](db, org_id))
    start, end, _ = month_bounds(period)
    q = select(func.coalesce(func.sum(BillingUsage.quantity), 0)).where(
        BillingUsage.organization_id == org_id, BillingUsage.resource == resource)
    if resource not in CUMULATIVE:
        q = q.where(BillingUsage.created_at >= start, BillingUsage.created_at < end)
    return Decimal(str(db.scalar(q) or 0))


def _alert(db, org_id, kind, resource, value: Decimal, limit: Decimal, thresholds) -> list[int]:
    if not limit or limit <= 0:
        return []
    _, _, period = month_bounds()
    pct = value / limit * 100
    have = set(db.scalars(select(BudgetAlert.threshold).where(
        BudgetAlert.organization_id == org_id, BudgetAlert.kind == kind, BudgetAlert.resource == resource,
        BudgetAlert.period == period)))
    fired = []
    for t in sorted(int(x) for x in thresholds):
        if pct >= t and t not in have:
            db.add(BudgetAlert(organization_id=org_id, kind=kind, resource=resource, period=period, threshold=t,
                               value=value, limit_value=limit))
            fired.append(t)
    return fired


def enforce_limit(db: Session, org_id: uuid.UUID, resource: str, increment: float | Decimal = 1) -> None:
    """Raise 402 if adding `increment` of `resource` would exceed the plan limit or the subscription is inactive.
    Records plan-limit alerts at 50/80/100% of the limit (once per month per threshold)."""
    if resource not in RESOURCES:
        raise ValueError(f"unknown billable resource {resource}")
    sub = get_subscription(db, org_id)
    if sub.status in INACTIVE:
        raise AppError(402, "subscription_inactive",
                       "Your subscription is not active (trial expired or payment due). Choose a plan to continue.",
                       {"status": sub.status})
    limit = (plan_of(db, sub).limits or {}).get(resource)
    if limit is None:
        return
    projected = current_usage(db, org_id, resource) + Decimal(str(increment))
    if projected > Decimal(limit):
        raise AppError(402, "plan_limit_reached", f"Your plan allows {limit} {resource}. Upgrade to add more.",
                       {"resource": resource, "limit": limit, "used": float(projected - Decimal(str(increment)))})
    _alert(db, org_id, "plan_limit", resource, projected, Decimal(limit), (50, 80, 100))


def limit_guard(resource: str, increment: float = 1):
    """FastAPI dependency: `ctx: TenantContext = Depends(limit_guard("leads"))` (combine with require_permission)."""

    def dep(ctx: TenantContext = Depends(get_tenant), db: Session = Depends(get_db)) -> TenantContext:
        enforce_limit(db, ctx.organization_id, resource, increment)
        return ctx

    return dep


def get_budget(db: Session, org_id: uuid.UUID) -> Budget | None:
    return db.scalar(select(Budget).where(Budget.organization_id == org_id))


def month_spend(db: Session, org_id: uuid.UUID, period: str | None = None) -> Decimal:
    start, end, _ = month_bounds(period)
    return _money(db.scalar(select(func.coalesce(func.sum(BillingUsage.cost), 0)).where(
        BillingUsage.organization_id == org_id, BillingUsage.created_at >= start, BillingUsage.created_at < end)) or 0)


def check_budget(db: Session, org_id: uuid.UUID, cost: Decimal | float = 0) -> None:
    b = get_budget(db, org_id)
    if b is None or b.monthly_limit is None or not b.hard_stop:
        return
    if month_spend(db, org_id) + _money(Decimal(str(cost))) > b.monthly_limit:
        raise AppError(402, "budget_exceeded", "Monthly budget reached (hard stop is enabled)",
                       {"monthly_limit": str(b.monthly_limit)})


def record_usage(db: Session, org_id: uuid.UUID, resource: str, quantity: float | Decimal = 1,
                 cost: float | Decimal = 0, *, campaign_id: uuid.UUID | None = None,
                 lead_id: uuid.UUID | None = None, meta: dict | None = None) -> BillingUsage:
    """Append a usage row, enforcing the budget hard stop and firing budget / plan-limit alerts."""
    if resource not in RESOURCES:
        raise ValueError(f"unknown billable resource {resource}")
    cost_d = _money(Decimal(str(cost)))
    check_budget(db, org_id, cost_d)
    row = BillingUsage(organization_id=org_id, resource=resource, quantity=Decimal(str(quantity)), cost=cost_d,
                       campaign_id=campaign_id, lead_id=lead_id, meta=meta)
    db.add(row)
    db.flush()
    b = get_budget(db, org_id)
    if b is not None and b.monthly_limit:
        _alert(db, org_id, "budget", "spend", month_spend(db, org_id), b.monthly_limit,
               b.alert_thresholds or (50, 80, 100))
    if resource not in _COUNTERS:
        limit = (plan_of(db, get_subscription(db, org_id)).limits or {}).get(resource)
        if limit:
            _alert(db, org_id, "plan_limit", resource, current_usage(db, org_id, resource), Decimal(limit),
                   (50, 80, 100))
    return row


# ---------------------------------------------------------------- plan changes
def change_plan(db: Session, org_id: uuid.UUID, code: str) -> tuple[Subscription, Invoice | None, dict]:
    sub = get_subscription(db, org_id)
    old, new = plan_of(db, sub), get_plan(db, code)
    if code == "free_trial":
        raise AppError(422, "plan_not_selectable", "The Free Trial cannot be selected")
    if new.id == old.id and sub.status not in INACTIVE:
        raise AppError(409, "same_plan", "Already on this plan")
    over = {}
    for r, lim in (new.limits or {}).items():
        if lim is not None and r in _COUNTERS and current_usage(db, org_id, r) > lim:
            over[r] = {"used": int(current_usage(db, org_id, r)), "limit": lim}
    if over:
        raise AppError(409, "downgrade_blocked", "Current usage exceeds the target plan's limits", over)
    now = utcnow()
    start, end = _aware(sub.current_period_start), _aware(sub.current_period_end)
    proration: dict = {"type": "new_period"}
    if sub.status in {"trialing", *INACTIVE} or old.price_monthly == 0 or end <= now:
        lines = [(f"{new.name} plan ({now:%Y-%m-%d} - {now + timedelta(days=PERIOD_DAYS):%Y-%m-%d})",
                  new.price_monthly)]
        sub.current_period_start, sub.current_period_end = now, now + timedelta(days=PERIOD_DAYS)
        inv = _new_invoice(db, org_id, lines, period_start=now, period_end=sub.current_period_end)
    else:
        frac = Decimal(str(max((end - now).total_seconds(), 0) / max((end - start).total_seconds(), 1)))
        credit, charge = _money(old.price_monthly * frac), _money(new.price_monthly * frac)
        proration = {"type": "prorated", "fraction_remaining": float(round(frac, 4)), "credit": str(credit),
                     "charge": str(charge), "net": str(charge - credit)}
        notes = None if charge >= credit else f"Unused credit of {credit - charge} USD retained on account"
        inv = _new_invoice(db, org_id, [(f"Unused time on {old.name}", -credit),
                                        (f"Remaining time on {new.name}", charge)],
                           period_start=now, period_end=end, notes=notes)
    sub.plan_id, sub.status, sub.trial_end, sub.cancel_at_period_end = new.id, "active", None, False
    db.flush()
    return sub, inv, proration
