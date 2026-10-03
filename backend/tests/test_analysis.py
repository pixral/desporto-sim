from __future__ import annotations

from datetime import date, datetime, time

from app.analysis.backtest import backtest
from app.analysis.index import SportsIndex
from app.analysis.models import candidates, estimate_match, market_consensus
from app.analysis.poisson import outcome_probs
from app.domain.strategy import Strategy


def _strategy(**kw) -> Strategy:
    kw.setdefault("markets", ["home_win", "draw", "away_win", "over_2_5", "under_2_5"])
    return Strategy(id="s", name="t", origin="test", created=date(2026, 8, 1), **kw)


def test_poisson_probabilities():
    h, d, a, over = outcome_probs(1.4, 1.4)
    assert abs(h + d + a - 1) < 1e-9
    assert abs(h - a) < 1e-9
    h2, _, a2, over2 = outcome_probs(2.5, 0.6)
    assert h2 > 0.65 and a2 < 0.12
    assert over2 > over or abs(over2 - over) < 0.2


def test_market_consensus_normalized(bootstrapped):
    _, history = bootstrapped
    cons = market_consensus(history[0].odds)
    assert abs(cons["home_win"] + cons["draw"] + cons["away_win"] - 1) < 1e-9
    assert abs(cons["over_2_5"] + cons["under_2_5"] - 1) < 1e-9


def test_estimates_never_use_future_results(bootstrapped):
    _, history = bootstrapped
    matches = {m.id: m.model_copy(deep=True) for m in history}
    target = sorted(matches.values(), key=lambda m: m.kickoff)[900]
    as_of = datetime.combine(target.kickoff.date(), time(11, 0))
    s = _strategy(model_weight=1.0, xg_weight=0.5)
    before = estimate_match(SportsIndex(matches, []), target, s, as_of)
    # Tamper with everything after the decision time: the estimate must not move.
    for m in matches.values():
        if m.kickoff >= as_of:
            m.home_goals, m.away_goals, m.home_xg, m.away_xg = 9, 0, 5.0, 0.1
    after = estimate_match(SportsIndex(matches, []), target, s, as_of)
    assert before.probs == after.probs


def test_candidates_respect_strategy_filters(bootstrapped):
    _, history = bootstrapped
    matches = {m.id: m for m in history}
    m = sorted(history, key=lambda m: m.kickoff)[800]
    s = _strategy(min_odds=2.0, max_odds=3.0, min_edge=-1.0, markets=["home_win", "away_win"])
    est = estimate_match(SportsIndex(matches, []), m, s, datetime.combine(m.kickoff.date(), time(11)))
    for c in candidates(m, est, s):
        if c.meets_strategy:
            assert 2.0 <= c.odds <= 3.0 and c.market in ("home_win", "away_win")


def test_backtest_is_walk_forward(bootstrapped):
    _, history = bootstrapped
    matches = {m.id: m.model_copy(deep=True) for m in history}
    s = _strategy(model_weight=0.7, xg_weight=0.8, half_life=4, competitions=["PL"], min_edge=0.03)
    cutoff = date(2026, 3, 1)
    res = backtest(SportsIndex(matches, []), matches.values(), s, set(), start=date(2025, 10, 1), end=cutoff)
    assert res.sample_size > 30
    assert res.to_date < cutoff
    for m in matches.values():
        if m.kickoff.date() >= cutoff:
            m.home_goals, m.away_goals = 0, 7
    res2 = backtest(SportsIndex(matches, []), matches.values(), s, set(), start=date(2025, 10, 1), end=cutoff)
    assert res2.profit_units == res.profit_units
