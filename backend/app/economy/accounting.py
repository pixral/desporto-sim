"""Bookkeeping. Every euro that moves goes through one of these functions."""

from __future__ import annotations

import math
from datetime import datetime

from app.domain.base import clamp
from app.domain.betting import Bet
from app.domain.company import CostTotals, DailyPoint, Department, MonthlyReport
from app.domain.people import Employee
from app.domain.world import World
from app.simulation import metrics

from . import config as C
from . import market
from . import valuation as val


# ------------------------------------------------------------------ daily accruals
def accrue_daily_costs(world: World) -> float:
    """Accrue one day of fixed costs into payables (paid at month close). Returns the amount."""
    f = world.finances
    mult = C.preset(world.config.difficulty)["cost_mult"]
    active = world.active_employees()
    salaries = sum(e.salary for e in active) / 30.0
    rent = (mult * (C.RENT_BASE + C.RENT_PER_HEAD * len(active)) + market.facilities_monthly_cost(world)) / 30.0
    comps = {c for d in world.active_departments() for c in d.competitions}
    data = mult * C.DATA_PER_COMPETITION * len(comps) * market.modifier(world, "data_prices") / 30.0
    marketing = f.marketing_budget / 30.0
    lab = f.lab_budget / 30.0
    for target in (f.month, f.totals):
        target.salaries += salaries
        target.rent += rent
        target.data += data
        target.marketing += marketing
        target.lab += lab
    total = salaries + rent + data + marketing + lab
    f.payables += total
    return total


def charge_ai(world: World, usd: float) -> float:
    eur = usd * C.USD_TO_EUR
    f = world.finances
    f.cash -= eur
    f.month.ai += eur
    f.totals.ai += eur
    return eur


def pay_severance(world: World, emp: Employee) -> float:
    amount = emp.salary * C.SEVERANCE_MONTHS
    f = world.finances
    f.cash -= amount
    f.month.severance += amount
    f.totals.severance += amount
    return amount


# ------------------------------------------------------------------ bets
def place_stake(dept: Department, stake: float) -> None:
    dept.bankroll -= stake


def settle_bet(world: World, bet: Bet, won: bool, settled_at: datetime, void: bool = False) -> float:
    """Pay out into the department bankroll and update every counter. Returns profit."""
    dept = world.departments[bet.department_id]
    emp = world.employees[bet.employee_id]
    if void:
        bet.status, bet.payout = "void", bet.stake
    elif won:
        bet.status, bet.payout = "won", round(bet.stake * bet.odds, 2)
    else:
        bet.status, bet.payout = "lost", 0.0
    bet.settled = settled_at
    profit = bet.payout - bet.stake
    if dept.active:
        dept.bankroll += bet.payout
    else:  # desk closed while the bet was open: money goes back to company cash
        world.finances.cash += bet.payout
    dept.total_profit += profit
    dept.month_profit += profit
    dept.day_profit += profit
    emp.returned += bet.payout
    emp.month_profit += profit
    emp.day_profit += profit
    if bet.status == "won":
        emp.wins += 1
    elif bet.status == "lost":
        emp.losses += 1
    f = world.finances
    f.month.betting_pnl += profit
    f.totals.betting_pnl += profit
    strat = world.strategies.get(bet.strategy_id or "")
    if strat:
        strat.live_profit += profit
    if bet.id in world.open_bet_ids:
        world.open_bet_ids.remove(bet.id)
    return profit


def register_bet(world: World, bet: Bet) -> None:
    dept = world.departments[bet.department_id]
    emp = world.employees[bet.employee_id]
    place_stake(dept, bet.stake)
    dept.total_staked += bet.stake
    dept.bets += 1
    emp.staked += bet.stake
    emp.bets_total += 1
    emp.bet_ids.append(bet.id)
    world.bets[bet.id] = bet
    world.open_bet_ids.append(bet.id)
    world.stats.bets_placed += 1
    strat = world.strategies.get(bet.strategy_id or "")
    if strat:
        strat.live_bets += 1
        strat.live_staked += bet.stake


# ------------------------------------------------------------------ liquidity
def transfer_to_department(world: World, dept: Department, amount: float) -> float:
    amount = max(0.0, min(amount, world.finances.cash))
    world.finances.cash -= amount
    dept.bankroll += amount
    return amount


def withdraw_from_department(world: World, dept: Department, amount: float) -> float:
    amount = max(0.0, min(amount, dept.bankroll))
    dept.bankroll -= amount
    world.finances.cash += amount
    return amount


def ensure_liquidity(world: World) -> list[str]:
    """If cash is negative, pull desk bankrolls, then draw on credit. Returns human-readable notes."""
    notes: list[str] = []
    f = world.finances
    if f.cash >= 0:
        return notes
    need = -f.cash
    desks = sorted((d for d in world.active_departments() if d.bankroll > 0), key=lambda d: -d.bankroll)
    total_bankroll = sum(d.bankroll for d in desks)
    if total_bankroll > 0:
        pulled = 0.0
        for d in desks:
            share = min(d.bankroll, need * d.bankroll / total_bankroll + 0.01)
            pulled += withdraw_from_department(world, d, share)
        notes.append(f"Emergency: €{pulled:,.0f} pulled from desk bankrolls to cover obligations.")
    if f.cash < 0:
        credit = val.credit_available(world)
        draw = min(credit, -f.cash)
        if draw > 0:
            f.debt += draw
            f.cash += draw
            notes.append(f"Emergency: drew €{draw:,.0f} on the credit line.")
    return notes


def take_loan(world: World, amount: float) -> float:
    amount = max(0.0, min(amount, val.credit_available(world)))
    world.finances.debt += amount
    world.finances.cash += amount
    return amount


def repay_loan(world: World, amount: float) -> float:
    f = world.finances
    amount = max(0.0, min(amount, f.debt, f.cash))
    f.debt -= amount
    f.cash -= amount
    return amount


# ------------------------------------------------------------------ month close
def subscriptions_update(world: World) -> tuple[int, int, float]:
    """Monthly subscriber churn and acquisition driven by the public 90-day track record."""
    f = world.finances
    perf = metrics.company_stats(world, 90)
    track = perf.roi if perf.bets >= 30 else 0.0
    p = C.preset(world.config.difficulty)
    mood = market.economy(world)  # consumer confidence in the city
    churn = clamp(p["sub_churn"] - 0.6 * track - 0.01 * mood, 0.025, 0.30)
    quality = 1.0 + clamp(track * 6, -0.5, 0.6)
    reach = (market.modifier(world, "ad_ban") * market.modifier(world, "sub_boost") * (1.0 + 0.15 * mood)
             * (C.STUDIO_ACQUISITION if market.leased(world, "studio") else 1.0))
    new = p["sub_acq"] * math.sqrt(max(f.marketing_budget, 0.0)) * quality * reach
    lost = round(f.subscribers * churn)
    gained = round(new)
    f.subscribers = max(0, f.subscribers - lost + gained)
    revenue = f.subscribers * f.subscription_price
    return gained, lost, revenue


def monthly_close(world: World, month: str) -> MonthlyReport:
    """Pay what was accrued, add revenue, pay bonuses and interest, freeze the month's report."""
    f = world.finances
    # bonuses
    bonuses = 0.0
    for e in world.tipsters():
        if e.month_profit > 0:
            b = round(C.BONUS_RATE * e.month_profit, 2)
            e.bonuses_earned += b
            bonuses += b
    f.month.bonuses += bonuses
    f.totals.bonuses += bonuses
    interest = f.debt * market.loan_rate_monthly(world)
    f.month.interest += interest
    f.totals.interest += interest
    _, _, revenue = subscriptions_update(world)
    f.month.subscriptions += revenue
    f.totals.subscriptions += revenue
    f.cash += revenue - f.payables - bonuses - interest
    f.payables = 0.0
    by_dept = {}
    for d in world.departments.values():
        if d.active or d.month_profit:
            by_dept[d.name] = round(d.month_profit, 2)
            d.profit_by_month[month] = round(d.month_profit, 2)
    report = MonthlyReport(
        month=month,
        lines=f.month.model_copy(),
        by_department=by_dept,
        end_cash=round(f.cash, 2),
        end_bankroll=round(metrics.bankroll_total(world), 2),
        end_debt=round(f.debt, 2),
        valuation=0.0,
        subscribers=f.subscribers,
        headcount=len(world.active_employees()),
        bets=sum(1 for b in world.bets.values() if b.placed.strftime("%Y-%m") == month),
    )
    world.monthly_reports.append(report)
    report.valuation = round(val.valuation(world), 2)
    f.month = CostTotals()
    for d in world.departments.values():
        d.month_profit = 0.0
    for e in world.employees.values():
        e.month_profit = 0.0
    return report


# ------------------------------------------------------------------ daily snapshot
def record_daily_point(world: World, day_pnl: float) -> DailyPoint:
    f = world.finances
    value = val.valuation(world)
    point = DailyPoint(
        day=world.today, cash=round(f.cash, 2), bankroll=round(metrics.bankroll_total(world), 2),
        exposure=round(metrics.exposure_total(world), 2), debt=round(f.debt, 2), payables=round(f.payables, 2),
        valuation=round(value, 2), day_pnl=round(day_pnl, 2), subscribers=f.subscribers,
    )
    world.daily.append(point)
    if value > f.peak_value:
        f.peak_value = value
        f.peak_value_day = world.today
    if f.peak_value > 0:
        f.max_drawdown = max(f.max_drawdown, 1.0 - value / f.peak_value)
    f.record_cash = max(f.record_cash, f.cash)
    return point
