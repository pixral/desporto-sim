"""Walk-forward backtester. Each match is evaluated with only the data available that morning."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time

from app.domain.sports import Match
from app.domain.strategy import BacktestResult, Strategy

from .index import SportsIndex
from .models import best_candidate, estimate_match

DECISION_TIME = time(11, 0)


def backtest(index: SportsIndex, matches: Iterable[Match], s: Strategy, popular: set[str],
             start: date | None = None, end: date | None = None,
             competitions: list[str] | None = None) -> BacktestResult:
    comps = set(competitions or s.competitions)
    pool = sorted(
        (m for m in matches
         if m.finished and m.odds
         and (not comps or m.competition in comps)
         and (start is None or m.kickoff.date() >= start)
         and (end is None or m.kickoff.date() < end)),
        key=lambda m: (m.kickoff, m.id),
    )
    res = BacktestResult(matches_scanned=len(pool))
    if not pool:
        return res
    bank = peak = 100.0
    max_dd_units = 0.0
    odds_sum = 0.0
    by_market: dict[str, dict[str, float]] = {}
    for m in pool:
        as_of = datetime.combine(m.kickoff.date(), DECISION_TIME)
        est = estimate_match(index, m, s, as_of, popular)
        cand = best_candidate(m, est, s, popular)
        if cand is None:
            continue
        won = cand.market in m.winning_markets()
        profit = cand.odds - 1.0 if won else -1.0
        res.sample_size += 1
        res.wins += int(won)
        res.profit_units += profit
        odds_sum += cand.odds
        bank += profit
        peak = max(peak, bank)
        max_dd_units = max(max_dd_units, peak - bank)
        row = by_market.setdefault(cand.market, {"bets": 0, "profit": 0.0})
        row["bets"] += 1
        row["profit"] += profit
    res.from_date = pool[0].kickoff.date()
    res.to_date = pool[-1].kickoff.date()
    if res.sample_size:
        res.roi = res.profit_units / res.sample_size
        res.win_rate = res.wins / res.sample_size
        res.avg_odds = odds_sum / res.sample_size
    res.max_drawdown_units = max_dd_units
    res.max_drawdown_pct = max_dd_units / 100.0
    res.by_market = {k: {"bets": v["bets"], "roi": v["profit"] / v["bets"] if v["bets"] else 0.0}
                     for k, v in by_market.items()}
    return res
