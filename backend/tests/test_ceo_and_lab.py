"""CEO rebuilding/replacement logic and the LAB's out-of-sample holdout."""

from __future__ import annotations

import random
from datetime import timedelta

from app.agents import management
from app.agents.context import build_ceo_context
from app.agents.policies import ceo_policy
from app.ai.schemas import CEOAction
from app.domain.lab import Experiment
from app.domain.strategy import BacktestResult
from app.simulation import lab


def _row(i: str, dept: str, **kw):
    base = dict(id=i, name=i, role="tipster", department_id=dept, tenure_days=200, bets_90d=80, roi_90d=0.0,
                z_90d=0.0, career_bets=200, career_roi=0.0, z_career=0.0, strategy_age_days=200)
    base.update(kw)
    return base


def _ctx(employees, candidates=(), days_since_swap=999):
    return {
        "company": {"days_since_swap": days_since_swap},
        "employees": list(employees),
        "candidates": list(candidates),
        "departments": [{"id": "d1", "competitions": ["BL1"], "preferred_specialties": ["bundesliga", "form"]},
                        {"id": "d2", "competitions": ["PL"], "preferred_specialties": ["premier_league"]}],
    }


def test_deploy_targets_are_distinct_losers_with_settled_strategies():
    ctx = _ctx([
        _row("good", "d1", z_90d=1.2, career_roi=0.04),
        _row("bad", "d1", z_90d=-1.5, career_roi=-0.05),
        _row("worse_but_just_switched", "d1", z_90d=-2.0, strategy_age_days=20),
        _row("meh", "d1", z_90d=-0.6, career_roi=-0.01),
    ])
    x = {"competitions": ["BL1"]}
    first = ceo_policy._deploy_target(ctx, x, set())
    second = ceo_policy._deploy_target(ctx, x, {first})
    third = ceo_policy._deploy_target(ctx, x, {first, second})
    assert first == "bad" and second == "meh" and third is None  # never the winner, never twice


def test_upgrade_swap_needs_lab_evidence_for_data_driven():
    weak = _row("weak", "d1", career_bets=300, career_roi=-0.06, z_career=-1.4)
    cands = [
        {"id": "c1", "name": "Shiny CV", "role": "tipster", "specialty": "form", "cv_rating": 95,
         "lab_backtest_roi": None, "lab_backtest_n": None},
        {"id": "c2", "name": "Tested", "role": "tipster", "specialty": "bundesliga", "cv_rating": 50,
         "lab_backtest_roi": 0.05, "lab_backtest_n": 400},
    ]
    t, c, dept = ceo_policy._upgrade_swap(_ctx([weak], cands), "data_driven", set(), set())
    assert (t["id"], c["id"], dept) == ("weak", "c2", "d1")
    # the aggressive expansionist goes for the CV instead
    _, c, _ = ceo_policy._upgrade_swap(_ctx([weak], cands), "aggressive_expansionist", set(), set())
    assert c["id"] == "c1"
    # without a weak performer nobody gets replaced
    assert ceo_policy._upgrade_swap(_ctx([_row("fine", "d1")], cands), "data_driven", set(), set()) is None
    # against a mildly weak tipster, a small lucky backtest is not enough evidence (winner's curse)...
    mild = _row("mild", "d1", career_bets=150, career_roi=-0.02, z_career=-1.0)
    lucky = [dict(cands[1], lab_backtest_roi=0.06, lab_backtest_n=110)]
    assert ceo_policy._upgrade_swap(_ctx([mild], lucky), "data_driven", set(), set()) is None
    # ...but a large, solid backtest is
    assert ceo_policy._upgrade_swap(_ctx([mild], cands), "data_driven", set(), set())[1]["id"] == "c2"
    # and swaps happen at most once a quarter
    assert ceo_policy._upgrade_swap(_ctx([weak], cands, days_since_swap=30), "data_driven", set(), set()) is None


def test_shrunken_company_with_runway_rebuilds(fresh):
    world, _, _ = fresh(style="data_driven")
    for e in world.tipsters()[:5]:
        management.depart(world, e, "fired: test", fired=True, severance=False)
    assert len(world.tipsters()) == 3
    ctx = build_ceo_context(world, "monthly")
    out = ceo_policy.review(ctx, random.Random(3))
    hires = [a for a in out["actions"] if a["type"] == "HIRE"]
    assert hires, out["actions"]


def test_strategy_switch_cooldown_is_enforced(fresh):
    world, _, _ = fresh()
    emp = world.tipsters()[0]
    sid = emp.strategy_id
    x1 = Experiment(id="x1", researcher_id="e1", name="A", hypothesis="h", strategy_id=sid, started=world.today,
                    due=world.today, status="completed")
    other = world.tipsters()[1].strategy_id
    x2 = Experiment(id="x2", researcher_id="e1", name="B", hypothesis="h", strategy_id=other, started=world.today,
                    due=world.today, status="completed")
    world.experiments = {"x1": x1, "x2": x2}
    emp.hired = world.today - timedelta(days=400)
    emp.traits.stubborn = 0.0  # never refuses
    (r,) = management.apply_actions(world, random.Random(1), [CEOAction(type="DEPLOY_STRATEGY", experiment_id="x2",
                                                                         employee_id=emp.id)], "monthly")
    assert r.applied, r.result
    (r,) = management.apply_actions(world, random.Random(1), [CEOAction(type="DEPLOY_STRATEGY", experiment_id="x1",
                                                                         employee_id=emp.id)], "monthly")
    assert not r.applied and "give it time" in r.result


def _fake_backtests(monkeypatch, in_sample: BacktestResult, holdout: BacktestResult):
    calls = iter([in_sample, holdout])
    monkeypatch.setattr(lab, "backtest", lambda *a, **k: next(calls))


def _experiment(world):
    sid = world.tipsters()[0].strategy_id
    researcher = world.active_employees("researcher")[0]
    researcher.traits.risk_seeking = researcher.traits.ambitious = researcher.traits.skeptical = 0.5
    return Experiment(id="x9", researcher_id=researcher.id, name="Idea", hypothesis="h", strategy_id=sid,
                      started=world.today, due=world.today)


def test_lab_deploys_only_what_survives_the_holdout(fresh, monkeypatch):
    world, sports, engine = fresh()
    strong = BacktestResult(sample_size=220, roi=0.06, win_rate=0.4, max_drawdown_pct=0.1)
    _fake_backtests(monkeypatch, strong, BacktestResult(sample_size=60, roi=0.02))
    x = _experiment(world)
    lab.complete_experiment(world, engine.index, engine.popular, x)
    assert x.recommendation == "DEPLOY" and x.holdout.roi == 0.02

    _fake_backtests(monkeypatch, strong, BacktestResult(sample_size=60, roi=-0.08))
    y = _experiment(world)
    lab.complete_experiment(world, engine.index, engine.popular, y)
    assert y.recommendation == "REJECT"
    assert world.events[-1].title.endswith("collapses on fresh data")

    _fake_backtests(monkeypatch, strong, BacktestResult(sample_size=10, roi=0.2))  # too little fresh data
    z = _experiment(world)
    lab.complete_experiment(world, engine.index, engine.popular, z)
    assert z.recommendation == "PROMISING"
    assert world.events[-1].importance == 1  # "promising" no longer floods the timeline
