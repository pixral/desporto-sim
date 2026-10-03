from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import Model

TRAIT_NAMES: tuple[str, ...] = (
    "cautious",
    "analytical",
    "aggressive",
    "ambitious",
    "stubborn",
    "collaborative",
    "independent",
    "risk_seeking",
    "skeptical",
)


class Traits(Model):
    """Stable personality, each in [0, 1]. Influences behaviour, never dictates it."""

    cautious: float = 0.5
    analytical: float = 0.5
    aggressive: float = 0.5
    ambitious: float = 0.5
    stubborn: float = 0.5
    collaborative: float = 0.5
    independent: float = 0.5
    risk_seeking: float = 0.5
    skeptical: float = 0.5

    def as_dict(self) -> dict[str, float]:
        return {name: round(getattr(self, name), 2) for name in TRAIT_NAMES}

    def top(self, n: int = 2) -> list[str]:
        return [k for k, _ in sorted(self.as_dict().items(), key=lambda kv: -kv[1])[:n]]

    def describe(self) -> str:
        words = []
        for name, value in sorted(self.as_dict().items(), key=lambda kv: -kv[1]):
            if value >= 0.72:
                words.append(f"very {name.replace('_', '-')}")
            elif value >= 0.58:
                words.append(name.replace("_", "-"))
        low = [n.replace("_", "-") for n, v in self.as_dict().items() if v <= 0.2]
        text = ", ".join(words[:4]) if words else "even-tempered"
        if low:
            text += f"; not at all {', '.join(low[:2])}"
        return text


class Appearance(Model):
    """Indices into the frontend's procedural sprite palettes."""

    skin: int = 0
    hair_style: int = 0
    hair_color: int = 0
    shirt: int = 0
    pants: int = 0
    accessory: int = 0  # 0 none, 1 glasses, 2 headphones, 3 tie, 4 cap


class Psyche(Model):
    stress: float = 0.25  # 0..1
    confidence: float = 0.5  # 0..1
    risk_tolerance: float = 0.4  # 0..1
    reputation: float = 50.0  # 0..100


class Relationship(Model):
    trust: float = 50.0  # 0..100
    respect: float = 50.0  # 0..100
    rivalry: float = 0.0  # 0..100


class CareerEntry(Model):
    day: date
    kind: str
    text: str


class DecisionLog(Model):
    time: datetime
    match_id: str
    match_label: str
    decision: Literal["BET", "NO_BET"]
    market: str | None = None
    selection: str | None = None
    odds: float | None = None
    stake: float | None = None
    confidence: float = 0.0
    reason: str = ""
    bet_id: str | None = None
    model_edge: float | None = None
    influenced_by: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # engine corrections (stake clamped, ...)


class Employee(Model):
    id: str
    name: str
    role: Literal["tipster", "researcher", "ceo"]
    title: str
    level: int = 1  # tipsters: 0 junior, 1 tipster, 2 senior, 3 head of desk
    specialty: str
    department_id: str | None = None
    desk_index: int = 0
    traits: Traits = Field(default_factory=Traits)
    psyche: Psyche = Field(default_factory=Psyche)
    appearance: Appearance = Field(default_factory=Appearance)
    salary: float = 100.0  # monthly
    hired: date
    left: date | None = None
    leave_reason: str | None = None
    active: bool = True
    strategy_id: str | None = None
    bankroll_weight: float = 1.0
    relationships: dict[str, Relationship] = Field(default_factory=dict)

    # performance
    bets_total: int = 0
    wins: int = 0
    losses: int = 0
    staked: float = 0.0
    returned: float = 0.0
    streak: int = 0  # >0 consecutive wins, <0 consecutive losses
    best_streak: int = 0
    worst_streak: int = 0
    bet_ids: list[str] = Field(default_factory=list)
    month_profit: float = 0.0
    day_profit: float = 0.0
    bonuses_earned: float = 0.0
    decisions: list[DecisionLog] = Field(default_factory=list)  # ring buffer
    no_bet_flags: list[int] = Field(default_factory=list)  # last 40 decisions: 1 = NO_BET
    career: list[CareerEntry] = Field(default_factory=list)
    series: list[list[float]] = Field(default_factory=list)  # [day_index, cum_profit, rep, stress, conf]

    # management
    under_review: bool = False
    warnings: int = 0
    promotions: int = 0

    # live presentation state
    status: str = "idle"
    task: str = ""
    thought: str = ""
    mood: str = "calm"
    pnl_flash_seq: int = 0  # bumps whenever day_profit is (re)published for floating indicators

    # CEO only
    ceo_style: str | None = None

    @property
    def profit(self) -> float:
        return self.returned - self.staked

    @property
    def roi(self) -> float:
        return self.profit / self.staked if self.staked > 0 else 0.0

    def tenure_days(self, today: date) -> int:
        end = self.left or today
        return max(0, (end - self.hired).days)

    def no_bet_rate(self) -> float:
        return sum(self.no_bet_flags) / len(self.no_bet_flags) if self.no_bet_flags else 0.0

    def add_career(self, day: date, kind: str, text: str) -> None:
        self.career.append(CareerEntry(day=day, kind=kind, text=text))


class Candidate(Model):
    """A job applicant in the hiring pool. Their true quality is unknown to everyone."""

    id: str
    name: str
    role: Literal["tipster", "researcher"]
    specialty: str
    traits: Traits
    appearance: Appearance
    cv_rating: int  # 1..100, noisy and only weakly informative
    experience_years: int
    salary_ask: float
    strategy_id: str | None = None
    pitch: str = ""
    lab_backtest_roi: float | None = None
    lab_backtest_n: int | None = None
    expires: date
