"""Bookmakers limit winning accounts."""

from __future__ import annotations

from datetime import timedelta

from app.domain.betting import Bet
from app.domain.sports import Match, OddsLine
from app.economy import bookmakers
from app.economy import config as EC


def _match(world, prices: dict[str, float]) -> Match:
    line = lambda p: OddsLine(home_win=p, draw=3.4, away_win=3.0, over_2_5=1.9, under_2_5=1.9)  # noqa: E731
    return Match(id="mX", competition="BL1", season="2026", stage="R1", home_id="a", away_id="b",
                 kickoff=world.clock.now, odds={b: line(p) for b, p in prices.items()})


def _desk(world):
    return next(d for d in world.active_departments() if d.kind != "lab")


def test_best_price_when_the_stake_fits(fresh):
    world, _, _ = fresh()
    m = _match(world, {"Atlas": 2.00, "Nordbet": 2.05, "Kicko": 2.10})
    book, price, stake, note = bookmakers.choose_book(_desk(world), m, "home_win", 50)
    assert (book, price, stake, note) == ("Kicko", 2.10, 50, "")


def test_limited_desk_moves_to_a_worse_price(fresh):
    world, _, _ = fresh()
    desk = _desk(world)
    desk.book_limits["Kicko"] = 20
    m = _match(world, {"Atlas": 2.00, "Nordbet": 2.05, "Kicko": 2.10})
    book, price, stake, note = bookmakers.choose_book(desk, m, "home_win", 50)
    assert book == "Nordbet" and price == 2.05 and stake == 50 and "Kicko limits" in note


def test_stake_is_cut_when_nobody_takes_it(fresh):
    world, _, _ = fresh()
    desk = _desk(world)
    m = _match(world, {"Atlas": 2.00, "Nordbet": 2.05, "Kicko": 2.10})
    book, price, stake, note = bookmakers.choose_book(desk, m, "home_win", 10_000)
    assert book == "Atlas" and stake == EC.BOOK_LIMITS["Atlas"] and "cut" in note


def _settled(world, desk, book: str, n: int, won_every: int, stake: float = 40, odds: float = 2.2):
    t = world.clock.now - timedelta(days=10)
    emp = next(e for e in world.department_members(desk.id) if e.role == "tipster")
    for i in range(n):
        won = i % won_every == 0
        b = Bet(id=world.next_id("b"), placed=t, employee_id=emp.id, department_id=desk.id, match_id="m",
                match_label="x", competition="BL1", market="home_win", selection="x", book=book, odds=odds,
                stake=stake, confidence=0.5, status="won" if won else "lost", settled=t,
                payout=round(stake * odds, 2) if won else 0.0)
        world.bets[b.id] = b


def test_soft_books_limit_winners_and_atlas_only_runaways(fresh):
    world, _, _ = fresh()
    desk = _desk(world)
    _settled(world, desk, "Kicko", 60, won_every=1)  # wins every bet: blatant
    _settled(world, desk, "Atlas", 60, won_every=1)  # +€2.9k at Atlas: welcome
    changes = bookmakers.review_limits(world)
    assert [(c[1], c[3]) for c in changes] == [("Kicko", round(EC.BOOK_LIMITS["Kicko"] * 0.35))]
    assert bookmakers.limit(desk, "Atlas") == EC.BOOK_LIMITS["Atlas"]
    _settled(world, desk, "Atlas", 60, won_every=1, stake=200)  # a runaway: +€14k more
    bookmakers.review_limits(world)
    assert bookmakers.limit(desk, "Atlas") == round(EC.BOOK_LIMITS["Atlas"] * 0.6)


def test_small_or_losing_desks_are_left_alone_and_losers_get_limits_back(fresh):
    world, _, _ = fresh()
    desk = _desk(world)
    _settled(world, desk, "Nordbet", 20, won_every=1)  # too few bets to matter
    assert bookmakers.review_limits(world) == []
    desk.book_limits["Kicko"] = 50
    _settled(world, desk, "Kicko", 60, won_every=4)  # losing at Kicko
    bookmakers.review_limits(world)
    assert bookmakers.limit(desk, "Kicko") == 65


def test_engine_records_limit_events(fresh):
    world, _, engine = fresh()
    desk = _desk(world)
    _settled(world, desk, "Kicko", 60, won_every=1)
    engine._bookmaker_reviews()
    ev = world.events[-1]
    assert ev.kind == "book_limit" and ev.department_id == desk.id and "Kicko limits" in ev.title
