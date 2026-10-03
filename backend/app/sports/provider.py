"""The sports data abstraction. The simulation only ever talks to this interface.

A real provider (football-data.org, API-Football, an odds API...) should implement the same
methods. The contract that matters for simulation integrity: **never return information that
would not have been available at `as_of`** (no results before the final whistle, no closing
odds before kick-off). The engine relies on that to make paper betting honest.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from app.domain.base import Model
from app.domain.sports import CompetitionInfo, Match, OddsLine, Team, TeamNews


class OddsSnapshot(Model):
    open: dict[str, OddsLine] = {}
    current: dict[str, OddsLine] = {}  # matchday price
    close: dict[str, OddsLine] = {}  # only once kicked off


class MatchResult(Model):
    home_goals: int
    away_goals: int
    home_xg: float | None = None
    away_xg: float | None = None
    note: str = ""


@runtime_checkable
class ISportsDataProvider(Protocol):
    name: str

    def competitions(self) -> list[CompetitionInfo]: ...

    def teams(self) -> list[Team]: ...

    def bootstrap_history(self, start: date) -> list[Match]:
        """Finished matches (with odds) before `start`, used to warm up models and the LAB."""
        ...

    def fixtures(self, start: date, end: date, as_of: datetime) -> list[Match]:
        """Scheduled matches kicking off in [start, end] that are known at `as_of`."""
        ...

    def odds(self, match_ids: list[str], as_of: datetime) -> dict[str, OddsSnapshot]: ...

    def results(self, match_ids: list[str], as_of: datetime) -> dict[str, MatchResult]: ...

    def news(self, since: datetime, as_of: datetime) -> list[TeamNews]: ...

    def export_state(self) -> dict[str, Any]: ...

    def import_state(self, state: dict[str, Any]) -> None: ...
