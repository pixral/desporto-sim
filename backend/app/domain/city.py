"""The city around the company: a small stock market, the morning paper, and office space.

Everything here is simulated. Listed companies are fictional; their prices follow a random walk
with sector moves and news-driven jumps. Some stories change the company's world (an advertising
ban on betting, a data-feed price hike, interest rates, the betting sector's mood).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field

from .base import Model

Section = Literal["front", "business", "city", "sports", "company"]
Tone = Literal["good", "bad", "neutral"]


class Stock(Model):
    ticker: str
    name: str
    sector: str
    price: float
    base: float  # listing price, for the sector indices
    vol: float  # annualised volatility
    drift: float  # annualised drift
    anchor: float = 0.0  # slowly growing fair value the price is pulled back towards
    history: list[float] = Field(default_factory=list)  # closes aligned with CityState.days
    next_earnings: date | None = None


class PressItem(Model):
    id: str
    day: date  # the edition it appears in
    section: Section
    headline: str
    body: str = ""
    tickers: list[str] = Field(default_factory=list)
    move: float | None = None  # the price move the story caused (fraction)
    importance: int = 1  # 1 brief, 2 story, 3 front-page material
    tone: Tone = "neutral"
    effect: str = ""  # plain-language consequence for the company, if any
    lead: bool = False  # the front-page story of its edition
    kind: str = ""  # e.g. "wrap" for the daily market report


class Story(Model):
    """A news arc that comes back later (a won tender may end in an accident, a delay or a ribbon cutting)."""

    id: str
    kind: str
    ticker: str
    subject: str
    opened: date
    due: date


class Modifier(Model):
    """A temporary change to the company's world caused by the news."""

    kind: str  # ad_ban | data_prices | sub_boost
    value: float
    since: date
    until: date
    label: str


class CityState(Model):
    name: str = "Portavia"
    paper: str = "The Portavia Ledger"
    stocks: dict[str, Stock] = Field(default_factory=dict)
    days: list[date] = Field(default_factory=list)  # market days
    index: list[float] = Field(default_factory=list)  # city index (PVX 12) aligned with days
    economy: float = 0.0  # consumer confidence, -1 .. 1
    base_rate: float = 3.0  # central bank rate, % per year
    next_rate_meeting: date | None = None
    press: list[PressItem] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
    modifiers: list[Modifier] = Field(default_factory=list)
    recent_templates: dict[str, int] = Field(default_factory=dict)  # template -> ordinal of last use
    editions: list[date] = Field(default_factory=list)
    rng_state: list[Any] = Field(default_factory=list)


class OfficeState(Model):
    leased: dict[str, date] = Field(default_factory=dict)  # facility key -> lease start
