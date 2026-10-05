"""The LAB: AI-proposed hypotheses, deterministic walk-forward backtests, audits of live tipsters."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import timedelta

from app.agents import prompts
from app.agents.context import build_lab_context
from app.ai.gateway import AIGateway
from app.ai.schemas import LabHypothesisOutput, LabStrategyParams
from app.analysis.backtest import backtest
from app.analysis.index import SportsIndex
from app.domain.base import clamp
from app.domain.lab import AuditFinding, Experiment
from app.domain.strategy import PARAM_BOUNDS, Strategy
from app.domain.world import World

from . import history, metrics

BACKTEST_DAYS = 365
HOLDOUT_DAYS = 120
HOLDOUT_MIN_BETS = 30


def _duration_days(budget: float) -> int:
    return int(clamp(round(24 - budget / 8), 5, 24))


def _capacity(budget: float) -> int:
    return 1 + int(budget >= 90) + int(budget >= 160)


MIN_TEST_BUDGET = 40.0  # below this the LAB doesn't backtest applicants


def slots(world: World) -> int:
    """Parallel LAB jobs: experiments and (player mode) applicant tests share them."""
    if world.finances.lab_budget <= 0:
        return 0
    return _capacity(world.finances.lab_budget) * len(world.active_employees("researcher"))


def pending_tests(world: World) -> int:
    return sum(1 for c in world.candidates if c.lab_test_due is not None and c.lab_backtest_n is None)


def free_slots(world: World) -> int:
    running = sum(1 for x in world.experiments.values() if x.status == "running")
    return slots(world) - running - pending_tests(world)


def strategy_from_params(world: World, params: LabStrategyParams, name: str, author_id: str) -> Strategy:
    covered = sorted({c for d in world.active_departments() for c in d.competitions})
    s = Strategy(id=world.next_id("s"), name=name[:60] or "Unnamed idea", origin="lab", author_id=author_id,
                 created=world.today)
    s.competitions = [c for c in params.competitions if c in world.competitions] or covered
    s.markets = list(dict.fromkeys(params.markets)) or ["home_win", "draw", "away_win"]
    for field, (lo, hi) in PARAM_BOUNDS.items():
        value = getattr(params, field, None)
        if value is not None:
            v = clamp(float(value), lo, hi)
            setattr(s, field, int(round(v)) if field == "window" else round(v, 4))
    if params.opponent_adjust is not None:
        s.opponent_adjust = params.opponent_adjust
    if params.fade_popular is not None:
        s.fade_popular = params.fade_popular
    if s.min_odds >= s.max_odds:
        s.max_odds = clamp(s.min_odds + 1.0, *PARAM_BOUNDS["max_odds"])
    world.strategies[s.id] = s
    return s


async def lab_morning(world: World, index: SportsIndex, popular: set[str], gateway: AIGateway,
                      rng: random.Random) -> None:
    for x in sorted(world.experiments.values(), key=lambda x: x.id):
        if x.status == "running" and x.due <= world.today:
            complete_experiment(world, index, popular, x)
    researchers = sorted(world.active_employees("researcher"), key=lambda e: e.id)
    budget = world.finances.lab_budget
    history_matches = sum(1 for m in world.matches.values() if m.finished)
    for r in researchers:
        running = [x for x in world.experiments.values() if x.status == "running" and x.researcher_id == r.id]
        if running:
            r.status, r.task = "researching", f"Backtesting '{running[0].name}'"
        else:
            r.status, r.task = "researching", "Reading old match data"
        if budget <= 0 or len(running) >= _capacity(budget):
            if budget <= 0:
                r.status, r.task = "idle", "No research budget"
            continue
        if pending_tests(world) and free_slots(world) <= 0:  # applicant tests the CEO asked for come first
            if not running:
                r.task = "Backtesting applicants' methods"
            continue
        last = world.milestones.get(f"lab_last_start:{r.id}")
        if last and (world.today.toordinal() - int(last)) < 3:
            continue
        ctx = build_lab_context(world, r, history_matches)
        out, _ = await gateway.run(
            purpose="lab_hypothesis", agent_id=r.id, agent_name=r.name, sim_time=world.clock.now,
            system=prompts.lab_system(ctx), user=prompts.lab_user(ctx), context=ctx,
            output_model=LabHypothesisOutput, seed=rng.randrange(1 << 30),
            fallback=lambda: LabHypothesisOutput(name="", hypothesis="", rationale="model failure",
                                                 params=LabStrategyParams()),
        )
        if not out.name:
            continue
        s = strategy_from_params(world, out.params, out.name, r.id)
        s.description = out.hypothesis
        exp = Experiment(id=world.next_id("x"), researcher_id=r.id, name=s.name, hypothesis=out.hypothesis,
                         rationale=out.rationale, strategy_id=s.id, started=world.today,
                         due=world.today + timedelta(days=_duration_days(budget)))
        world.experiments[exp.id] = exp
        world.milestones[f"lab_last_start:{r.id}"] = world.today.toordinal()
        r.task = f"Designing '{exp.name}'"
        history.record(world, "experiment_started", f"LAB: {r.name} starts testing '{exp.name}'", exp.hypothesis,
                       1, "neutral", [r.id])


def complete_experiment(world: World, index: SportsIndex, popular: set[str], x: Experiment) -> None:
    """Backtest in-sample, then check the most recent months as an out-of-sample holdout.

    Researchers try many ideas; the best in-sample result is usually partly luck. A strategy is
    only recommended for deployment if it also holds up on the holdout period.
    """
    s = world.strategies[x.strategy_id]
    split = world.today - timedelta(days=HOLDOUT_DAYS)
    res = backtest(index, world.matches.values(), s, popular, start=world.today - timedelta(days=BACKTEST_DAYS),
                   end=split)
    hold = backtest(index, world.matches.values(), s, popular, start=split, end=world.today)
    s.backtest = res
    x.result = res
    x.holdout = hold
    x.completed = world.today
    x.status = "completed"
    world.stats.experiments_run += 1
    r = world.employees.get(x.researcher_id)
    boldness = 0.0
    if r is not None:
        boldness = 0.5 * r.traits.risk_seeking + 0.3 * r.traits.ambitious - 0.4 * r.traits.skeptical
    n, roi, dd = res.sample_size, res.roi, res.max_drawdown_pct
    holds = hold.sample_size >= HOLDOUT_MIN_BETS and hold.roi > 0.0
    if n >= 120 and roi >= 0.04 - 0.015 * boldness and dd < 0.3 and holds:
        x.recommendation = "DEPLOY"
    elif n >= 40 and roi > 0.0 and (hold.sample_size < 20 or hold.roi > -0.03):
        x.recommendation = "PROMISING"
    else:
        x.recommendation = "REJECT"
    x.recommendation_text = (f"In-sample {n} bets, ROI {roi:+.1%}, win rate {res.win_rate:.0%}, "
                             f"max drawdown {res.max_drawdown_units:.1f} units. Holdout {hold.sample_size} bets, "
                             f"ROI {hold.roi:+.1%}.")
    who = [x.researcher_id] if r else []
    if x.recommendation == "REJECT":
        x.status = "rejected"
        failed_on_holdout = n >= 120 and roi >= 0.03 and not holds
        history.record(world, "experiment_failed",
                       f"LAB: '{x.name}' {'collapses on fresh data' if failed_on_holdout else 'does not survive testing'}",
                       x.recommendation_text, 1, "neutral", who)
    else:
        world.stats.strategies_invented += 1
        breakthrough = x.recommendation == "DEPLOY" and roi >= 0.05 and n >= 200 and hold.roi >= 0.03
        importance = 3 if breakthrough else 1  # deployments get their own (notable) event
        title = (f"LAB breakthrough: '{x.name}'" if breakthrough
                 else f"LAB invents '{x.name}' ({x.recommendation.lower()})")
        history.record(world, "strategy_invented", title, f"{x.hypothesis} {x.recommendation_text}",
                       importance, "good", who)


def _odds_bucket(odds: float) -> str:
    if odds < 1.8:
        return "odds under 1.80"
    if odds < 2.6:
        return "odds 1.80-2.60"
    if odds < 4.0:
        return "odds 2.60-4.00"
    return "odds 4.00+"


_BUCKET_FIX = {"odds 4.00+": ("max_odds", 4.0), "odds 2.60-4.00": ("max_odds", 2.6), "odds under 1.80": ("min_odds", 1.8)}


def run_audit(world: World) -> list[AuditFinding]:
    """Deterministic review of each tipster's bets by segment. Needs at least one researcher."""
    if not world.active_employees("researcher"):
        return []
    open_keys = {(f.employee_id, f.segment) for f in world.audit_findings if not f.resolved}
    found: list[AuditFinding] = []
    cutoff = world.today - timedelta(days=150)
    for e in world.tipsters():
        bets = [b for b in metrics.settled_bets(world, e) if b.settled and b.settled.date() > cutoff]
        if len(bets) < 40:
            continue
        segs: dict[str, list] = defaultdict(list)
        for b in bets:
            segs[_odds_bucket(b.odds)].append(b)
            segs[f"market {b.market}"].append(b)
            segs[f"competition {b.competition}"].append(b)
        flagged = 0
        for seg, rows in sorted(segs.items(), key=lambda kv: metrics.PerfStats.from_bets(kv[1]).roi):
            if flagged >= 2:
                break
            perf = metrics.PerfStats.from_bets(rows)
            if perf.bets < 20 or perf.roi > -0.2 or (e.id, seg) in open_keys:
                continue
            fix = _BUCKET_FIX.get(seg)
            f = AuditFinding(id=world.next_id("a"), day=world.today, employee_id=e.id, segment=seg, bets=perf.bets,
                             roi=perf.roi, profit=perf.profit,
                             text=f"{e.name} loses on {seg}: ROI {perf.roi:+.0%} over {perf.bets} bets.",
                             suggestion={"field": fix[0], "value": fix[1]} if fix else {})
            found.append(f)
            flagged += 1
    world.audit_findings.extend(found)
    world.audit_findings = world.audit_findings[-60:]
    if found:
        history.record(world, "audit", f"LAB audit flags {len(found)} weak spot(s)",
                       " ".join(f.text for f in found[:3]), 1, "neutral",
                       [r.id for r in world.active_employees("researcher")])
    return found


def evaluate_candidates(world: World, index: SportsIndex, popular: set[str]) -> None:
    """When the LAB has budget, it backtests applicants' methods before the CEO decides."""
    if not world.active_employees("researcher") or world.finances.lab_budget < MIN_TEST_BUDGET:
        return
    for c in world.candidates:
        if c.strategy_id is None or c.lab_backtest_n is not None or c.strategy_id not in world.strategies:
            continue
        _test_candidate(world, index, popular, c)


def _test_candidate(world: World, index: SportsIndex, popular: set[str], c) -> None:
    covered = sorted({x for d in world.active_departments() for x in d.competitions})
    s = world.strategies[c.strategy_id]
    res = backtest(index, world.matches.values(), s, popular, start=world.today - timedelta(days=240),
                   end=world.today, competitions=s.competitions or covered)
    c.lab_backtest_roi = round(res.roi, 4)
    c.lab_backtest_n = res.sample_size


def run_candidate_tests(world: World, index: SportsIndex, popular: set[str]) -> None:
    """Player mode: finish the applicant tests the CEO asked for."""
    done = []
    for c in world.candidates:
        if c.lab_test_due is None or c.lab_test_due > world.today or c.lab_backtest_n is not None:
            continue
        if c.strategy_id not in world.strategies:
            c.lab_test_due = None
            continue
        _test_candidate(world, index, popular, c)
        done.append(f"{c.name}: ROI {c.lab_backtest_roi:+.1%} over {c.lab_backtest_n} bets")
    if done:
        history.record(world, "candidate_tests", f"LAB tested {len(done)} applicant(s)", "; ".join(done) + ".", 1,
                       "neutral", [r.id for r in world.active_employees("researcher")])
