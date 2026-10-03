from __future__ import annotations

import asyncio

from app.ai.mock_provider import MockAgentModelProvider
from app.domain.world import World
from app.economy import valuation as val
from app.simulation.engine import SimulationEngine
from app.sports.mock_provider import MockSportsDataProvider


def _fingerprint(world: World) -> tuple:
    return (world.clock.day_index, world.stats.bets_placed, world.stats.no_bets, round(world.finances.cash, 6),
            round(val.valuation(world), 6), len(world.events), world.events[-1].title,
            tuple(sorted((e.name, e.active, round(e.profit, 6)) for e in world.employees.values())))


def test_runs_two_months_and_keeps_books_consistent(fresh):
    world, _, engine = fresh()
    asyncio.run(engine.run_days(62))
    assert world.clock.day_index == 62
    assert world.stats.bets_placed > 50
    assert len(world.daily) == 62
    assert len(world.monthly_reports) == 2  # August and September closed
    assert world.ai_stats.calls > 0 and world.ai_stats.failures == 0
    # every settled bet's profit is accounted in the betting P&L
    settled = sum(b.profit for b in world.bets.values() if b.status != "open")
    assert abs(settled - world.finances.totals.betting_pnl) < 1e-6
    # desk bankrolls + open exposure + cash reconcile with the cumulative cash flows
    f = world.finances
    implied = (world.config.starting_capital + f.totals.betting_pnl + f.totals.subscriptions - f.totals.expenses
               + f.debt)
    actual = f.cash + sum(d.bankroll for d in world.departments.values()) + \
        sum(world.bets[b].stake for b in world.open_bet_ids) - f.payables
    assert abs(implied - actual) < 0.05


def test_no_results_visible_when_tipsters_decide(fresh):
    world, _, engine = fresh()
    seen = []
    original = engine._apply_tipster_day

    def spy(emp, rows, out, ok):
        # snapshot what the match looked like at the moment of the decision
        seen.extend((r.match.home_goals, r.match.home_xg, r.match.status, bool(r.match.odds_close)) for r in rows)
        return original(emp, rows, out, ok)

    engine._apply_tipster_day = spy
    asyncio.run(engine.run_days(10))
    assert seen
    assert all(s == (None, None, "scheduled", False) for s in seen)


def test_decisions_happen_before_kickoff(fresh):
    world, _, engine = fresh()
    asyncio.run(engine.run_days(20))
    for b in world.bets.values():
        m = world.matches[b.match_id]
        assert b.placed < m.kickoff


def test_deterministic_given_seed(fresh):
    a, _, ea = fresh(seed=9)
    b, _, eb = fresh(seed=9)
    asyncio.run(ea.run_days(40))
    asyncio.run(eb.run_days(40))
    assert _fingerprint(a) == _fingerprint(b)


def test_save_load_roundtrip_continues_identically(fresh):
    straight, _, es = fresh(seed=4)
    asyncio.run(es.run_days(45))

    world, sports, engine = fresh(seed=4)
    asyncio.run(engine.run_days(25))
    engine.sync_provider_state()
    blob = world.model_dump_json()
    restored = World.model_validate_json(blob)
    sports2 = MockSportsDataProvider(seed=12345)
    sports2.import_state(restored.provider_state)
    engine2 = SimulationEngine(restored, sports2, MockAgentModelProvider())
    asyncio.run(engine2.run_days(20))
    assert _fingerprint(restored) == _fingerprint(straight)


def test_bankruptcy_is_a_real_ending(fresh):
    world, _, engine = fresh(style="aggressive_expansionist", capital=20000)
    asyncio.run(engine.run_days(3))
    # wipe the company out: nothing left anywhere
    for d in world.departments.values():
        d.bankroll = 0.0
    world.finances.cash = -50.0
    world.finances.debt = world.config.starting_capital  # credit line exhausted
    asyncio.run(engine.run_days(2))
    assert world.ended and world.finances.status == "bankrupt"
    assert world.summary is not None and world.summary.days_survived >= 3
    day = world.clock.day_index
    asyncio.run(engine.step())
    assert world.clock.day_index == day  # an ended run does not advance
