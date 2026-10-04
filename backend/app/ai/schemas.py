"""Structured outputs the judgement layer must return. Validated with pydantic on every call."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MarketKey = Literal["home_win", "draw", "away_win", "over_2_5", "under_2_5"]
CompetitionKey = Literal["BL1", "PL", "LL", "SA", "UCL"]


class TipsterMatchDecision(BaseModel):
    match_id: str
    decision: Literal["BET", "NO_BET"]
    market: MarketKey | None = None
    selection: str | None = None
    odds: float | None = None
    stake: float | None = None
    confidence: float = Field(description="0 to 1")
    reason: str
    influenced_by: list[str] = Field(default_factory=list, description="names of colleagues whose view swayed you")


class TipsterDayOutput(BaseModel):
    thought: str = Field(description="one short inner-monologue sentence about how you feel today")
    decisions: list[TipsterMatchDecision]


CEOActionType = Literal[
    "FIRE", "HIRE", "PROMOTE", "WARN", "CLEAR_REVIEW", "TRANSFER_EMPLOYEE",
    "SET_STAKE_LIMIT", "FUND_DEPARTMENT", "WITHDRAW_BANKROLL",
    "CREATE_DEPARTMENT", "CLOSE_DEPARTMENT",
    "SET_LAB_BUDGET", "SET_MARKETING_BUDGET",
    "DEPLOY_STRATEGY", "ADJUST_STRATEGY",
    "FREEZE_HIRING", "UNFREEZE_HIRING", "CUT_SALARIES",
    "TAKE_LOAN", "REPAY_LOAN",
    "LEASE_SPACE", "RELEASE_SPACE",
]


class CEOAction(BaseModel):
    type: CEOActionType
    employee_id: str | None = None
    department_id: str | None = None
    candidate_id: str | None = None
    experiment_id: str | None = None
    department_kind: str | None = None
    amount: float | None = None
    pct: float | None = None
    field: str | None = None
    value: float | None = None
    facility: Literal["canteen", "desk_wing", "studio"] | None = None
    reason: str = ""


class CEOReviewOutput(BaseModel):
    thought: str = Field(description="your private read of the situation, one or two sentences")
    memo: str = Field(description="a short memo to all staff; empty string if you have nothing to say")
    actions: list[CEOAction]


class LabStrategyParams(BaseModel):
    competitions: list[CompetitionKey] = Field(default_factory=list)
    markets: list[MarketKey] = Field(default_factory=list)
    model_weight: float | None = None
    window: int | None = None
    half_life: float | None = None
    shrinkage: float | None = None
    home_adv: float | None = None
    news_weight: float | None = None
    xg_weight: float | None = None
    opponent_adjust: bool | None = None
    underdog_bias: float | None = None
    fade_popular: bool | None = None
    min_odds: float | None = None
    max_odds: float | None = None
    min_edge: float | None = None
    kelly_fraction: float | None = None


class LabHypothesisOutput(BaseModel):
    name: str = Field(description="short catchy strategy name")
    hypothesis: str = Field(description="one sentence testable claim")
    rationale: str
    params: LabStrategyParams
