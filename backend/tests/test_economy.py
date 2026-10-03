from __future__ import annotations

from app.domain.betting import Bet
from app.economy import accounting
from app.economy import config as EC
from app.economy import valuation as val
from app.simulation import metrics


def _bet(world, emp, dept, stake=20.0, odds=2.5, market="home_win") -> Bet:
    m = next(iter(world.matches.values()))
    return Bet(id=world.next_id("b"), placed=world.clock.now, employee_id=emp.id, department_id=dept.id,
               match_id=m.id, match_label="A vs B", competition=m.competition, market=market, selection="A",
               book="Atlas", odds=odds, stake=stake, confidence=0.6)


def test_bet_lifecycle_moves_money_correctly(fresh):
    world, _, _ = fresh()
    emp = world.tipsters()[0]
    dept = world.departments[emp.department_id]
    start_bankroll = dept.bankroll
    win = _bet(world, emp, dept, 20, 2.5)
    loss = _bet(world, emp, dept, 10, 3.0)
    void = _bet(world, emp, dept, 5, 2.0)
    for b in (win, loss, void):
        accounting.register_bet(world, b)
    assert dept.bankroll == start_bankroll - 35
    assert metrics.exposure_total(world) == 35
    accounting.settle_bet(world, win, True, world.clock.now)
    accounting.settle_bet(world, loss, False, world.clock.now)
    accounting.settle_bet(world, void, False, world.clock.now, void=True)
    assert dept.bankroll == start_bankroll - 35 + 50 + 0 + 5
    assert emp.profit == 30 - 10
    assert world.finances.month.betting_pnl == 20
    assert not world.open_bet_ids
    assert (emp.wins, emp.losses) == (1, 1)


def test_closed_desk_payout_goes_to_cash(fresh):
    world, _, _ = fresh()
    emp = world.tipsters()[0]
    dept = world.departments[emp.department_id]
    b = _bet(world, emp, dept, 10, 2.0)
    accounting.register_bet(world, b)
    dept.active = False
    cash = world.finances.cash
    accounting.settle_bet(world, b, True, world.clock.now)
    assert world.finances.cash == cash + 20


def test_month_close_pays_accruals_revenue_and_bonuses(fresh):
    world, _, _ = fresh()
    for _ in range(30):
        accounting.accrue_daily_costs(world)
    payables = world.finances.payables
    assert payables > 0
    star = world.tipsters()[0]
    star.month_profit = 200.0
    loser = world.tipsters()[1]
    loser.month_profit = -150.0
    cash = world.finances.cash
    report = accounting.monthly_close(world, "2026-08")
    assert world.finances.payables == 0
    assert report.lines.bonuses == round(EC.BONUS_RATE * 200, 2)
    assert star.bonuses_earned == 20 and loser.bonuses_earned == 0
    expected = cash + report.lines.subscriptions - payables - report.lines.bonuses - report.lines.interest
    assert abs(world.finances.cash - expected) < 1e-6
    assert world.finances.month.expenses == 0  # accumulators reset
    assert world.monthly_reports[-1] is report


def test_liquidity_pulls_bankroll_then_credit(fresh):
    world, _, _ = fresh()
    total_bankroll = metrics.bankroll_total(world)
    world.finances.cash = -500.0
    notes = accounting.ensure_liquidity(world)
    assert world.finances.cash >= 0
    assert metrics.bankroll_total(world) < total_bankroll
    assert notes
    # money tied up in open bets still counts as equity: the credit line covers the gap
    emp = world.tipsters()[0]
    accounting.register_bet(world, _bet(world, emp, world.departments[emp.department_id], stake=1000, odds=2.0))
    for d in world.active_departments():
        d.bankroll = 0.0
    world.finances.cash = -300.0
    accounting.ensure_liquidity(world)
    assert world.finances.debt > 0 and world.finances.cash >= 0
    # an insolvent company gets no credit
    world.open_bet_ids.clear()
    world.finances.cash = -world.finances.debt - 50
    debt = world.finances.debt
    accounting.ensure_liquidity(world)
    assert world.finances.debt == debt and world.finances.cash < 0


def test_valuation_and_runway(fresh):
    world, _, _ = fresh()
    eq = val.equity(world)
    assert abs(eq - world.config.starting_capital) < 1.0  # nothing spent yet
    assert val.valuation(world) > eq  # subscriber goodwill
    assert val.runway_months(world) is not None  # fixed costs exceed subscriptions at founding
    assert val.company_status(world) in ("stable", "strained", "thriving")


def test_subscribers_react_to_track_record(fresh):
    world, _, _ = fresh()
    world.finances.subscribers = 100
    gained, lost, revenue = accounting.subscriptions_update(world)  # no bets yet: neutral track record
    assert lost == round(100 * EC.preset("normal")["sub_churn"])
    assert revenue == world.finances.subscribers * world.finances.subscription_price


def test_difficulty_presets_change_the_economy_not_the_football():
    from datetime import date

    from app.domain.world import RunConfig
    from app.providers import make_sports_provider
    from app.simulation.factory import create_world

    worlds = {}
    for level in ("easy", "hard"):
        cfg = RunConfig(seed=4, difficulty=level, starting_capital=EC.preset(level)["capital"])
        worlds[level] = create_world(cfg, make_sports_provider(cfg))
    easy, hard = worlds["easy"], worlds["hard"]
    assert easy.config.starting_capital > hard.config.starting_capital
    assert easy.finances.subscribers > hard.finances.subscribers
    pay = lambda w: sum(e.salary for e in w.active_employees())
    assert pay(hard) > pay(easy)
    assert val.estimated_operating_cost(hard) > val.estimated_operating_cost(easy)
    # same seed, same results; only the bookmakers' sharpness differs
    first = lambda w: sorted((m.id, m.home_goals, m.away_goals) for m in w.matches.values())[:300]
    assert first(easy) == first(hard)
    assert date(2026, 8, 14) == easy.config.start_date
