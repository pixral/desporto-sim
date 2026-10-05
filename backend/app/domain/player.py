"""Player mode: the human sits in the CEO's chair. The AI CEO policy becomes the advisor."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .base import Model

PAUSE_MODES: tuple[str, ...] = ("monthly", "every_review", "events_only")


class Proposal(Model):
    """One action the advisor suggests, with its reasoning and a readable label."""

    action: dict[str, Any]  # a CEOAction dump
    label: str
    reason: str = ""
    area: str = "people"  # people | hiring | desks | money | lab | office


class PendingReview(Model):
    id: str
    scope: Literal["weekly", "monthly"]
    created: datetime
    thought: str = ""  # the advisor's private read
    memo: str = ""  # the advisor's draft memo
    proposals: list[Proposal] = Field(default_factory=list)
    status: Literal["open", "resolved", "auto"] = "open"


class PlayerState(Model):
    review: PendingReview | None = None
    advisor_thought: str = ""
    lab_brief: dict[str, Any] | None = None  # what the CEO asked the LAB to research (kind, value, label, since)
    queue: list[Proposal] = Field(default_factory=list)  # review-only decisions for the next monthly review
    week: str = ""  # ISO week the office-hours counters belong to
    used: dict[str, int] = Field(default_factory=dict)  # office-hours actions used this week, by type
    reviews_signed: int = 0
    reviews_auto: int = 0
    advice_taken: int = 0
    advice_skipped: int = 0
    board_warned: datetime | None = None
