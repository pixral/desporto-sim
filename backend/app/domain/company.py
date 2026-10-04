from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .base import Model

CompanyStatus = Literal["thriving", "stable", "strained", "distress", "bankrupt"]


class Department(Model):
    id: str
    name: str
    kind: str  # key into agents.catalog.DEPARTMENT_KINDS
    competitions: list[str]
    bankroll: float
    stake_limit_pct: float = 0.035  # max single stake as share of a tipster's allocation
    founded: date
    closed: date | None = None
    active: bool = True
    room_slot: int = 0
    head_id: str | None = None
    total_staked: float = 0.0
    total_profit: float = 0.0
    bets: int = 0
    month_profit: float = 0.0
    day_profit: float = 0.0
    profit_by_month: dict[str, float] = Field(default_factory=dict)


class CostTotals(Model):
    """Cumulative or per-month cost/revenue lines. All values positive except betting_pnl."""

    betting_pnl: float = 0.0
    salaries: float = 0.0
    bonuses: float = 0.0
    severance: float = 0.0
    rent: float = 0.0
    data: float = 0.0
    marketing: float = 0.0
    lab: float = 0.0
    ai: float = 0.0
    interest: float = 0.0
    other_costs: float = 0.0  # one-offs: office fit-outs, lease breaks, disasters
    subscriptions: float = 0.0  # revenue
    other_income: float = 0.0  # one-offs: sponsorship bonuses, rebates

    @property
    def expenses(self) -> float:
        return (
            self.salaries
            + self.bonuses
            + self.severance
            + self.rent
            + self.data
            + self.marketing
            + self.lab
            + self.ai
            + self.interest
            + self.other_costs
        )

    @property
    def net(self) -> float:
        return self.betting_pnl + self.subscriptions + self.other_income - self.expenses

    def add(self, other: "CostTotals") -> None:
        for name in CostTotals.model_fields:
            setattr(self, name, getattr(self, name) + getattr(other, name))


class Finances(Model):
    cash: float
    payables: float = 0.0  # accrued but unpaid salaries/rent/data/budgets (paid at month close)
    debt: float = 0.0
    marketing_budget: float = 60.0
    lab_budget: float = 60.0
    subscribers: int = 30
    subscription_price: float = 9.0
    hiring_frozen: bool = False
    status: CompanyStatus = "stable"
    totals: CostTotals = Field(default_factory=CostTotals)
    month: CostTotals = Field(default_factory=CostTotals)
    peak_value: float = 0.0
    peak_value_day: date | None = None
    max_drawdown: float = 0.0  # fraction from peak valuation
    record_cash: float = 0.0
    invested: float = 0.0  # outside money put into the company (sandbox investors)


class MonthlyReport(Model):
    month: str  # "2026-08"
    lines: CostTotals
    by_department: dict[str, float] = Field(default_factory=dict)
    end_cash: float
    end_bankroll: float
    end_debt: float
    valuation: float
    subscribers: int
    headcount: int
    bets: int


class DailyPoint(Model):
    day: date
    cash: float
    bankroll: float
    exposure: float
    debt: float
    payables: float
    valuation: float
    day_pnl: float
    subscribers: int
