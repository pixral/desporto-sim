"""Player mode: the clock waits for the CEO's briefing; decisions go through the usual validation."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta

import pytest

from app.ai.mock_provider import MockAgentModelProvider
from app.ai.schemas import CEOAction
from app.domain.player import Proposal
from app.domain.world import RunConfig, World
from app.providers import make_sports_provider
from app.simulation import player, views
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_world


def make(pause_mode: str = "every_review", seed: int = 5, **kw) -> SimulationEngine:
    cfg = RunConfig(seed=seed, player_ceo=True, player_name="Test Player", pause_mode=pause_mode, **kw)
    sports = make_sports_provider(cfg)
    world = create_world(cfg, sports)
    return SimulationEngine(world, sports, MockAgentModelProvider())


def run(coro):
    return asyncio.run(coro)


def test_player_founds_the_same_company_under_their_name():
    eng = make()
    watch = create_world(RunConfig(seed=5), make_sports_provider(RunConfig(seed=5)))
    assert eng.world.ceo().name == "Test Player"
    assert sorted(e.name for e in eng.world.tipsters()) == sorted(e.name for e in watch.tipsters())


def test_clock_stops_at_a_briefing_and_survives_a_save():
    eng = make()
    w = eng.world
    run(eng.run_days(30))
    assert player.awaiting(w) and w.today.weekday() == 0 and w.clock.now.time() == time(8, 0)
    day = w.clock.day_index
    assert run(eng.step()) == "awaiting_ceo"
    assert w.clock.day_index == day  # nothing moved
    loaded = World.model_validate_json(w.model_dump_json())
    assert loaded.player.review is not None and loaded.player.review.id == w.player.review.id
    view = views.review_view(w)
    assert view["open"] and view["scope"] == "weekly" and view["people"]


def test_resolving_applies_actions_with_the_usual_validation():
    eng = make()
    w = eng.world
    run(eng.run_days(30))
    review = w.player.review
    t = w.tipsters()[0]
    cand = w.candidates[0]
    desk = next(d for d in w.active_departments() if d.kind != "lab")
    records = run(eng.resolve_review([
        CEOAction(type="WARN", employee_id=t.id, reason="sloppy week"),
        CEOAction(type="HIRE", candidate_id=cand.id, department_id=desk.id),  # weekly: no hiring
        CEOAction(type="FIRE", employee_id="nobody"),
    ], "Focus, everyone."))
    assert [r.applied for r in records] == [True, False, False]
    assert records[1].result == "hiring limit for this review reached"
    assert records[2].result == "no such active employee"
    assert t.under_review and not player.awaiting(w)
    log = w.management_log[-1]
    assert log.by == "player" and log.memo == "Focus, everyone." and w.memos[-1].text == "Focus, everyone."
    assert len(log.skipped) == len(review.proposals)
    assert w.player.reviews_signed == 1
    assert run(eng.step()) == "analysis"  # the day carries on
    with pytest.raises(ValueError):
        run(eng.resolve_review([], ""))


def test_advisor_handles_the_reviews_the_player_skips_but_never_fires():
    eng = make(pause_mode="monthly", seed=3)
    w = eng.world
    run(eng.run_days(16))  # past the first Mondays, not yet the 1st
    assert not player.awaiting(w)
    weekly = [m for m in w.management_log if m.scope == "weekly"]
    assert weekly and all(m.by == "advisor" for m in weekly)
    assert not any(a.type == "FIRE" for m in weekly for a in m.actions)
    run(eng.run_days(30))
    assert player.awaiting(w) and w.player.review.scope == "monthly" and w.today.day == 1


def test_office_hours_limits_and_review_only_refusals():
    eng = make(pause_mode="events_only")
    w = eng.world
    run(eng.run_days(2))
    a, b = w.tipsters()[:2]
    assert eng.office_action(CEOAction(type="TALK", employee_id=a.id)).applied
    again = eng.office_action(CEOAction(type="TALK", employee_id=a.id))
    assert not again.applied and "already talked" in again.result
    hire = eng.office_action(CEOAction(type="HIRE", candidate_id=w.candidates[0].id, department_id="d1"))
    assert not hire.applied and "monthly review" in hire.result
    assert eng.office_action(CEOAction(type="FIRE", employee_id=a.id, reason="test")).applied
    second = eng.office_action(CEOAction(type="FIRE", employee_id=b.id))
    assert not second.applied and "this week's firing" in second.result
    assert w.management_log[-1].scope == "office" and len(w.management_log[-1].actions) == 2
    w.clock.now += timedelta(days=7)  # a new week resets the counters
    assert player.limits_left(w) == {"FIRE": 1, "TALK": 3}


def test_queued_decisions_reach_the_monthly_briefing():
    eng = make(pause_mode="monthly")
    w = eng.world
    with pytest.raises(ValueError):
        player.queue(w, CEOAction(type="WARN", employee_id=w.tipsters()[0].id))  # do that now
    p = player.queue(w, CEOAction(type="LEASE_SPACE", facility="canteen", reason="lunch"))
    assert isinstance(p, Proposal) and p.label == "Lease the Canteen" and p.area == "office"
    cand = w.candidates[0]
    desk = next(d for d in w.active_departments() if d.kind != "lab")
    cand.expires = w.today + timedelta(days=3)  # would leave the pool before the 1st...
    player.queue(w, CEOAction(type="HIRE", candidate_id=cand.id, department_id=desk.id))
    assert cand.expires == date(2026, 9, 2)  # ...but agrees to wait for the review
    run(eng.run_days(25))
    assert player.awaiting(w) and w.player.review.scope == "monthly"
    view = views.review_view(w)
    assert [q["action"].get("facility") for q in view["queue"]] == ["canteen", None]
    assert cand in w.candidates
    run(eng.resolve_review([CEOAction(**q.action) for q in w.player.queue], ""))
    assert w.player.queue == [] and "canteen" in w.office.leased


def test_board_warns_then_fires_the_player():
    eng = make()
    w = eng.world
    player.board_review(w, collapsed=True, value=5000)
    assert w.player.board_warned is not None and not w.ended
    assert w.events[-1].kind == "board_warning"
    w.clock.now += timedelta(days=10)
    player.board_review(w, collapsed=True, value=5000)
    assert not w.ended  # still inside the grace period
    w.clock.now += timedelta(days=30)
    player.board_review(w, collapsed=True, value=5000)
    assert w.ended and w.end_kind == "fired" and w.summary and w.summary.end_kind == "fired"


def test_board_only_warns_on_easy_and_forgives_a_recovery():
    eng = make(difficulty="easy")
    w = eng.world
    for _ in range(4):
        player.board_review(w, collapsed=True, value=5000)
        w.clock.now += timedelta(days=40)
    assert not w.ended
    player.board_review(w, collapsed=False, value=0.7 * w.config.starting_capital)
    assert w.player.board_warned is None and w.events[-1].kind == "board_relief"


def test_five_seasons_then_retirement():
    eng = make()
    w = eng.world
    assert player.seasons_completed(w, date(2027, 5, 31)) == 0
    assert player.seasons_completed(w, date(2027, 6, 1)) == 1
    assert player.seasons_completed(w, date(2031, 6, 1)) == 5
    w.clock.now = datetime.combine(date(2030, 6, 1), time(8, 0))
    player.check_retirement(w)
    assert not w.ended
    w.clock.now = datetime.combine(date(2031, 6, 1), time(8, 0))
    player.check_retirement(w)
    assert w.ended and w.end_kind == "retired" and "retires" in (w.end_reason or "")


def test_watch_mode_has_no_player_state():
    cfg = RunConfig(seed=5)
    sports = make_sports_provider(cfg)
    eng = SimulationEngine(create_world(cfg, sports), sports, MockAgentModelProvider())
    run(eng.run_days(10))
    assert eng.world.player.review is None and views.state_view(eng.world)["player"] is None
    assert all(m.by == "ai" for m in eng.world.management_log)
    assert eng.office_action(CEOAction(type="TALK", employee_id=eng.world.tipsters()[0].id)).applied is False


def test_lab_brief_is_set_at_monthly_reviews_and_steers_research():
    eng = make(pause_mode="monthly", seed=4)
    w = eng.world
    weekly = eng.office_action(CEOAction(type="SET_LAB_BRIEF", field="competition:PL"))
    assert not weekly.applied  # review-only
    run(eng.run_days(25))
    assert w.player.review.scope == "monthly"
    rec = run(eng.resolve_review([CEOAction(type="SET_LAB_BRIEF", field="competition:PL", reason="England")], ""))[0]
    assert rec.applied and w.player.lab_brief["value"] == "PL"
    before = set(w.experiments)
    w.finances.lab_budget = 160  # more parallel experiments, more ideas to look at
    for _ in range(3):
        run(eng.run_days(10))
        if player.awaiting(w):
            run(eng.resolve_review([], ""))
    new = [x for k, x in w.experiments.items() if k not in before]
    assert new, "the LAB should have started experiments"
    assert all("brief" in x.rationale for x in new)
    followed = [x for x in new if "following the brief" in x.rationale]
    assert followed and all(w.strategies[x.strategy_id].competitions == ["PL"] for x in followed)


def test_player_chooses_which_applicants_the_lab_tests():
    eng = make(pause_mode="events_only", seed=6)
    w = eng.world
    run(eng.run_days(3))
    cand = next(c for c in w.candidates if c.role == "tipster" and c.strategy_id)
    w.finances.lab_budget = 160
    rec = eng.office_action(CEOAction(type="TEST_CANDIDATE", candidate_id=cand.id))
    assert rec.applied, rec.result
    assert cand.lab_test_due is not None and cand.lab_test_due.weekday() == 0
    again = eng.office_action(CEOAction(type="TEST_CANDIDATE", candidate_id=cand.id))
    assert not again.applied and "already being tested" in again.result
    while w.today < cand.lab_test_due:
        run(eng.run_days(1))
    assert cand in w.candidates and cand.lab_backtest_n is not None
    assert any(e.kind == "candidate_tests" for e in w.events)
    untested = [c for c in w.candidates if c.lab_backtest_n is None and c.lab_test_due is None]
    assert untested, "in player mode the LAB doesn't test everyone automatically"


def test_shelving_a_finished_experiment():
    eng = make(pause_mode="monthly")
    w = eng.world
    run(eng.run_days(25))
    from app.domain.lab import Experiment

    s = next(iter(w.strategies.values()))
    x = Experiment(id="x99", researcher_id=w.active_employees("researcher")[0].id, name="Idea", hypothesis="h",
                   strategy_id=s.id, started=w.today, due=w.today, status="completed", recommendation="PROMISING")
    w.experiments[x.id] = x
    assert any(r["id"] == "x99" for r in views.review_view(w)["lab"]["ready"])
    recs = run(eng.resolve_review([CEOAction(type="SHELVE_STRATEGY", experiment_id="x99")], ""))
    assert recs[0].applied and x.status == "shelved"
