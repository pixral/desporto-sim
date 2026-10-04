"""Office leases, review meetings and the sandbox tools."""

from __future__ import annotations

import random

import pytest

from app.agents import management, psychology
from app.ai.schemas import CEOAction
from app.economy import accounting, market
from app.economy import valuation as val
from app.simulation import drama, god


# ---------------------------------------------------------------------------------- office
def test_lease_costs_fit_out_and_rent(fresh):
    world, _, _ = fresh()
    world.finances.cash = 5000
    cost_before = val.estimated_operating_cost(world)
    ok, msg = management.lease_facility(world, "canteen")
    assert ok, msg
    assert world.finances.cash < 5000 and world.finances.month.other_costs > 0
    assert val.estimated_operating_cost(world) > cost_before
    assert any(e.kind == "facility_leased" for e in world.events)
    ok, _ = management.lease_facility(world, "canteen")
    assert not ok  # already leased


def test_desk_wing_adds_a_seventh_room(fresh):
    world, _, _ = fresh()
    world.finances.cash = 5000
    for slot in range(6):  # fill the original floor
        if management.free_room_slot(world) is None:
            break
        management.create_department(world, ["spain", "italy", "goals", "england", "europe", "markets"][slot], 100)
    assert management.free_room_slot(world) is None
    management.lease_facility(world, "desk_wing", free=True)
    assert management.free_room_slot(world) == 6


def test_cannot_release_the_wing_while_a_desk_works_there(fresh):
    world, _, _ = fresh()
    management.lease_facility(world, "desk_wing", free=True)
    dept = next(d for d in world.active_departments() if d.kind != "lab")
    dept.room_slot = 6
    ok, msg = management.release_facility(world, "desk_wing")
    assert not ok and "desk" in msg


def test_ceo_leases_only_at_monthly_reviews(fresh):
    world, _, _ = fresh()
    world.finances.cash = 9000
    act = CEOAction(type="LEASE_SPACE", facility="studio", reason="test")
    weekly = management.apply_actions(world, random.Random(1), [act], "weekly")
    assert not weekly[0].applied
    monthly = management.apply_actions(world, random.Random(1), [act], "monthly")
    assert monthly[0].applied and market.leased(world, "studio")


def test_studio_brings_more_subscribers(fresh):
    world, _, _ = fresh()
    world.city.economy = 0.0
    twin = world.model_copy(deep=True)
    management.lease_facility(twin, "studio", free=True)
    assert accounting.subscriptions_update(twin)[0] > accounting.subscriptions_update(world)[0]


def test_canteen_lowers_stress_over_time(fresh):
    world, _, _ = fresh()
    a = next(e for e in world.tipsters())
    b = a.model_copy(deep=True)
    ctx = dict(distress=0.4, company_thriving=False, dept_month_profit=0.0, recent_layoffs=0,
               recent_roi=0.0, recent_bets=0, day_profit=0.0)
    for _ in range(60):
        psychology.daily_update(a, psychology.DayContext(**ctx))
        psychology.daily_update(b, psychology.DayContext(**ctx, canteen=True))
    assert b.psyche.stress < a.psyche.stress


# ---------------------------------------------------------------------------------- meetings
def test_review_meeting_has_desk_leads(fresh):
    world, _, _ = fresh()
    attendees = drama.gather_meeting(world, "weekly")
    desks = [d for d in world.active_departments() if d.kind != "lab" and world.department_members(d.id)]
    assert len(attendees) == len(desks)
    assert all(e.status == "meeting" and e.task == "Monday stand-up" for e in attendees)
    monthly = drama.gather_meeting(world, "monthly")
    assert len(monthly) == len(desks) + 1  # the LAB joins
    called = next(e for e in world.tipsters() if e not in monthly)
    again = drama.gather_meeting(world, "monthly", {called.id})
    assert again[0].id == called.id and again[0].task == "Called in by the CEO"
    assert len(again) <= 8


# ---------------------------------------------------------------------------------- sandbox
def test_investor_adds_cash_but_not_profit(fresh):
    world, _, _ = fresh()
    cash, net = world.finances.cash, world.finances.month.net
    god.apply(world, random.Random(1), "invest", {"amount": 10000})
    assert world.finances.cash == pytest.approx(cash + 10000)
    assert world.finances.month.net == pytest.approx(net)
    assert world.finances.invested == 10000 and world.stats.god_actions == 1
    assert world.events[-1].kind == "god" and world.events[-1].data["god"]


def test_disaster_costs_money_and_nerves(fresh):
    world, _, _ = fresh()
    stress = sum(e.psyche.stress for e in world.active_employees())
    value = val.valuation(world)
    god.apply(world, random.Random(1), "disaster", {"kind": "flood", "severity": "catastrophic"})
    assert val.valuation(world) < value
    assert sum(e.psyche.stress for e in world.active_employees()) > stress
    assert world.finances.month.other_costs > 0


def test_hack_loses_subscribers(fresh):
    world, _, _ = fresh()
    subs = world.finances.subscribers
    god.apply(world, random.Random(1), "disaster", {"kind": "hack", "severity": "major"})
    assert world.finances.subscribers < subs


def test_market_crash_hits_valuation_and_prints(fresh):
    world, _, _ = fresh()
    value = val.valuation(world)
    god.apply(world, random.Random(1), "market", {"sector": "betting", "pct": -0.3})
    assert val.valuation(world) < value
    assert world.city.press[-1].headline.startswith("Betting shares crash")


def test_planted_headline_moves_a_stock(fresh):
    world, _, _ = fresh()
    before = world.city.stocks["BRKH"].price
    god.apply(world, random.Random(1), "headline", {"headline": "Crane collapses at Brickhall site",
                                                    "ticker": "BRKH", "pct": -0.15, "section": "business"})
    assert world.city.stocks["BRKH"].price < before
    assert world.city.press[-1].headline == "Crane collapses at Brickhall site"


def test_replace_ceo_and_star_candidate(fresh):
    world, _, _ = fresh(style="data_driven")
    old = world.ceo().id
    god.apply(world, random.Random(1), "replace_ceo", {"style": "chaotic_founder"})
    assert world.ceo().id != old and world.ceo().ceo_style == "chaotic_founder"
    n = len(world.candidates)
    god.apply(world, random.Random(1), "star", {})
    assert len(world.candidates) == n + 1 and world.candidates[-1].cv_rating == 96


def test_bad_requests_are_rejected_and_not_counted(fresh):
    world, _, _ = fresh()
    with pytest.raises(god.GodError):
        god.apply(world, random.Random(1), "summon_dragon", {})
    with pytest.raises(god.GodError):
        god.apply(world, random.Random(1), "disaster", {"kind": "meteor"})
    assert world.stats.god_actions == 0


def test_free_facility_and_difficulty(fresh):
    world, _, _ = fresh()
    god.apply(world, random.Random(1), "facility", {"facility": "canteen"})
    assert market.leased(world, "canteen")
    god.apply(world, random.Random(1), "difficulty", {"level": "hard"})
    assert world.config.difficulty == "hard" and world.stats.god_actions == 2
