"""Valuation, runway, burn and company status. Pure functions of World."""

from __future__ import annotations

from app.domain.company import CompanyStatus
from app.domain.world import World
from app.simulation import metrics

from . import config as C


def equity(world: World) -> float:
    f = world.finances
    return f.cash + metrics.bankroll_total(world) + metrics.exposure_total(world) - f.debt - f.payables


def trailing_net(world: World, months: int = 3) -> float | None:
    reps = world.monthly_reports[-months:]
    if not reps:
        return None
    return sum(r.lines.net for r in reps)


def valuation(world: World) -> float:
    f = world.finances
    goodwill = f.subscribers * f.subscription_price * 6
    tn = trailing_net(world, 3)
    momentum = max(0.0, tn) * 1.5 if tn is not None else 0.0
    return equity(world) + goodwill + momentum


def estimated_operating_cost(world: World) -> float:
    """Monthly fixed cost at current headcount and budgets."""
    f = world.finances
    payroll = sum(e.salary for e in world.active_employees())
    heads = len(world.active_employees())
    comps = {c for d in world.active_departments() for c in d.competitions}
    return payroll + C.RENT_BASE + C.RENT_PER_HEAD * heads + C.DATA_PER_COMPETITION * len(comps) \
        + f.marketing_budget + f.lab_budget


def monthly_burn(world: World) -> float:
    """Average monthly net cash burn (positive = losing money). Betting included once history exists."""
    reps = world.monthly_reports[-3:]
    if reps:
        return -sum(r.lines.net for r in reps) / len(reps)
    f = world.finances
    return estimated_operating_cost(world) - f.subscribers * f.subscription_price


def runway_months(world: World) -> float | None:
    """Months until the money runs out at the current burn; None when the company is not burning."""
    burn = monthly_burn(world)
    if burn <= 0:
        return None
    f = world.finances
    liquid = f.cash + metrics.bankroll_total(world) - f.payables - f.debt
    return max(0.0, liquid / burn)


def drawdown(world: World) -> float:
    peak = world.finances.peak_value
    if peak <= 0:
        return 0.0
    return max(0.0, 1.0 - valuation(world) / peak)


def credit_available(world: World) -> float:
    f = world.finances
    if equity(world) <= 0:
        return 0.0
    ratio = C.DISTRESS_CREDIT_RATIO if f.status == "distress" else C.CREDIT_LINE_RATIO
    return max(0.0, ratio * world.config.starting_capital - f.debt)


def company_status(world: World) -> CompanyStatus:
    if world.ended:
        return "bankrupt"
    eq = equity(world)
    start = world.config.starting_capital
    runway = runway_months(world)
    if eq < 0.25 * start or (runway is not None and runway < 4):
        return "distress"
    if runway is not None and runway < 12:
        return "strained"
    tn = trailing_net(world, 3)
    if runway is None and valuation(world) >= 1.05 * start and (tn is None or tn > 0):
        return "thriving"
    return "stable"
