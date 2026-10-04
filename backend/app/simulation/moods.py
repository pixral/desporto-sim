"""Mood events: when feelings turn into things that happen.

- Sick days: burned-out people sometimes stay home (no bets that day); rest lowers their stress.
- Lost nerve: a shaken tipster on a losing run can't bring themselves to back anything for a few days.
- Tilt: after a heavy losing day, desperate or risk-loving tipsters chase their losses the next day.
- Bragging: a cocky (or confident, after a huge day) winner winds up rivals at the desk, sometimes into an argument.

The states are facts about a person (shown to the AI in its context); how much they change decisions is up to
the judgement layer (the mock policy follows them, an LLM is told about them). Deterministic given the RNG.
"""

from __future__ import annotations

import random
from datetime import timedelta

from app.agents.context import allocation_for
from app.domain.base import clamp
from app.domain.people import Employee
from app.domain.world import World

from . import drama, history

SICK_STRESS = 0.8  # frantic / burned out
REST_PER_DAY = {"sick": 0.04, "leave": 0.07}
NERVE_CONFIDENCE = 0.28
TILT_COOLDOWN_DAYS = 14
BRAG_LINES = ("Read it and weep.", "That's how it's done.", "Another day at the office.", "Too easy.")


def morning(world: World, rng: random.Random) -> None:
    """Who is in today: returns from leave, new sick days, nerves lost and found. Runs after the morning reset."""
    today = world.today
    for e in sorted(world.active_employees(), key=lambda e: e.id):
        if e.role == "ceo":
            continue
        if e.away_until is not None and e.away_until < today:
            reason = e.away_reason
            e.away_until, e.away_reason = None, ""
            history.record(world, "back_at_work", f"{e.name} is back {'from leave' if reason == 'leave' else 'at work'}",
                           "", 1, "neutral", [e.id], e.department_id)
        if e.is_away(today):
            e.psyche.stress = clamp(e.psyche.stress - REST_PER_DAY.get(e.away_reason, 0.04), 0.02, 0.98)
            e.status, e.task = "away", "On leave" if e.away_reason == "leave" else "Off sick"
            continue
        _maybe_sick(world, rng, e)
        if e.role == "tipster" and not e.is_away(today):
            _nerve(world, rng, e)


def _maybe_sick(world: World, rng: random.Random, e: Employee) -> None:
    p = e.psyche
    if p.stress < SICK_STRESS:
        return
    prob = (0.015 + 0.12 * (p.stress - SICK_STRESS) / (0.98 - SICK_STRESS)) * (1.5 if p.confidence < 0.35 else 1.0)
    if rng.random() >= prob:
        return
    days = rng.randint(1, 3)
    send_home(world, e, days, "sick")
    world.stats.sick_days += days
    history.record(world, "sick_day", f"{e.name} calls in sick", f"Stress {p.stress:.0%}. Out for {days} day(s).",
                   1, "bad", [e.id], e.department_id)


def send_home(world: World, e: Employee, days: int, reason: str) -> None:
    e.away_until = world.today + timedelta(days=days - 1)
    e.away_reason = reason
    e.status, e.task = "away", "On leave" if reason == "leave" else "Off sick"
    e.tilt_on = None


def _nerve(world: World, rng: random.Random, e: Employee) -> None:
    today = world.today
    p, t = e.psyche, e.traits
    if e.frozen_until is not None:
        if today > e.frozen_until or p.confidence > 0.4:
            e.frozen_until = None
            history.record(world, "found_nerve", f"{e.name} finds their nerve again", "", 1, "good", [e.id],
                           e.department_id)
        return
    if p.confidence < NERVE_CONFIDENCE and e.streak <= -4 and rng.random() < 0.15 + 0.3 * t.cautious:
        days = rng.randint(3, 6)
        e.frozen_until = today + timedelta(days=days - 1)
        world.stats.nerves_lost += 1
        history.record(world, "lost_nerve", f"{e.name} has lost their nerve",
                       f"{-e.streak} losses in a row, confidence {p.confidence:.0%}. Can't pull the trigger.",
                       1, "drama", [e.id], e.department_id)


def evening(world: World, rng: random.Random) -> None:
    """After settlement: who goes on tilt for tomorrow, who brags about today."""
    today = world.today
    for e in sorted(world.tipsters(), key=lambda e: e.id):
        if e.is_away(today) or not e.day_profit:
            continue
        _, max_stake = allocation_for(world, e)
        if e.day_profit < 0:
            _tilt(world, rng, e, max_stake)
        else:
            _brag(world, rng, e, max_stake)


def _tilt(world: World, rng: random.Random, e: Employee, max_stake: float) -> None:
    if -e.day_profit < max(3.0 * max_stake, 30.0):
        return
    if e.tilt_on is not None and (world.today - e.tilt_on).days < TILT_COOLDOWN_DAYS - 1:
        return  # one tilt every couple of weeks, not a daily spiral
    t, p = e.traits, e.psyche
    prone = 0.05 + 0.4 * t.risk_seeking + 0.2 * t.ambitious - 0.4 * t.cautious + 0.25 * p.stress + 0.2 * e.under_review
    if rng.random() >= clamp(prone, 0.02, 0.7):
        return
    e.tilt_on = world.today + timedelta(days=1)
    world.stats.tilts += 1
    history.record(world, "tilt", f"{e.name} is on tilt after losing €{-e.day_profit:,.0f}",
                   "Wants it all back tomorrow.", 1, "drama", [e.id], e.department_id)


def _brag(world: World, rng: random.Random, e: Employee, max_stake: float) -> None:
    big = e.day_profit >= max(1.5 * max_stake, 20.0)
    huge = e.day_profit >= max(2.5 * max_stake, 40.0)
    if not ((e.mood == "cocky" and big) or (e.mood == "confident" and huge)):
        return
    last = world.milestones.get(f"brag:{e.id}")
    if last is not None and world.today.toordinal() - int(last) < 5:
        return
    rivals = [x for x in world.department_members(e.department_id or "")
              if x.id != e.id and x.role == "tipster" and not x.is_away(world.today)
              and max(x.relationships.get(e.id).rivalry if x.relationships.get(e.id) else 0,
                      e.relationships.get(x.id).rivalry if e.relationships.get(x.id) else 0) >= 20]
    if not rivals or rng.random() >= 0.35:
        return
    world.milestones[f"brag:{e.id}"] = world.today.toordinal()
    world.stats.brags += 1
    line = rng.choice(BRAG_LINES)
    for r in rivals:
        rel = r.relationships.get(e.id)
        if rel:
            rel.rivalry = clamp(rel.rivalry + 5, 0, 100)
            rel.trust = clamp(rel.trust - 3, 0, 100)
        r.psyche.stress = clamp(r.psyche.stress + 0.02, 0.02, 0.98)
    history.record(world, "brag", f"{e.name} brags about a €{e.day_profit:,.0f} day", f'"{line}"', 1, "drama",
                   [e.id], e.department_id, {"lines": {e.id: line}})
    target = max(rivals, key=lambda r: r.relationships[e.id].rivalry if e.id in r.relationships else 0)
    temper = (target.traits.aggressive + target.traits.stubborn) / 2
    if e.id in target.relationships and target.id in e.relationships and rng.random() < 0.25 + 0.35 * temper:
        drama.argue(world, rng, e, target, e.department_id, w_line=line)


def tilted(e: Employee, today) -> bool:
    return e.tilt_on == today


def frozen(e: Employee, today) -> bool:
    return e.frozen_until is not None and today <= e.frozen_until
