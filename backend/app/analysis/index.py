"""Fast lookup structures over observable match data (rebuilt on load, never serialized)."""

from __future__ import annotations

import bisect
from collections import defaultdict
from datetime import date, datetime

from app.domain.sports import Match, TeamNews

_DEFAULT_AVG = (1.55, 1.25)


class SportsIndex:
    """Per-team chronological lists of finished matches plus cached league averages.

    Everything here only uses information that is public at the time of the query:
    finished matches with kickoff strictly before `as_of`, and news published before `as_of`.
    """

    def __init__(self, matches: dict[str, Match], news: list[TeamNews]) -> None:
        self.matches = matches
        self._team: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
        self._comp: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
        self._news: dict[str, list[TeamNews]] = defaultdict(list)
        self._avg_cache: dict[tuple[str, date, int], tuple[float, float]] = {}
        self._strength_cache: dict[tuple, tuple[float, float, float]] = {}
        self._cache_day: date | None = None
        for m in sorted(matches.values(), key=lambda m: (m.kickoff, m.id)):
            if m.finished:
                self._insert(m)
        for n in news:
            self.add_news(n)

    # ------------------------------------------------------------------ maintenance
    def _insert(self, m: Match) -> None:
        key = (m.kickoff, m.id)
        for lst in (self._team[m.home_id], self._team[m.away_id], self._comp[m.competition]):
            bisect.insort(lst, key)

    def add_finished(self, m: Match) -> None:
        self._insert(m)
        self._avg_cache.clear()
        self._strength_cache.clear()

    def add_news(self, n: TeamNews) -> None:
        self._news[n.team_id].append(n)

    def forget_match(self, match_id: str) -> None:
        """Used when old matches are pruned from the world."""
        for lst in list(self._team.values()) + list(self._comp.values()):
            for i, (_, mid) in enumerate(lst):
                if mid == match_id:
                    del lst[i]
                    break

    # ------------------------------------------------------------------ queries
    def team_history(self, team_id: str, before: datetime, limit: int) -> list[Match]:
        lst = self._team.get(team_id, [])
        hi = bisect.bisect_left(lst, (before, ""))
        lo = max(0, hi - limit)
        return [self.matches[mid] for _, mid in lst[lo:hi] if mid in self.matches]

    def league_averages(self, competition: str, before: datetime, sample: int = 300) -> tuple[float, float]:
        key = (competition, before.date(), sample)
        cached = self._avg_cache.get(key)
        if cached:
            return cached
        lst = self._comp.get(competition, [])
        hi = bisect.bisect_left(lst, (datetime.combine(before.date(), datetime.min.time()), ""))
        rows = [self.matches[mid] for _, mid in lst[max(0, hi - sample):hi] if mid in self.matches]
        if len(rows) < 30:
            avg = _DEFAULT_AVG
        else:
            home = sum(m.home_goals or 0 for m in rows) / len(rows)
            away = sum(m.away_goals or 0 for m in rows) / len(rows)
            avg = (max(home, 0.5), max(away, 0.4))
        self._avg_cache[key] = avg
        return avg

    def active_news(self, team_id: str, as_of: datetime) -> list[TeamNews]:
        return [
            n for n in self._news.get(team_id, [])
            if n.published <= as_of and n.expires > as_of.date() and n.kind != "return"
        ]

    def recent_news(self, team_id: str, as_of: datetime, days: int = 10) -> list[TeamNews]:
        start = as_of.toordinal() - days
        return [n for n in self._news.get(team_id, []) if n.published <= as_of and n.published.toordinal() >= start]

    def strength_cache(self) -> dict[tuple, tuple[float, float, float]]:
        return self._strength_cache

    def form_string(self, team_id: str, before: datetime, n: int = 5) -> str:
        out = []
        for m in self.team_history(team_id, before, n):
            gf, ga = (m.home_goals, m.away_goals) if m.home_id == team_id else (m.away_goals, m.home_goals)
            out.append("W" if gf > ga else "D" if gf == ga else "L")
        return "".join(out)

    def goal_averages(self, team_id: str, before: datetime, n: int = 10) -> tuple[float, float]:
        hist = self.team_history(team_id, before, n)
        if not hist:
            return 0.0, 0.0
        gf = ga = 0
        for m in hist:
            if m.home_id == team_id:
                gf += m.home_goals or 0
                ga += m.away_goals or 0
            else:
                gf += m.away_goals or 0
                ga += m.home_goals or 0
        return gf / len(hist), ga / len(hist)
