from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .base import Model


class HistoryEvent(Model):
    id: str
    time: datetime
    kind: str
    title: str
    text: str = ""
    importance: int = 1  # 1 = feed only, 2 = notable, 3 = landmark (timeline highlight)
    tone: Literal["good", "bad", "neutral", "drama"] = "neutral"
    employee_ids: list[str] = Field(default_factory=list)
    department_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Memo(Model):
    time: datetime
    author_id: str
    scope: Literal["weekly", "monthly"]
    text: str


class ActionRecord(Model):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    applied: bool
    result: str = ""


class ManagementLog(Model):
    time: datetime
    scope: Literal["weekly", "monthly", "office"]
    thought: str = ""
    memo: str = ""
    actions: list[ActionRecord] = Field(default_factory=list)
    by: Literal["ai", "player", "advisor"] = "ai"  # who decided: the AI CEO, the player, or the advisor for them
    skipped: list[str] = Field(default_factory=list)  # advisor suggestions the player turned down
