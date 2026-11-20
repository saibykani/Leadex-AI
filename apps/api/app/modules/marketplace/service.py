"""Marketplace persistence helpers: tenant-scoped lookups, category seeding, matching, ledger maths."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.identity.models import OrganizationMembership
from app.modules.marketplace import engine
from app.modules.marketplace.models import (
    CommissionDispute,
    CommissionTransaction,
    CustomerRequirement,
    MatchingSettings,
    ProviderCategory,
    ProviderMatch,
    Referral,
    ReferralEvent,
    ServiceCategory,
    ServiceProvider,
)

LEDGER_KINDS = ("accrual", "invoice", "payment", "settlement", "refund", "dispute", "reversal")


def get_in_org(db: Session, ctx: TenantContext, model, obj_id: uuid.UUID, label: str):
    obj = db.scalar(select(model).where(model.id == obj_id, model.organization_id == ctx.organization_id))
    if obj is None:
        raise AppError(404, "not_found", f"{label} not found")
    return obj


def ensure_categories(db: Session, org_id: uuid.UUID) -> None:
    """Seed the default (system) categories for a tenant on first use; tenants may add their own."""
    have = set(db.scalars(select(ServiceCategory.slug).where(ServiceCategory.organization_id == org_id)))
    missing = [(s, n) for s, n in engine.DEFAULT_CATEGORIES if s not in have]
    for slug, name in missing:
        db.add(ServiceCategory(organization_id=org_id, slug=slug, name=name, is_system=True))
    if missing:
        db.flush()


def ensure_member(db: Session, org_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    m = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "active"))
    if m is None:
        raise AppError(422, "invalid_user", "portal_user_id must be an active member of this organization")


def provider_category_ids(db: Session, provider_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(ProviderCategory.category_id).where(ProviderCategory.provider_id == provider_id)))


def set_provider_categories(db: Session, ctx: TenantContext, provider: ServiceProvider, ids: list[uuid.UUID]):
    valid = set(db.scalars(select(ServiceCategory.id).where(ServiceCategory.organization_id == ctx.organization_id,
                                                            ServiceCategory.id.in_(ids))))
    if len(valid) != len(set(ids)):
        raise AppError(422, "invalid_category", "One or more category_ids do not exist in this organization")
    for pc in db.scalars(select(ProviderCategory).where(ProviderCategory.provider_id == provider.id)):
        db.delete(pc)
    db.flush()
    for cid in valid:
        db.add(ProviderCategory(organization_id=ctx.organization_id, provider_id=provider.id, category_id=cid))


def weights_for(db: Session, org_id: uuid.UUID) -> dict[str, int]:
    row = db.scalar(select(MatchingSettings).where(MatchingSettings.organization_id == org_id))
    return {**engine.DEFAULT_WEIGHTS, **(row.weights if row else {})}


def run_matching(db: Session, ctx: TenantContext, req: CustomerRequirement, limit: int = 20) -> list[ProviderMatch]:
    weights = weights_for(db, ctx.organization_id)
    providers = db.scalars(select(ServiceProvider).where(ServiceProvider.organization_id == ctx.organization_id,
                                                         ServiceProvider.verification_status != "rejected")).all()
    rv = engine.ReqView(req.category_id, req.city, req.country, req.budget_min, req.budget_max, req.currency,
                        req.preferences)
    scored = []
    for p in providers:
        text = " ".join(str(x) for x in (p.business_name, p.description, p.portfolio, p.credentials) if x).lower()
        pv = engine.ProvView(set(provider_category_ids(db, p.id)), p.service_areas, p.price_min, p.price_max,
                             p.currency, p.availability, p.experience_years, p.verification_status, text)
        score, expl = engine.score_match(rv, pv, weights)
        expl["provider_name"] = p.business_name
        scored.append((score, p.verification_status == "verified", p, expl))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    for old in db.scalars(select(ProviderMatch).where(ProviderMatch.requirement_id == req.id)):
        db.delete(old)
    db.flush()
    out = []
    for score, _, p, expl in scored[:limit]:
        m = ProviderMatch(organization_id=ctx.organization_id, requirement_id=req.id, provider_id=p.id,
                          score=score, explanation=expl)
        db.add(m)
        out.append(m)
    if out and req.status == "open":
        req.status = "matched"
    db.flush()
    return out


def add_event(db: Session, org_id: uuid.UUID, user_id, ref: Referral, type_: str, frm=None, to=None, note=None):
    db.add(ReferralEvent(organization_id=org_id, referral_id=ref.id, actor_user_id=user_id, type=type_,
                         from_status=frm, to_status=to, note=note))


def transition(db: Session, org_id, user_id, ref: Referral, new: str, note: str | None,
               deal_value: Decimal | None = None) -> None:
    engine.check_transition(ref.status, new)
    old = ref.status
    ref.status = new
    if deal_value is not None:
        ref.deal_value = deal_value
    add_event(db, org_id, user_id, ref, "status.changed", old, new, note)


# ---------------------------------------------------------------- ledger
def ledger(db: Session, org_id: uuid.UUID, referral_ids: list[uuid.UUID] | None = None):
    q = select(CommissionTransaction).where(CommissionTransaction.organization_id == org_id)
    if referral_ids is not None:
        q = q.where(CommissionTransaction.referral_id.in_(referral_ids))
    return db.scalars(q.order_by(CommissionTransaction.created_at, CommissionTransaction.id)).all()


def balances(txs) -> list[dict]:
    by: dict[str, dict[str, Decimal]] = {}
    for t in txs:
        b = by.setdefault(t.currency, dict.fromkeys(LEDGER_KINDS, Decimal(0)))
        b[t.kind] += Decimal(t.amount)
    out = []
    for cur, b in sorted(by.items()):
        net = b["accrual"] - b["reversal"]
        out.append({"currency": cur, "accrued": b["accrual"], "reversed": b["reversal"], "invoiced": b["invoice"],
                    "paid": b["payment"], "refunded": b["refund"], "settled": b["settlement"],
                    "outstanding": net - (b["payment"] - b["refund"])})
    return out


def referral_position(db: Session, org_id: uuid.UUID, ref: Referral) -> dict[str, Decimal | str | None]:
    txs = ledger(db, org_id, [ref.id])
    b = balances(txs)
    if not b:
        return {"currency": None, "net": Decimal(0), "invoiced": Decimal(0), "paid": Decimal(0),
                "settled": Decimal(0), "agreement_id": None}
    if len(b) > 1:
        raise AppError(409, "currency_mismatch", "Referral ledger has multiple currencies")
    x = b[0]
    accrual = next((t for t in txs if t.kind == "accrual"), None)
    return {"currency": x["currency"], "net": x["accrued"] - x["reversed"], "invoiced": x["invoiced"],
            "paid": x["paid"] - x["refunded"], "settled": x["settled"],
            "agreement_id": accrual.agreement_id if accrual else None}


def settlement_blockers(db: Session, org_id: uuid.UUID, ref: Referral, conditions: dict | None) -> list[str]:
    c = {"requires_converted": True, "requires_invoice_paid": True, "no_open_disputes": True, **(conditions or {})}
    pos = referral_position(db, org_id, ref)
    blockers = []
    if pos["net"] <= 0:
        blockers.append("No commission has been accrued")
    if c["requires_converted"] and ref.status != "converted":
        blockers.append("Referral is not converted")
    if c["requires_invoice_paid"] and (pos["invoiced"] < pos["net"] or pos["paid"] < pos["net"] or pos["net"] <= 0):
        blockers.append("Commission has not been fully invoiced and paid")
    if c["no_open_disputes"] and db.scalar(select(CommissionDispute.id).where(
            CommissionDispute.referral_id == ref.id, CommissionDispute.status == "open").limit(1)):
        blockers.append("There is an open dispute")
    if pos["net"] > 0 and pos["settled"] >= pos["net"]:
        blockers.append("Commission is already settled")
    return blockers
