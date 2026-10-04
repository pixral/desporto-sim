"""Bookmakers limit winning accounts.

Soft books (Kicko, then Nordbet) cut the maximum stake of a desk that keeps winning money from them; the sharp
book (Atlas) takes big stakes and offers the tightest prices, and only reins in blatant runaways. A desk that
wins a lot is pushed towards worse prices and smaller stakes, so success can't compound forever. Pure code,
no randomness.
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.company import Department
from app.domain.sports import Match
from app.domain.world import World

from . import config as C


def limit(dept: Department, book: str) -> float:
    return dept.book_limits.get(book, C.BOOK_LIMITS.get(book, float("inf")))


def choose_book(dept: Department, match: Match, market: str, stake: float) -> tuple[str, float, float, str] | None:
    """Where to place a bet: the best price whose limit takes the whole stake; failing that, the most generous
    book, with the stake cut to its limit. Returns (book, price, stake, note) or None if nobody prices it."""
    offers = sorted(((book, line.get(market)) for book, line in match.odds.items()), key=lambda o: -o[1])
    if not offers:
        return None
    best_book, best_price = offers[0]
    for book, price in offers:
        if limit(dept, book) >= stake:
            note = "" if book == best_book else (
                f"{best_book} limits this desk to €{limit(dept, best_book):.0f}: booked at {book} {price:.2f} "
                f"instead of {best_price:.2f}")
            return book, price, stake, note
    book, price = max(offers, key=lambda o: (limit(dept, o[0]), o[1]))
    capped = limit(dept, book)
    return book, price, capped, f"stake cut from €{stake:.0f} to €{capped:.0f} by bookmaker limits"


def review_limits(world: World) -> list[tuple[Department, str, float, float]]:
    """Monthly: soft books cut limits for desks that won real money from them, and slowly restore limits for
    desks that are losing. Returns (desk, book, old, new) for every change."""
    since = world.clock.now - timedelta(days=C.BOOK_REVIEW_DAYS)
    changes: list[tuple[Department, str, float, float]] = []
    for dept in world.active_departments():
        if dept.kind == "lab":
            continue
        for book, policy in C.BOOK_LIMIT_POLICY.items():
            bets = [b for b in world.bets.values() if b.department_id == dept.id and b.book == book
                    and b.settled is not None and b.settled >= since and b.status in ("won", "lost")]
            if len(bets) < C.BOOK_LIMIT_MIN_BETS:
                continue
            staked = sum(b.stake for b in bets)
            profit = sum(b.profit for b in bets)
            old = limit(dept, book)
            new = old
            min_profit = policy.get("min_profit", C.BOOK_LIMIT_MIN_PROFIT)
            min_roi = policy.get("min_roi", C.BOOK_LIMIT_MIN_ROI)
            if profit >= min_profit and staked and profit / staked >= min_roi:
                new = max(policy["floor"], round(old * policy["cut"], 0))
            elif profit < 0:
                new = min(C.BOOK_LIMITS[book], round(old * policy["restore"], 0))
            if new != old:
                dept.book_limits[book] = new
                changes.append((dept, book, old, new))
    return changes
