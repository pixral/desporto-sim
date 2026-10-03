from __future__ import annotations

import asyncio
import copy
import random
from datetime import datetime

from app.agents import psychology
from app.agents.context import build_tipster_context
from app.agents.policies import tipster_policy
from app.ai.gateway import AIGateway
from app.ai.provider import ModelRequest, ModelResponse
from app.ai.schemas import TipsterDayOutput


async def _first_context(engine):
    """Advance to the first day where some tipster has matches and return (employee, context)."""
    w = engine.world
    captured = {}
    original = engine.gateway.run

    async def spy(**kw):
        if kw["purpose"] == "tipster_day" and "ctx" not in captured:
            captured["ctx"] = kw["context"]
        return await original(**kw)

    engine.gateway.run = spy
    while "ctx" not in captured and w.clock.day_index < 30:
        await engine.step()
    engine.gateway.run = original
    return captured["ctx"]


def test_tipster_policy_output_is_valid_and_within_limits(fresh):
    world, _, engine = fresh()
    ctx = asyncio.run(_first_context(engine))
    for seed in range(30):
        out = TipsterDayOutput.model_validate(tipster_policy.decide_day(ctx, random.Random(seed)))
        assert {d.match_id for d in out.decisions} <= {m["match_id"] for m in ctx["matches"]}
        bets = [d for d in out.decisions if d.decision == "BET"]
        assert len(bets) <= ctx["constraints"]["max_bets"]
        for d in bets:
            assert 1.0 <= d.stake <= ctx["constraints"]["max_stake"] + 1e-9
            assert d.market in {c["market"] for m in ctx["matches"] for c in m["candidates"]}


def test_no_edge_means_no_bet_for_disciplined_tipster(fresh):
    world, _, engine = fresh()
    ctx = copy.deepcopy(asyncio.run(_first_context(engine)))
    ctx["agent"]["traits"].update(cautious=0.9, risk_seeking=0.1, stubborn=0.9, skeptical=0.8)
    for m in ctx["matches"]:
        m["coworkers"] = []
        for c in m["candidates"]:
            c["edge"] = -0.05
    for seed in range(20):
        out = tipster_policy.decide_day(ctx, random.Random(seed))
        assert all(d["decision"] == "NO_BET" for d in out["decisions"])


def test_career_pressure_makes_risk_seekers_swing_harder(fresh):
    world, _, engine = fresh()
    base = copy.deepcopy(asyncio.run(_first_context(engine)))
    calm = copy.deepcopy(base)
    calm["agent"].update(under_review=False, reputation=60, stress=0.2, confidence=0.5, streak=0)
    calm["agent"]["traits"].update(risk_seeking=0.8, ambitious=0.8, cautious=0.2)
    calm["company"]["status"] = "stable"
    pressured = copy.deepcopy(calm)
    pressured["agent"].update(under_review=True, reputation=30, stress=0.75)
    pressured["company"]["status"] = "distress"

    def totals(ctx):
        n = stake = 0.0
        for seed in range(60):
            for d in tipster_policy.decide_day(ctx, random.Random(seed))["decisions"]:
                if d["decision"] == "BET":
                    n += 1
                    stake += d["stake"]
        return n, stake

    n_calm, s_calm = totals(calm)
    n_press, s_press = totals(pressured)
    assert n_press >= n_calm
    assert s_press > s_calm


def test_stress_rises_under_distress_and_review(fresh):
    world, _, _ = fresh()
    a, b = world.tipsters()[0], world.tipsters()[1]
    for e in (a, b):
        e.psyche.stress = 0.25
    calm = psychology.DayContext(distress=0.0, company_thriving=True, dept_month_profit=50, recent_layoffs=0,
                                 recent_roi=0.02, recent_bets=40, day_profit=0)
    bad = psychology.DayContext(distress=0.8, company_thriving=False, dept_month_profit=-400, recent_layoffs=2,
                                recent_roi=-0.1, recent_bets=40, day_profit=-20)
    b.under_review = True
    for _ in range(30):
        psychology.daily_update(a, calm)
        psychology.daily_update(b, bad)
    assert b.psyche.stress > a.psyche.stress + 0.2
    for e in (a, b):
        assert 0 <= e.psyche.stress <= 1 and 0 <= e.psyche.confidence <= 1 and 0 <= e.psyche.reputation <= 100


class _FlakyProvider:
    name = "flaky"

    def __init__(self, bad_attempts: int) -> None:
        self.bad_attempts = bad_attempts
        self.calls = 0

    def model_for(self, purpose: str) -> str:
        return "claude-haiku-4-5"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        text = "not json at all" if self.calls <= self.bad_attempts else '{"thought": "ok", "decisions": []}'
        return ModelResponse(text=text, input_tokens=100, output_tokens=20, model="claude-haiku-4-5", latency_ms=1)


def _run_gateway(provider):
    records = []
    gw = AIGateway(provider, "run", sink=records.append, max_retries=2)
    out, rec = asyncio.run(gw.run(
        purpose="tipster_day", agent_id="e1", agent_name="Test", sim_time=datetime(2026, 8, 10), system="s",
        user="u", context={}, output_model=TipsterDayOutput, seed=1,
        fallback=lambda: TipsterDayOutput(thought="fallback", decisions=[])))
    return out, rec, records


def test_gateway_retries_then_succeeds():
    out, rec, records = _run_gateway(_FlakyProvider(bad_attempts=1))
    assert rec.ok and rec.retries == 1 and out.thought == "ok"
    assert rec.input_tokens == 200 and rec.cost_usd > 0
    assert records == [rec]


def test_gateway_falls_back_after_repeated_failures():
    out, rec, _ = _run_gateway(_FlakyProvider(bad_attempts=10))
    assert not rec.ok and rec.used_fallback and out.thought == "fallback"
    assert rec.retries == 2 and rec.error
