"""Deterministic psychology updates.

These rules move *state* (stress, confidence, reputation, risk tolerance). They never decide
anything. Decisions are made by the judgement layer, which sees this state together with the
company situation and may react to it in its own way.
"""

from __future__ import annotations

import math
import random

from app.domain.base import Model, clamp
from app.domain.betting import Bet
from app.domain.people import Employee
from app.domain.world import World
from app.economy.config import CANTEEN_STRESS_RELIEF

STATUS_DISTRESS = {"thriving": 0.0, "stable": 0.15, "strained": 0.45, "distress": 0.8, "bankrupt": 1.0}


class DayContext(Model):
    distress: float
    company_thriving: bool
    dept_month_profit: float
    recent_layoffs: int
    recent_roi: float
    recent_bets: int
    day_profit: float
    canteen: bool = False  # the company runs a canteen (see economy.config.FACILITIES)


def baseline_confidence(emp: Employee) -> float:
    return 0.45 + 0.2 * emp.traits.aggressive - 0.1 * emp.traits.cautious


def baseline_risk(emp: Employee) -> float:
    t = emp.traits
    return clamp(0.2 + 0.4 * t.risk_seeking + 0.2 * t.aggressive - 0.2 * t.cautious, 0.05, 0.9)


def on_bet_settled(emp: Employee, bet: Bet, max_stake: float) -> None:
    """Outcome-driven confidence change. Analytical people partly judge process (CLV) instead."""
    won = bet.status == "won"
    if won:
        delta = 0.03 * math.sqrt(min(max(bet.odds - 1.0, 0.05), 3.0))
        emp.streak = emp.streak + 1 if emp.streak >= 0 else 1
    else:
        delta = -0.025 * math.sqrt(clamp(bet.stake / max(max_stake, 1.0), 0.1, 2.0))
        emp.streak = emp.streak - 1 if emp.streak <= 0 else -1
    clv = bet.clv
    if clv is not None:
        a = emp.traits.analytical * 0.5
        delta = (1 - a) * delta + a * clamp(clv * 0.5, -0.03, 0.03)
    delta *= 1.0 - 0.5 * emp.traits.stubborn
    emp.psyche.confidence = clamp(emp.psyche.confidence + delta, 0.05, 0.95)
    emp.best_streak = max(emp.best_streak, emp.streak)
    emp.worst_streak = min(emp.worst_streak, emp.streak)


def daily_update(emp: Employee, ctx: DayContext) -> None:
    t, p = emp.traits, emp.psyche
    losing = min(1.0, max(0, -emp.streak) / 6)
    winning = min(1.0, max(0, emp.streak) / 5)
    dept_pain = min(1.0, max(0.0, -ctx.dept_month_profit) / 300.0)
    target = (
        0.18
        + 0.30 * ctx.distress
        + 0.18 * emp.under_review
        + 0.12 * losing
        + 0.10 * dept_pain
        + 0.06 * min(3, ctx.recent_layoffs)
        + 0.08 * max(0.0, (50 - p.reputation) / 50)
        - 0.08 * winning
        - 0.05 * ctx.company_thriving
        - CANTEEN_STRESS_RELIEF * ctx.canteen
    )
    sensitivity = 0.75 + 0.5 * t.cautious - 0.35 * t.aggressive + 0.2 * t.ambitious
    p.stress += 0.12 * (clamp(target * sensitivity, 0.02, 0.98) - p.stress)
    if ctx.day_profit > 0:
        p.stress -= 0.02
    elif ctx.day_profit < 0:
        p.stress += 0.03 * (0.6 + t.cautious)
    p.stress = clamp(p.stress, 0.02, 0.98)

    p.confidence = clamp(p.confidence + 0.015 * (baseline_confidence(emp) - p.confidence), 0.05, 0.95)

    desperation = emp.under_review * max(0.0, p.stress - 0.5) * (0.5 + t.ambitious + t.risk_seeking * 0.5)
    hubris = max(0.0, p.confidence - 0.7) * (0.5 + t.aggressive)
    fear = max(0.0, 0.35 - p.confidence) * (0.5 + t.cautious)
    risk_target = clamp(baseline_risk(emp) + 0.5 * desperation + 0.4 * hubris - 0.6 * fear, 0.03, 0.97)
    p.risk_tolerance = clamp(p.risk_tolerance + 0.05 * (risk_target - p.risk_tolerance), 0.03, 0.97)

    sample = min(1.0, ctx.recent_bets / 40)
    rep_target = (
        45 + 5 * emp.level
        + clamp(ctx.recent_roi * 250, -30, 30) * sample
        - 8 * emp.under_review
        + 4 * min(emp.promotions, 3)
        - 3 * min(emp.warnings, 3)
    )
    p.reputation = clamp(p.reputation + 0.04 * (rep_target - p.reputation), 0, 100)
    emp.mood = mood_label(emp)


def researcher_daily_update(emp: Employee, distress: float, lab_budget_ratio: float, canteen: bool = False) -> None:
    p, t = emp.psyche, emp.traits
    target = 0.15 + 0.3 * distress + 0.15 * max(0.0, 1 - lab_budget_ratio) - CANTEEN_STRESS_RELIEF * canteen
    sensitivity = 0.8 + 0.4 * t.cautious
    p.stress = clamp(p.stress + 0.08 * (target * sensitivity - p.stress), 0.02, 0.98)
    emp.mood = mood_label(emp)


def mood_label(emp: Employee) -> str:
    p = emp.psyche
    if p.stress > 0.8:
        return "burned out" if p.confidence < 0.35 else "frantic"
    if emp.under_review and p.stress > 0.6 and p.risk_tolerance > 0.55:
        return "desperate"
    if p.confidence > 0.75 and emp.streak >= 3:
        return "cocky"
    if p.confidence > 0.62:
        return "confident"
    if p.confidence < 0.3:
        return "shaken"
    if p.stress > 0.55:
        return "anxious"
    return "calm" if p.stress < 0.25 else "focused"


def resignation_reason(world: World, emp: Employee, distress: float, rng: random.Random) -> str | None:
    """Rare burnout exits. (Being poached by rivals is handled explicitly in simulation/drama.py.)"""
    p, t = emp.psyche, emp.traits
    prob = 0.0
    if p.stress > 0.78:
        prob += 0.004 * (p.stress - 0.78) / 0.22 * (1 + t.ambitious) * (1 + 0.5 * distress)
    if emp.tenure_days(world.today) < 21:
        prob *= 0.2
    if rng.random() >= prob:
        return None
    return "burned out and resigned"
