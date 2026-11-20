import random
import uuid

from sqlalchemy import select

from app.core.db import tenant_session
from app.modules.learning import service as svc
from app.modules.learning.models import CallLearning, ScriptVariant
from tests.test_telephony import C, _dialed, _env, _hook  # noqa: F401  (_env: autouse telephony fixture)

A = "/api/v1/agents"


def test_auto_reward_rules():
    assert svc.auto_reward("high", None, False) == (1, "interested")
    assert svc.auto_reward("unknown", "Send a proposal", False) == (1, "interested")
    assert svc.auto_reward("none", "x", False) == (0, "not_interested")
    assert svc.auto_reward("high", None, True) == (0, "opted_out")
    assert svc.auto_reward("unknown", None, False) == (None, "unclear")


def test_thompson_sampling_prefers_the_winner(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Learn Bandit")
    org, agent = s["org"], uuid.UUID(s["agent"])
    good = client.post(f"{A}/{agent}/variants", headers=s["h"], json={"name": "Good", "opening": "Hi, quick question?"})
    bad = client.post(f"{A}/{agent}/variants", headers=s["h"], json={"name": "Bad", "opening": "Hello, buy now please"})
    assert good.status_code == bad.status_code == 201
    g, b = uuid.UUID(good.json()["id"]), uuid.UUID(bad.json()["id"])
    with tenant_session(org) as db:
        # With no history both are tried.
        picks = {svc.choose_variant(db, org, agent, random.Random(i)).id for i in range(40)}  # noqa: S311
        assert picks == {g, b}
    with tenant_session(org) as db:
        counts = {g: (18, 2), b: (2, 18)}
        monkeypatch.setattr(svc, "_counts", lambda *_: counts)
        rng = random.Random(1)  # noqa: S311
        wins = sum(svc.choose_variant(db, org, agent, rng).id == g for _ in range(200))
        assert wins > 180
        st = svc.stats(db, org, agent)
        top = {v["id"]: v for v in st["variants"]}
        assert top[g]["prob_best"] > 0.95 and top[g]["success_rate"] == 0.9


def test_real_call_uses_variant_and_records_reward_and_feedback(client, monkeypatch):
    s, cid, _ = _dialed(client, monkeypatch, "Learn Call")
    r = client.post(f"{A}/{s['agent']}/variants", headers=s["h"],
                    json={"name": "Warm", "opening": "Hi! Do you have a minute to talk about your website?"})
    vid = r.json()["id"]
    x = _hook(client, "voice", cid, {"CallSid": "CA1"}).text
    assert "Do you have a minute to talk about your website?" in x and "AI assistant" in x
    assert 'voice="Polly.Aditi"' in x  # Indian female voice by default for Indian numbers
    _hook(client, "turn", cid, {"SpeechResult": "Yes we are interested, our budget is 40000 rupees"})
    _hook(client, "status", cid, {"CallSid": "CA1", "CallStatus": "completed", "CallDuration": "60"})
    st = client.get(f"{A}/{s['agent']}/learning", headers=s["h"]).json()
    v = next(v for v in st["variants"] if v["id"] == vid)
    assert v["calls_scored"] == 1 and v["wins"] == 1
    r = client.post(f"{C}/{cid}/feedback", headers=s["h"], json={"good": False, "note": "Too pushy"})
    assert r.json() == {"reward": 0, "label": "rated_bad"}
    with tenant_session(s["org"]) as db:
        row = db.scalar(select(CallLearning).where(CallLearning.call_id == uuid.UUID(cid)))
        assert row.reward_source == "human" and row.variant_id == uuid.UUID(vid)
        assert db.scalar(select(ScriptVariant).where(ScriptVariant.id == uuid.UUID(vid))).active


def test_learning_is_tenant_isolated(client, monkeypatch):
    s, _cid, _ = _dialed(client, monkeypatch, "Learn Iso")
    other, _c2, _ = _dialed(client, monkeypatch, "Learn Other")
    assert client.get(f"{A}/{s['agent']}/learning", headers=other["h"]).status_code == 404
    assert client.post(f"{A}/{s['agent']}/variants", headers=other["h"],
                       json={"name": "x", "opening": "hello there"}).status_code == 404
