"""Deterministic performance metrics derived from the bet ledger. Plain code, no AI."""

from __future__ import annotations

import math
from datetime import date, timedelta

from app.domain.base import Model
from app.domain.betting import Bet
from app.domain.people import Employee
from app.domain.world import World


class PerfStats(Model):
    bets: int = 0
    wins: int = 0
    staked: float = 0.0
    profit: float = 0.0
    roi: float = 0.0
    z: float = 0.0  # profit relative to luck: >2 is hard to explain by chance

    @classmethod
    def from_bets(cls, bets: list[Bet]) -> "PerfStats":
        s = cls()
        var = 0.0
        for b in bets:
            s.bets += 1
            s.wins += int(b.status == "won")
            s.staked += b.stake
            s.profit += b.profit
            var += b.stake * b.stake * max(b.odds - 1.0, 0.01)
        s.roi = s.profit / s.staked if s.staked > 0 else 0.0
        s.z = s.profit / math.sqrt(var) if var > 0 else 0.0
        return s


def settled_bets(world: World, emp: Employee) -> list[Bet]:
    """Most recent first."""
    out = []
    for bid in reversed(emp.bet_ids):
        b = world.bets.get(bid)
        if b is not None and b.status != "open":
            out.append(b)
    return out


def recent_stats(world: World, emp: Employee, n: int = 30) -> PerfStats:
    return PerfStats.from_bets(settled_bets(world, emp)[:n])


def period_stats(world: World, emp: Employee, days: int) -> PerfStats:
    cutoff = world.today - timedelta(days=days)
    bets = [b for b in settled_bets(world, emp) if b.settled and b.settled.date() > cutoff]
    return PerfStats.from_bets(bets)


def department_stats(world: World, dept_id: str, days: int) -> PerfStats:
    cutoff = world.today - timedelta(days=days)
    bets = [b for b in world.bets.values()
            if b.department_id == dept_id and b.status != "open" and b.settled and b.settled.date() > cutoff]
    return PerfStats.from_bets(bets)


def company_stats(world: World, days: int) -> PerfStats:
    cutoff = world.today - timedelta(days=days)
    bets = [b for b in world.bets.values() if b.status != "open" and b.settled and b.settled.date() > cutoff]
    return PerfStats.from_bets(bets)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def bankroll_total(world: World) -> float:
    return sum(d.bankroll for d in world.departments.values() if d.active)


def exposure_total(world: World) -> float:
    return sum(world.bets[b].stake for b in world.open_bet_ids if b in world.bets)
