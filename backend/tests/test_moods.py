"""Mood events: sick days, lost nerve, tilt, bragging, and the CEO's wellbeing actions."""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from app.agents import management
from app.agents.context import build_tipster_context
from app.agents.policies import tipster_policy
from app.ai.schemas import CEOAction
from app.simulation import moods
from app.simulation.engine import max_bets


class Always:
    """RNG stand-in: every coin flip returns `value`; everything else is a real RNG."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = value
        self._real = random.Random(1)

    def random(self) -> float:
        return self.value

    def choice(self, seq):
        return seq[0]

    def __getattr__(self, name):
        return getattr(self._real, name)


def _tipster(world):
    return sorted(world.tipsters(), key=lambda e: e.id)[0]


def test_burned_out_people_call_in_sick_and_rest(fresh):
    world, _, _ = fresh()
    e = _tipster(world)
    e.psyche.stress = 0.97
    moods.morning(world, Always(0.0))
    assert e.is_away(world.today) and e.status == "away" and e.task == "Off sick"
    assert world.stats.sick_days >= 1 and world.events[-1].kind == "sick_day"
    before = e.psyche.stress
    e.away_until = world.today  # back tomorrow
    moods.morning(world, Always(0.99))  # still away today: resting
    assert e.psyche.stress < before


def test_calm_people_never_call_in_sick(fresh):
    world, _, _ = fresh()
    for e in world.active_employees():
        e.psyche.stress = 0.3
    moods.morning(world, Always(0.0))
    assert not any(e.is_away(world.today) for e in world.active_employees())


def test_absent_tipsters_place_no_bets(fresh):
    world, _, engine = fresh()
    e = _tipster(world)
    moods.send_home(world, e, 30, "leave")
    asyncio.run(engine.run_days(10))
    assert not any(b.employee_id == e.id for b in world.bets.values())
    assert e.status == "away" or world.clock.phase_index == 0


def test_lost_nerve_means_passing_on_everything(fresh):
    world, _, engine = fresh()
    e = _tipster(world)
    e.psyche.confidence, e.streak = 0.15, -7
    moods.morning(world, Always(0.0))
    assert moods.frozen(e, world.today) and world.events[-1].kind == "lost_nerve"
    ctx = build_tipster_context(world, engine.index, e, [], {}, 3)
    assert ctx["agent"]["lost_nerve"] and any("nerve" in n for n in ctx["situation"])
    ctx["matches"] = [{"match_id": "m1", "candidates": [], "coworkers": []}]
    out = tipster_policy.decide_day(ctx, random.Random(1))
    assert all(d["decision"] == "NO_BET" for d in out["decisions"])


def test_big_losses_put_risk_takers_on_tilt(fresh):
    world, _, engine = fresh()
    e = _tipster(world)
    e.traits.risk_seeking, e.traits.cautious = 0.9, 0.0
    e.day_profit = -500.0
    moods.evening(world, Always(0.0))
    tomorrow = world.today + timedelta(days=1)
    assert e.tilt_on == tomorrow and world.stats.tilts == 1
    assert max_bets(e, tomorrow) == max_bets(e, world.today) + 1
    world.clock.now += timedelta(days=1)
    ctx = build_tipster_context(world, engine.index, e, [], {}, 4)
    assert ctx["agent"]["on_tilt"] and tipster_policy._state(ctx)["desperation"] >= 0.4


def test_cocky_winners_brag_and_wind_up_rivals(fresh):
    world, _, _ = fresh()
    dept = next(d for d in world.active_departments() if d.kind != "lab")
    a, b = [e for e in world.department_members(dept.id) if e.role == "tipster"][:2]
    a.mood, a.day_profit = "cocky", 400.0
    b.relationships[a.id].rivalry = 40
    before = b.relationships[a.id].rivalry
    moods.evening(world, Always(0.0))
    kinds = [ev.kind for ev in world.events[-2:]]
    assert "brag" in kinds and world.stats.brags == 1
    assert b.relationships[a.id].rivalry > before


def test_ceo_wellbeing_actions(fresh):
    world, _, _ = fresh()
    world.finances.cash = 5000
    e = _tipster(world)
    stress = {x.id: x.psyche.stress for x in world.active_employees()}
    recs = management.apply_actions(world, random.Random(1), [CEOAction(type="TEAM_EVENT", reason="morale")], "monthly")
    assert recs[0].applied and world.finances.cash < 5000
    assert all(x.psyche.stress <= stress[x.id] for x in world.active_employees())
    again = management.apply_actions(world, random.Random(1), [CEOAction(type="TEAM_EVENT")], "monthly")
    assert not again[0].applied  # cooldown
    off = management.apply_actions(world, random.Random(1),
                                   [CEOAction(type="GIVE_TIME_OFF", employee_id=e.id, value=4)], "weekly")
    assert off[0].applied and e.is_away(world.today + timedelta(days=3)) and not e.is_away(world.today + timedelta(days=4))
