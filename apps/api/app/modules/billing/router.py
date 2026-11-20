import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.billing import service as svc
from app.modules.billing.models import BillingUsage, Budget, BudgetAlert, Invoice, InvoiceLine, Payment, Plan
from app.modules.billing.providers import PROVIDERS
from app.modules.billing.schemas import (
    AlertOut,
    BudgetBody,
    BudgetOut,
    ChangePlan,
    ChangeResult,
    InvoiceLineOut,
    InvoiceOut,
    PayBody,
    PaymentOut,
    PlanOut,
    ProviderOut,
    SubscriptionOut,
    UsageItem,
    UsageOut,
)
from app.modules.identity.schemas import Page

router = APIRouter(prefix="/billing", tags=["billing"])
READ = require_permission("org:read")
MANAGE = require_permission("billing:manage")


def _sub_out(db, sub) -> SubscriptionOut:
    return SubscriptionOut(id=sub.id, status=sub.status, plan=PlanOut.model_validate(svc.plan_of(db, sub)),
                           current_period_start=sub.current_period_start, current_period_end=sub.current_period_end,
                           trial_end=sub.trial_end, cancel_at_period_end=sub.cancel_at_period_end)


def _inv_out(db, inv: Invoice) -> InvoiceOut:
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id,
                                                 InvoiceLine.organization_id == inv.organization_id)).all()
    out = InvoiceOut.model_validate(inv)
    out.lines = [InvoiceLineOut.model_validate(x) for x in lines]
    return out


@router.get("/plans", response_model=list[PlanOut])
def plans(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    svc.ensure_plans(db)
    db.commit()
    return db.scalars(select(Plan).order_by(Plan.sort_order)).all()


@router.get("/subscription", response_model=SubscriptionOut)
def subscription(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    sub = svc.get_subscription(db, ctx.organization_id)
    db.commit()
    return _sub_out(db, sub)


@router.post("/subscription/change", response_model=ChangeResult)
def change(body: ChangePlan, request: Request, ctx: TenantContext = Depends(MANAGE), db: Session = Depends(get_db)):
    old = svc.plan_of(db, svc.get_subscription(db, ctx.organization_id)).code
    sub, inv, proration = svc.change_plan(db, ctx.organization_id, body.plan_code)
    audit(db, "billing.plan_change", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="subscription",
          entity_id=sub.id, data={"from": old, "to": body.plan_code, "proration": proration}, request=request)
    db.commit()
    return ChangeResult(subscription=_sub_out(db, sub), invoice=_inv_out(db, inv) if inv else None,
                        proration=proration)


@router.post("/subscription/cancel", response_model=SubscriptionOut)
def cancel(request: Request, ctx: TenantContext = Depends(MANAGE), db: Session = Depends(get_db)):
    sub = svc.get_subscription(db, ctx.organization_id)
    sub.cancel_at_period_end = True
    audit(db, "billing.cancel", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="subscription",
          entity_id=sub.id, request=request)
    db.commit()
    return _sub_out(db, sub)


def _level(pct):
    if pct is None:
        return "unlimited"
    return "exceeded" if pct >= 100 else "critical" if pct >= 80 else "warning" if pct >= 50 else "ok"


@router.get("/usage", response_model=UsageOut)
def usage(period: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), ctx: TenantContext = Depends(READ),
          db: Session = Depends(get_db)):
    sub = svc.get_subscription(db, ctx.organization_id)
    limits = svc.plan_of(db, sub).limits or {}
    start, end, label = svc.month_bounds(period)
    costs = dict(db.execute(select(BillingUsage.resource, func.coalesce(func.sum(BillingUsage.cost), 0)).where(
        BillingUsage.organization_id == ctx.organization_id, BillingUsage.created_at >= start,
        BillingUsage.created_at < end).group_by(BillingUsage.resource)).all())
    items = []
    for r in svc.RESOURCES:
        used = float(svc.current_usage(db, ctx.organization_id, r, period if r not in svc._COUNTERS else None))
        lim = limits.get(r)
        pct = round(used / lim * 100, 1) if lim else None
        items.append(UsageItem(resource=r, used=used, limit=lim, percent=pct, level=_level(pct),
                               cost=Decimal(str(costs.get(r, 0))).quantize(svc.CENT)))
    db.commit()
    return UsageOut(period=label, items=items, total_cost=sum((i.cost for i in items), Decimal("0.00")))


def _budget_out(db, org_id) -> BudgetOut:
    b = svc.get_budget(db, org_id)
    alerts = db.scalars(select(BudgetAlert).where(BudgetAlert.organization_id == org_id)
                        .order_by(BudgetAlert.created_at.desc()).limit(50)).all()
    base = BudgetBody(monthly_limit=b.monthly_limit, alert_thresholds=b.alert_thresholds or [50, 80, 100],
                      hard_stop=b.hard_stop, paid_fallback_enabled=b.paid_fallback_enabled) if b else BudgetBody()
    return BudgetOut(**base.model_dump(), month_spend=svc.month_spend(db, org_id),
                     alerts=[AlertOut.model_validate(a) for a in alerts])


@router.get("/budget", response_model=BudgetOut)
def get_budget(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return _budget_out(db, ctx.organization_id)


@router.put("/budget", response_model=BudgetOut)
def put_budget(body: BudgetBody, request: Request, ctx: TenantContext = Depends(MANAGE),
               db: Session = Depends(get_db)):
    b = svc.get_budget(db, ctx.organization_id)
    if b is None:
        b = Budget(organization_id=ctx.organization_id)
        db.add(b)
    b.monthly_limit, b.alert_thresholds = body.monthly_limit, body.alert_thresholds
    b.hard_stop, b.paid_fallback_enabled = body.hard_stop, body.paid_fallback_enabled
    audit(db, "billing.budget_update", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="budget",
          data={**body.model_dump(mode="json")}, request=request)
    db.commit()
    return _budget_out(db, ctx.organization_id)


@router.get("/alerts", response_model=list[AlertOut])
def alerts(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(select(BudgetAlert).where(BudgetAlert.organization_id == ctx.organization_id)
                      .order_by(BudgetAlert.created_at.desc()).limit(200)).all()


@router.get("/invoices", response_model=Page[InvoiceOut])
def invoices(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db), page: int = Query(1, ge=1),
             page_size: int = Query(25, ge=1, le=100)):
    svc.get_subscription(db, ctx.organization_id)  # applies renewals
    db.commit()
    base = select(Invoice).where(Invoice.organization_id == ctx.organization_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Invoice.created_at.desc(), Invoice.number.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[InvoiceOut](items=[_inv_out(db, r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/invoices/{invoice_id}/pay", response_model=PaymentOut)
def pay(invoice_id: uuid.UUID, request: Request, body: PayBody = PayBody(), ctx: TenantContext = Depends(MANAGE),
        db: Session = Depends(get_db)):
    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == ctx.organization_id))
    if inv is None:
        raise AppError(404, "not_found", "Invoice not found")
    if inv.status != "open":
        raise AppError(409, "invoice_not_open", f"Invoice is {inv.status}")
    provider = PROVIDERS.get(body.provider)
    if provider is None:
        raise AppError(422, "unknown_provider", f"Unknown provider '{body.provider}'")
    if provider.status() in {"not_configured", "disabled"}:
        raise AppError(422, "provider_not_configured", f"Payment provider '{body.provider}' is {provider.status()}")
    res = provider.charge(inv.total, inv.currency, inv.number)
    p = Payment(organization_id=ctx.organization_id, invoice_id=inv.id, provider=provider.name,
                provider_reference=res.reference, amount=inv.total, currency=inv.currency, status=res.status,
                simulated=res.simulated, error=res.error)
    db.add(p)
    if res.status == "succeeded":
        inv.status, inv.paid_at = "paid", utcnow()
        sub = svc.get_subscription(db, ctx.organization_id)
        if sub.status == "past_due":
            sub.status = "active"
    audit(db, "billing.invoice_pay", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="invoice",
          entity_id=inv.id, data={"provider": provider.name, "status": res.status, "simulated": res.simulated},
          request=request)
    db.commit()
    out = PaymentOut.model_validate(p)
    out.checkout_url = res.checkout_url
    return out


@router.get("/providers", response_model=list[ProviderOut])
def providers(ctx: TenantContext = Depends(READ)):
    labels = {"simulated": "Simulated (test only - no money moves)", "stripe": "Stripe", "razorpay": "Razorpay"}
    return [ProviderOut(name=n, status=p.status(), label=labels[n]) for n, p in PROVIDERS.items()]
from app.modules.billing.webhooks import router as webhook_router  # noqa: E402

extra_routers = [webhook_router]
