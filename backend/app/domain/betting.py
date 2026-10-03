from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .base import Model


class Bet(Model):
    """A paper bet. Stake is moved from the department bankroll into exposure when placed."""

    id: str
    placed: datetime
    employee_id: str
    department_id: str
    match_id: str
    match_label: str
    competition: str
    market: str
    selection: str
    book: str
    odds: float
    stake: float
    confidence: float
    model_prob: float | None = None
    model_edge: float | None = None
    strategy_id: str | None = None
    reason: str = ""
    influenced_by: list[str] = Field(default_factory=list)
    status: Literal["open", "won", "lost", "void"] = "open"
    settled: datetime | None = None
    payout: float = 0.0
    closing_odds: float | None = None
    score: str | None = None

    @property
    def profit(self) -> float:
        if self.status == "open":
            return 0.0
        return self.payout - self.stake

    @property
    def clv(self) -> float | None:
        """Closing line value: how much better our price was than the closing price."""
        if not self.closing_odds:
            return None
        return self.odds / self.closing_odds - 1.0
