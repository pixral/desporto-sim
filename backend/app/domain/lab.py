from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field

from .base import Model
from .strategy import BacktestResult


class Experiment(Model):
    id: str
    researcher_id: str
    name: str
    hypothesis: str
    rationale: str = ""
    strategy_id: str
    started: date
    due: date
    completed: date | None = None
    status: Literal["running", "completed", "deployed", "rejected"] = "running"
    result: BacktestResult | None = None  # in-sample period
    holdout: BacktestResult | None = None  # most recent months, kept out of the main test
    recommendation: Literal["", "DEPLOY", "PROMISING", "REJECT"] = ""
    recommendation_text: str = ""
    deployed_to: list[str] = Field(default_factory=list)


class AuditFinding(Model):
    id: str
    day: date
    employee_id: str
    segment: str  # e.g. "odds 4.0+", "market draw", "competition UCL"
    bets: int
    roi: float
    profit: float
    text: str
    suggestion: dict[str, Any] = Field(default_factory=dict)  # e.g. {"field": "max_odds", "value": 4.0}
    resolved: bool = False
