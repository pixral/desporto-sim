from __future__ import annotations

import random
from collections import Counter
from datetime import date, datetime, timedelta

from app.domain.sports import MATCH_DURATION_MINUTES
from app.sports.mock_provider import MockSportsDataProvider
from app.sports.pricing import fair_probs, price, round_odds
from app.sports.schedule import double_round_robin, league_anchor_dates, ucl_league_phase


def test_double_round_robin_is_complete_and_balanced():
    teams = [f"T{i}" for i in range(18)]
    rounds = double_round_robin(teams, random.Random(1))
    assert len(rounds) == 34
    pairs = Counter((h, a) for rnd in rounds for h, a in rnd)
    for a in teams:
        for b in teams:
            if a != b:
                assert pairs[(a, b)] == 1  # each ordered pairing exactly once: home and away
    for rnd in rounds:
        playing = [t for pair in rnd for t in pair]
        assert len(playing) == len(set(playing)) == 18


def test_league_dates_cover_all_rounds_in_order():
    dates = league_anchor_dates("PL", 2026, 38, set())
    assert len(dates) == 38
    assert dates == sorted(dates)
    assert len(set(dates)) == 38


def test_ucl_league_phase_no_repeat_opponents():
    teams = [f"C{i}" for i in range(36)]
    rounds = ucl_league_phase(teams, random.Random(4))
    assert len(rounds) == 8
    seen = set()
    for rnd in rounds:
        assert len(rnd) == 18
        for h, a in rnd:
            key = frozenset((h, a))
            assert key not in seen
            seen.add(key)


def test_pricing_has_margin_and_ladder():
    odds = price([0.5, 0.27, 0.23], 0.05)
    assert sum(1 / o for o in odds) > 1.0
    assert round_odds(2.137) == 2.12  # 0.02 steps between 2 and 3, rounded down
    assert abs(sum(fair_probs(odds)) - 1) < 1e-9


def test_bootstrap_season_is_realistic(bootstrapped):
    _, history = bootstrapped
    domestic = [m for m in history if m.competition != "UCL"]
    assert len(domestic) == 306 + 3 * 380
    home = sum(m.home_goals > m.away_goals for m in domestic) / len(domestic)
    draws = sum(m.home_goals == m.away_goals for m in domestic) / len(domestic)
    goals = sum(m.total_goals for m in domestic) / len(domestic)
    assert 0.38 < home < 0.52
    assert 0.18 < draws < 0.32
    assert 2.3 < goals < 3.3
    stages = {m.stage for m in history if m.competition == "UCL"}
    assert "Final" in stages and any(s.startswith("Round of 16") for s in stages)
    assert all(m.odds and m.odds_close and m.home_xg is not None for m in history)


def test_no_results_before_final_whistle():
    p = MockSportsDataProvider(seed=11)
    p.bootstrap_history(date(2026, 8, 10))
    fixtures = p.fixtures(date(2026, 8, 10), date(2026, 8, 20), datetime(2026, 8, 10, 8, 0))
    m = fixtures[0]
    assert m.home_goals is None and not m.odds
    before = p.results([m.id], m.kickoff + timedelta(minutes=MATCH_DURATION_MINUTES - 1))
    assert m.id not in before
    snap_early = p.odds([m.id], m.kickoff - timedelta(hours=1))[m.id]
    assert snap_early.close == {}
    after = p.results([m.id], m.kickoff + timedelta(minutes=MATCH_DURATION_MINUTES))
    assert m.id in after
    assert p.odds([m.id], m.kickoff)[m.id].close


def test_same_seed_same_football():
    a = MockSportsDataProvider(seed=21).bootstrap_history(date(2026, 8, 10))
    b = MockSportsDataProvider(seed=21).bootstrap_history(date(2026, 8, 10))
    assert [(m.id, m.home_goals, m.away_goals, m.odds["Atlas"].home_win) for m in a[:200]] == \
           [(m.id, m.home_goals, m.away_goals, m.odds["Atlas"].home_win) for m in b[:200]]


def test_provider_state_roundtrip():
    p = MockSportsDataProvider(seed=8)
    p.bootstrap_history(date(2026, 8, 10))
    state = p.export_state()
    q = MockSportsDataProvider(seed=999)
    q.import_state(state)
    end = datetime(2026, 9, 1, 23, 30)
    ids = [m.id for m in p.fixtures(date(2026, 8, 10), date(2026, 9, 1), datetime(2026, 8, 10, 8))]
    assert p.results(ids, end) == q.results(ids, end)
