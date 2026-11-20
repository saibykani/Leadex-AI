"""Self-improving call agent.

1. Opening selection: Thompson sampling (Beta-Bernoulli bandit) over an agent's active opening variants.
   Each variant's success rate gets a Beta(1 + wins, 1 + losses) posterior; per call we sample every posterior and
   use the highest draw. Good openings get used more, new ones still get tried. Real statistics, no fabricated data:
   with no history every variant is equally likely.
2. Reward: from the extracted call outcome (interest high/medium or a concrete next step => 1; low/none, opt-out => 0),
   overridable by a human rating, which always wins.
3. Example memory: agent replies from rewarded calls are given to the model as style examples on later calls.
"""
import random
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.learning.models import CallLearning, ScriptVariant

POSITIVE_INTEREST = {"high", "medium"}


def _counts(db: Session, org: uuid.UUID, agent_id: uuid.UUID) -> dict:
    rows = db.execute(select(CallLearning.variant_id, CallLearning.reward, func.count())
                      .where(CallLearning.organization_id == org, CallLearning.agent_id == agent_id,
                             CallLearning.reward.is_not(None))
                      .group_by(CallLearning.variant_id, CallLearning.reward)).all()
    out: dict = {}
    for vid, reward, n in rows:
        w, losses = out.get(vid, (0, 0))
        out[vid] = (w + n, losses) if reward == 1 else (w, losses + n)
    return out


def choose_variant(db: Session, org: uuid.UUID, agent_id: uuid.UUID, rng: random.Random | None = None):
    variants = list(db.scalars(select(ScriptVariant).where(ScriptVariant.organization_id == org,
                                                          ScriptVariant.agent_id == agent_id,
                                                          ScriptVariant.active.is_(True))))
    if not variants:
        return None
    rng = rng or random.Random()  # noqa: S311 - statistical sampling, not security
    counts = _counts(db, org, agent_id)
    best, best_draw = None, -1.0
    for v in variants:
        w, losses = counts.get(v.id, (0, 0))
        draw = rng.betavariate(1 + w, 1 + losses)
        if draw > best_draw:
            best, best_draw = v, draw
    return best


def start_call(db: Session, call, rng: random.Random | None = None) -> ScriptVariant | None:
    """Record the learning row for a call (idempotent) and return the chosen opening variant, if any."""
    row = db.scalar(select(CallLearning).where(CallLearning.call_id == call.id))
    if row is not None:
        return db.get(ScriptVariant, row.variant_id) if row.variant_id else None
    v = choose_variant(db, call.organization_id, call.agent_id, rng)
    db.add(CallLearning(organization_id=call.organization_id, agent_id=call.agent_id, call_id=call.id,
                        variant_id=v.id if v else None))
    db.flush()
    return v


def auto_reward(interest: str | None, next_step: str | None, opted_out: bool) -> tuple[int | None, str]:
    if opted_out:
        return 0, "opted_out"
    if interest in POSITIVE_INTEREST or (next_step and interest not in ("none", "low")):
        return 1, "interested"
    if interest in ("low", "none"):
        return 0, "not_interested"
    return None, "unclear"


def record_outcome(db: Session, call, *, interest: str | None, next_step: str | None, opted_out: bool,
                   had_conversation: bool) -> None:
    row = db.scalar(select(CallLearning).where(CallLearning.call_id == call.id))
    if row is None:
        row = CallLearning(organization_id=call.organization_id, agent_id=call.agent_id, call_id=call.id)
        db.add(row)
    if row.reward_source == "human":
        return
    if not had_conversation:
        row.reward, row.label, row.reward_source = None, "no_conversation", "auto"
    else:
        row.reward, row.label = auto_reward(interest, next_step, opted_out)
        row.reward_source = "auto"
    row.updated_at = utcnow()


def human_feedback(db: Session, org: uuid.UUID, call, good: bool, note: str | None) -> CallLearning:
    row = db.scalar(select(CallLearning).where(CallLearning.organization_id == org, CallLearning.call_id == call.id))
    if row is None:
        row = CallLearning(organization_id=org, agent_id=call.agent_id, call_id=call.id)
        db.add(row)
    row.reward, row.reward_source = (1 if good else 0), "human"
    row.label = "rated_good" if good else "rated_bad"
    row.feedback_note = (note or "")[:1000] or None
    row.updated_at = utcnow()
    return row


def winning_examples(db: Session, org: uuid.UUID, agent_id: uuid.UUID, limit: int = 3) -> list[tuple[str, str]]:
    """(customer said, agent replied) pairs from recent rewarded calls of this agent."""
    from app.modules.voice.models import CallTranscript

    call_ids = list(db.scalars(select(CallLearning.call_id).where(
        CallLearning.organization_id == org, CallLearning.agent_id == agent_id, CallLearning.reward == 1)
        .order_by(CallLearning.created_at.desc()).limit(10)))
    pairs: list[tuple[str, str]] = []
    for cid in call_ids:
        turns = list(db.scalars(select(CallTranscript).where(CallTranscript.organization_id == org,
                                                             CallTranscript.call_id == cid)
                                .order_by(CallTranscript.seq)))
        for a, b in zip(turns, turns[1:], strict=False):
            if a.speaker == "contact" and b.speaker == "agent" and len(a.text) > 8:
                pairs.append((a.text[:200], b.text[:300]))
                break
        if len(pairs) >= limit:
            break
    return pairs


def examples_prompt(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    lines = ["Examples of replies that worked well on earlier calls (match their tone and brevity; "
             "never copy facts that are not true for this customer):"]
    lines += [f'- Customer: "{c}" -> You: "{a}"' for c, a in pairs]
    return "\n".join(lines)


def stats(db: Session, org: uuid.UUID, agent_id: uuid.UUID, draws: int = 2000, seed: int = 7) -> dict:
    variants = list(db.scalars(select(ScriptVariant).where(ScriptVariant.organization_id == org,
                                                          ScriptVariant.agent_id == agent_id)
                               .order_by(ScriptVariant.created_at)))
    counts = _counts(db, org, agent_id)
    active = [v for v in variants if v.active]
    rng = random.Random(seed)  # noqa: S311
    best_count = {v.id: 0 for v in active}
    if active:
        for _ in range(draws):
            pick = max(active, key=lambda v: rng.betavariate(1 + counts.get(v.id, (0, 0))[0],
                                                             1 + counts.get(v.id, (0, 0))[1]))
            best_count[pick.id] += 1
    out = []
    for v in variants:
        w, losses = counts.get(v.id, (0, 0))
        n = w + losses
        out.append({"id": v.id, "name": v.name, "opening": v.opening, "active": v.active, "calls_scored": n,
                    "wins": w, "success_rate": (w / n) if n else None,
                    "posterior_mean": (1 + w) / (2 + n),
                    "prob_best": (best_count.get(v.id, 0) / draws) if v.active and active else None})
    totals = db.execute(select(CallLearning.label, func.count()).where(
        CallLearning.organization_id == org, CallLearning.agent_id == agent_id).group_by(CallLearning.label)).all()
    w0, l0 = counts.get(None, (0, 0))
    return {"variants": out, "baseline": {"calls_scored": w0 + l0, "wins": w0},
            "labels": {k or "pending": n for k, n in totals}}
