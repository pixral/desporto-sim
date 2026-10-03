from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from .base import Model

# Selection keys used everywhere (decisions, bets, odds lines).
MARKETS: tuple[str, ...] = ("home_win", "draw", "away_win", "over_2_5", "under_2_5")
MARKET_GROUPS: dict[str, tuple[str, ...]] = {
    "1X2": ("home_win", "draw", "away_win"),
    "OU25": ("over_2_5", "under_2_5"),
}
GROUP_OF: dict[str, str] = {m: g for g, ms in MARKET_GROUPS.items() for m in ms}

MATCH_DURATION_MINUTES = 115  # kick-off to final whistle incl. half-time and stoppage


class CompetitionInfo(Model):
    code: str
    name: str
    country: str
    kind: Literal["league", "cup"]
    color: str


class Team(Model):
    id: str
    name: str
    short: str
    competition: str  # domestic league code, or "OTHER" for teams only seen in Europe
    country: str
    popular: bool = False


class OddsLine(Model):
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    under_2_5: float

    def get(self, market: str) -> float:
        return float(getattr(self, market))


class Match(Model):
    id: str
    competition: str
    season: str
    stage: str
    home_id: str
    away_id: str
    kickoff: datetime
    neutral: bool = False
    status: Literal["scheduled", "live", "finished"] = "scheduled"
    odds_open: dict[str, OddsLine] = {}
    odds: dict[str, OddsLine] = {}  # matchday price (what tipsters bet at)
    odds_close: dict[str, OddsLine] = {}
    home_goals: int | None = None
    away_goals: int | None = None
    home_xg: float | None = None  # expected goals, published with the result
    away_xg: float | None = None
    note: str = ""

    @property
    def finished(self) -> bool:
        return self.status == "finished" and self.home_goals is not None

    @property
    def total_goals(self) -> int:
        return (self.home_goals or 0) + (self.away_goals or 0)

    def winning_markets(self) -> set[str]:
        if not self.finished:
            return set()
        hg, ag = self.home_goals or 0, self.away_goals or 0
        won = {"home_win" if hg > ag else "away_win" if ag > hg else "draw"}
        won.add("over_2_5" if hg + ag > 2 else "under_2_5")
        return won

    def best_price(self, market: str, source: str = "odds") -> tuple[str, float] | None:
        book_lines: dict[str, OddsLine] = getattr(self, source)
        best: tuple[str, float] | None = None
        for book, line in book_lines.items():
            price = line.get(market)
            if best is None or price > best[1]:
                best = (book, price)
        return best


class TeamNews(Model):
    id: str
    team_id: str
    published: datetime
    expires: date
    # injury_* also covers suspensions; "return" is informational (the absence ends at `expires`).
    kind: Literal["injury_attack", "injury_defense", "return", "manager_change"]
    severity: int  # 1..3
    headline: str
