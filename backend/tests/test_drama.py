"""Workplace drama: arguments, poaching, the board, season awards."""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from app.simulation import drama


class Always:
    """RNG stand-in: every coin flip takes the dramatic branch; everything else is a real RNG."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = value
        self._real = random.Random(1)

    def random(self) -> float:
        return self.value

    def choice(self, seq):
        return seq[0]

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_rivals_argue_after_opposite_days(fresh):
    world, _, _ = fresh()
    dept = next(d for d in world.active_departments() if d.kind != "lab")
    a, b = [e for e in world.department_members(dept.id) if e.role == "tipster"][:2]
    a.relationships[b.id].rivalry = b.relationships[a.id].rivalry = 80
    trust_before = a.relationships[b.id].trust
    a.day_profit, b.day_profit = 40.0, -30.0
    drama.daily(world, Always())
    ev = next(e for e in world.events if e.kind == "argument")
    assert set(ev.employee_ids) == {a.id, b.id} and ev.employee_ids[0] == a.id  # winner speaks first
    assert set(ev.data["lines"]) == {a.id, b.id}
    assert a.relationships[b.id].trust < trust_before
    # one scene per desk per week
    drama.daily(world, Always())
    assert sum(1 for e in world.events if e.kind == "argument") == 1


def _make_star(world, e, bets=150):
    """Give an employee a strong, long track record."""
    from app.domain.betting import Bet

    e.hired = world.today - timedelta(days=300)
    e.psyche.reputation = 80
    for i in range(bets):
        won = i % 2 == 0
        b = Bet(id=f"sb{i}", placed=world.clock.now, employee_id=e.id, department_id=e.department_id,
                match_id="m", match_label="X vs Y", competition="PL", market="home_win", selection="X", book="Atlas",
                odds=2.4, stake=10.0, confidence=0.6, status="won" if won else "lost",
                settled=world.clock.now, payout=24.0 if won else 0.0)
        world.bets[b.id] = b
        e.bet_ids.append(b.id)


def test_rival_syndicate_poaches_a_star_unless_the_ceo_counters(fresh):
    world, _, _ = fresh(style="aggressive_expansionist")
    star = world.tipsters()[0]
    _make_star(world, star)
    salary = star.salary
    drama._poaching(world, Always(0.0))  # offer happens; aggressive CEO counters
    assert any(e.kind == "poach_offer" for e in world.events)
    assert any(e.kind == "counter_offer" for e in world.events) and star.salary > salary and star.active

    world2, _, _ = fresh(style="conservative_operator")
    star2 = world2.tipsters()[0]
    _make_star(world2, star2)
    world2.finances.cash = 0.0  # cannot afford a counter-offer
    drama._poaching(world2, Always(0.0))
    assert not star2.active and star2.leave_reason.startswith("poached by")
    assert any(e.kind == "poached" for e in world2.events)


def test_board_replaces_a_ceo_who_wrecked_the_company(fresh):
    world, _, _ = fresh(style="chaotic_founder")
    old = world.ceo()
    drama._board_review(world, Always())
    assert world.ceo().id == old.id  # too early: the board waits at least 180 days
    world.clock.day_index = 400
    old.hired = world.today - timedelta(days=400)
    for d in world.active_departments():
        d.bankroll = 0.0
    world.finances.cash = 2000.0
    drama._board_review(world, Always())
    new = world.ceo()
    assert new.id != old.id and not old.active and new.ceo_style != "chaotic_founder"
    assert new.name != old.name
    assert world.config.ceo_style == new.ceo_style and world.stats.ceo_changes == 1
    kinds = [e.kind for e in world.events]
    assert "board_fires_ceo" in kinds and "new_ceo" in kinds
    assert world.memos[-1].author_id == new.id
    drama._board_review(world, Always())
    assert world.ceo().id == new.id  # at most once a year


def test_season_awards_name_the_mvp(fresh):
    world, _, engine = fresh(seed=6)
    asyncio.run(engine.run_days(120))
    recap = drama.season_awards(world)
    assert recap is not None and recap.awards
    titles = [a.title for a in recap.awards]
    assert "Biggest win" in titles and "Desk of the season" in titles
    if "MVP" in titles:
        mvp = recap.awards[titles.index("MVP")]
        assert mvp.employee_id in world.employees
    assert world.events[-1].kind == "season_awards" and world.events[-1].data["recap_id"] == recap.id
    assert drama.season_awards(world) is None  # once per season
