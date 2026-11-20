"""Pure domain logic: matching score, referral lifecycle, commission arithmetic. No I/O."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import AppError

# ---------------------------------------------------------------- categories
DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("real-estate", "Real estate"),
    ("property-consulting", "Property consulting"),
    ("architecture", "Architecture"),
    ("interior-design", "Interior design"),
    ("construction", "Construction"),
    ("civil-engineering", "Civil engineering"),
    ("contractors", "Contractors"),
    ("property-development", "Property development"),
    ("home-renovation", "Home renovation"),
)

# ---------------------------------------------------------------- matching
DEFAULT_WEIGHTS: dict[str, int] = {
    "category": 25, "location": 20, "budget": 15, "availability": 10,
    "experience": 10, "verification": 15, "preferences": 5,
}
UNVERIFIED_PENALTY = Decimal("0.85")  # non-verified providers are always ranked below an equal verified one


@dataclass
class ReqView:
    category_id: object
    city: str | None
    country: str | None
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str
    preferences: dict | None


@dataclass
class ProvView:
    category_ids: set
    service_areas: list | None
    price_min: Decimal | None
    price_max: Decimal | None
    currency: str
    availability: str
    experience_years: int | None
    verification_status: str
    text: str


def _norm(s) -> str:
    return (s or "").strip().lower()


def _factor(score: float, reason: str) -> dict:
    return {"score": round(max(0.0, min(1.0, score)), 3), "reason": reason}


def score_match(req: ReqView, prov: ProvView, weights: dict[str, int]) -> tuple[int, dict]:
    f: dict[str, dict] = {}
    f["category"] = (_factor(1, "Provider offers the requested service category")
                     if req.category_id in prov.category_ids
                     else _factor(0, "Provider does not list the requested service category"))

    areas = prov.service_areas or []
    cities = {_norm(a.get("city")) for a in areas if isinstance(a, dict)}
    countries = {_norm(a.get("country")) for a in areas if isinstance(a, dict)}
    if not req.city and not req.country:
        f["location"] = _factor(0.5, "Requirement has no location; neutral score")
    elif req.city and _norm(req.city) in cities:
        f["location"] = _factor(1, f"Serves {req.city}")
    elif req.country and _norm(req.country) in countries:
        f["location"] = _factor(0.6, f"Serves {req.country.upper()} but not {req.city or 'the city'} specifically")
    elif not areas:
        f["location"] = _factor(0.2, "Provider has not declared service areas")
    else:
        f["location"] = _factor(0, "Outside the provider's declared service areas")

    if prov.price_min is None and prov.price_max is None:
        f["budget"] = _factor(0.5, "Provider has no pricing range on file; neutral score")
    elif req.budget_min is None and req.budget_max is None:
        f["budget"] = _factor(0.5, "Requirement has no budget; neutral score")
    elif req.currency != prov.currency:
        f["budget"] = _factor(0.3, f"Currencies differ ({req.currency} vs {prov.currency}); not compared")
    else:
        rlo, rhi = req.budget_min or Decimal(0), req.budget_max or req.budget_min
        plo, phi = prov.price_min or Decimal(0), prov.price_max or prov.price_min
        if rhi is not None and plo > rhi:
            f["budget"] = _factor(0.1, f"Provider's minimum {plo} {prov.currency} exceeds budget {rhi}")
        elif phi is not None and phi < rlo:
            f["budget"] = _factor(0.6, f"Provider's typical range (up to {phi}) is below the budget minimum")
        else:
            f["budget"] = _factor(1, "Budget overlaps the provider's pricing range")

    f["availability"] = {
        "available": _factor(1, "Currently available"),
        "limited": _factor(0.5, "Limited availability"),
    }.get(prov.availability, _factor(0, "Currently unavailable"))

    yrs = prov.experience_years
    f["experience"] = (_factor(0.3, "Experience not stated") if yrs is None
                       else _factor(min(yrs / 10, 1), f"{yrs} years of experience (10+ scores full)"))

    f["verification"] = {
        "verified": _factor(1, "Verified (manual review with recorded evidence)"),
        "pending": _factor(0.4, "Verification pending — not yet verified"),
    }.get(prov.verification_status, _factor(0, "Unverified — credentials have not been checked"))

    prefs = req.preferences or {}
    checks: list[tuple[bool, str]] = []
    if prefs.get("verified_only"):
        checks.append((prov.verification_status == "verified", "verified only"))
    if prefs.get("min_experience_years") is not None:
        checks.append(((yrs or 0) >= int(prefs["min_experience_years"]),
                       f"at least {prefs['min_experience_years']} years experience"))
    for kw in prefs.get("keywords") or []:
        checks.append((_norm(kw) in prov.text, f"mentions '{kw}'"))
    if not checks:
        f["preferences"] = _factor(1, "No specific preferences")
    else:
        ok = [d for good, d in checks if good]
        miss = [d for good, d in checks if not good]
        reason = "Meets: " + (", ".join(ok) or "none")
        if miss:
            reason += "; misses: " + ", ".join(miss)
        f["preferences"] = _factor(len(ok) / len(checks), reason)

    total_w = sum(max(0, int(weights.get(k, 0))) for k in f) or 1
    raw = sum(Decimal(str(f[k]["score"])) * max(0, int(weights.get(k, 0))) for k in f) / total_w
    for k in f:
        f[k]["weight"] = int(weights.get(k, 0))
    flagged = prov.verification_status != "verified"
    if flagged:
        raw *= UNVERIFIED_PENALTY
    score = int((raw * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return score, {"factors": f, "unverified_flag": flagged,
                   "penalty": str(UNVERIFIED_PENALTY) if flagged else None}


# ---------------------------------------------------------------- referral lifecycle
REFERRAL_STATUSES = ("requirement_received", "matched", "invited", "accepted", "introduced", "meeting",
                     "quotation", "negotiation", "converted", "declined", "lost")
TRANSITIONS: dict[str, frozenset[str]] = {
    "requirement_received": frozenset({"matched", "declined", "lost"}),
    "matched": frozenset({"invited", "declined", "lost"}),
    "invited": frozenset({"accepted", "declined", "lost"}),
    "accepted": frozenset({"introduced", "lost"}),
    "introduced": frozenset({"meeting", "quotation", "lost"}),
    "meeting": frozenset({"quotation", "lost"}),
    "quotation": frozenset({"negotiation", "converted", "lost"}),
    "negotiation": frozenset({"quotation", "converted", "lost"}),
    "converted": frozenset(), "declined": frozenset(), "lost": frozenset(),
}
# Statuses a provider-portal user may move their own referral into.
PROVIDER_ALLOWED = frozenset({"accepted", "declined", "meeting", "quotation", "negotiation", "converted", "lost"})


def check_transition(old: str, new: str) -> None:
    if new not in TRANSITIONS:
        raise AppError(422, "invalid_status", f"Unknown status '{new}'", {"allowed": list(REFERRAL_STATUSES)})
    if new not in TRANSITIONS[old]:
        raise AppError(409, "invalid_transition", f"Cannot move referral from '{old}' to '{new}'",
                       {"from": old, "to": new, "allowed": sorted(TRANSITIONS[old])})


# ---------------------------------------------------------------- commissions
CENT = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_splits(splits: list[dict] | None) -> list[dict]:
    out, total, seen = [], Decimal(0), set()
    for s in splits or []:
        party = str(s.get("party", "")).strip()
        pct = Decimal(str(s.get("pct")))
        if not party or pct <= 0 or pct > 100:
            raise AppError(422, "invalid_splits", "Each split needs a party and 0 < pct <= 100")
        if party in seen:
            raise AppError(422, "invalid_splits", f"Duplicate split party '{party}'")
        seen.add(party)
        total += pct
        out.append({"party": party, "pct": str(pct)})
    if total > 100:
        raise AppError(422, "invalid_splits", f"Split percentages sum to {total}%, must be <= 100%")
    return out


def compute_commission(type_: str, value: Decimal | None, deal_value: Decimal | None,
                       negotiated_amount: Decimal | None) -> Decimal:
    if type_ == "fixed":
        return money(value)
    if type_ == "percentage":
        if deal_value is None or deal_value <= 0:
            raise AppError(422, "deal_value_required", "A positive deal_value is required for percentage commissions")
        return money(Decimal(deal_value) * Decimal(value) / 100)
    if type_ == "negotiated":
        if negotiated_amount is None or negotiated_amount <= 0:
            raise AppError(422, "amount_required", "An agreed amount is required for negotiated commissions")
        return money(negotiated_amount)
    raise AppError(422, "invalid_type", f"Unknown commission type '{type_}'")


def split_amount(total: Decimal, splits: list[dict], remainder_party: str = "organization") -> list[dict]:
    """Allocate `total` across split parties using the largest-remainder method on whole cents, so
    every part is a whole cent and the parts always sum exactly to `total`. Any unallocated
    percentage (splits summing to < 100%) goes to `remainder_party`."""
    cents = int(money(total) * 100)
    pcts = [Decimal(s["pct"]) for s in splits]
    shared = int((Decimal(cents) * sum(pcts, Decimal(0)) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    exact = [Decimal(shared) * p / sum(pcts) for p in pcts] if pcts else []
    base = [int(e) for e in exact]  # floor (values are non-negative)
    leftover = shared - sum(base)
    for i in sorted(range(len(exact)), key=lambda i: (exact[i] - base[i], -i), reverse=True)[:leftover]:
        base[i] += 1
    parts = [{"party": s["party"], "pct": s["pct"], "amount": str((Decimal(c) / 100).quantize(CENT))}
             for s, c in zip(splits, base, strict=True)]
    rest = cents - shared
    if rest or not parts:
        parts.append({"party": remainder_party, "pct": str(100 - sum(pcts, Decimal(0))),
                      "amount": str((Decimal(rest) / 100).quantize(CENT))})
    return parts
