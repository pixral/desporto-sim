from __future__ import annotations

from datetime import date

from pydantic import Field

from .base import Model

# Bounds for every tunable strategy parameter. Used to clamp LLM/LAB output and by mutation code.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "model_weight": (0.0, 1.0),
    "window": (4, 40),
    "half_life": (2.0, 60.0),
    "shrinkage": (0.5, 12.0),
    "home_adv": (0.85, 1.2),
    "news_weight": (0.0, 1.6),
    "xg_weight": (0.0, 1.0),
    "underdog_bias": (-0.04, 0.06),
    "min_odds": (1.15, 4.0),
    "max_odds": (1.6, 15.0),
    "min_edge": (0.0, 0.15),
    "kelly_fraction": (0.05, 0.6),
}


class BacktestResult(Model):
    sample_size: int = 0
    wins: int = 0
    profit_units: float = 0.0
    roi: float = 0.0
    win_rate: float = 0.0
    avg_odds: float = 0.0
    max_drawdown_units: float = 0.0
    max_drawdown_pct: float = 0.0  # relative to a 100-unit bank
    matches_scanned: int = 0
    from_date: date | None = None
    to_date: date | None = None
    by_market: dict[str, dict[str, float]] = {}


class Strategy(Model):
    """A fully specified, backtestable way of turning observable data into bet candidates.

    The judgement layer (LLM/mock policy) decides whether to follow a candidate; the strategy
    only produces probabilities, edges and candidates deterministically.
    """

    id: str
    name: str
    origin: str  # "default", "lab", "hire"
    author_id: str | None = None
    created: date
    description: str = ""
    competitions: list[str] = Field(default_factory=list)  # empty = department's competitions
    markets: list[str] = Field(default_factory=lambda: ["home_win", "draw", "away_win"])
    model_weight: float = 0.6  # 0 = pure market consensus, 1 = pure Poisson model
    window: int = 15
    half_life: float = 8.0
    shrinkage: float = 4.0
    home_adv: float = 1.0
    news_weight: float = 0.8
    xg_weight: float = 0.0  # 0 = rate teams on goals, 1 = rate teams on expected goals
    opponent_adjust: bool = False
    underdog_bias: float = 0.0
    fade_popular: bool = False
    min_odds: float = 1.4
    max_odds: float = 6.0
    min_edge: float = 0.03
    kelly_fraction: float = 0.25
    # live tracking across every employee using this strategy
    live_bets: int = 0
    live_staked: float = 0.0
    live_profit: float = 0.0
    backtest: BacktestResult | None = None
    retired: bool = False

    @property
    def live_roi(self) -> float:
        return self.live_profit / self.live_staked if self.live_staked > 0 else 0.0

    def summary(self) -> str:
        if self.description:
            return self.description
        parts = []
        if self.model_weight <= 0.05:
            parts.append("pure market-consensus price shopping")
        elif self.model_weight >= 0.95:
            parts.append(f"Poisson goal model ({self.window}-match window)")
        else:
            parts.append(
                f"{int(self.model_weight * 100)}% Poisson model / {int((1 - self.model_weight) * 100)}% market"
            )
        if self.xg_weight >= 0.6:
            parts.append("rates teams on expected goals")
        if self.half_life < 6:
            parts.append("heavy recent-form weighting")
        if self.news_weight >= 0.8:
            parts.append("reacts to team news")
        if self.fade_popular:
            parts.append("fades popular clubs")
        if self.underdog_bias > 0.015:
            parts.append("leans towards underdogs")
        parts.append(f"odds {self.min_odds:.2f}-{self.max_odds:.2f}, min edge {self.min_edge:.0%}")
        return "; ".join(parts)
