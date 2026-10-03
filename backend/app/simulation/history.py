"""Company history: event recording and milestone detection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain.events import HistoryEvent
from app.domain.world import World

FEED_RETENTION_DAYS = 120


def record(world: World, kind: str, title: str, text: str = "", importance: int = 1, tone: str = "neutral",
           employees: Iterable[str] = (), department_id: str | None = None,
           data: dict[str, Any] | None = None) -> HistoryEvent:
    ev = HistoryEvent(id=world.next_id("ev"), time=world.clock.now, kind=kind, title=title, text=text,
                      importance=importance, tone=tone, employee_ids=list(employees),  # type: ignore[arg-type]
                      department_id=department_id, data=data or {})
    world.events.append(ev)
    return ev


def prune(world: World) -> None:
    """Keep every notable event forever; drop old feed-only noise."""
    if len(world.events) < 4000:
        return
    cutoff = world.clock.now.toordinal() - FEED_RETENTION_DAYS
    world.events = [e for e in world.events if e.importance >= 2 or e.time.toordinal() >= cutoff]


def _flag(world: World, key: str) -> bool:
    """True the first time a one-off milestone is reached."""
    if world.milestones.get(key):
        return False
    world.milestones[key] = True
    return True


def after_month_close(world: World, net: float, month_label: str, valuation: float) -> None:
    m = world.milestones
    if net > 0 and _flag(world, "first_profitable_month"):
        record(world, "milestone", f"First profitable month: {month_label}",
               f"The company made €{net:,.0f} net in {month_label}.", 3, "good")
    best = m.get("best_month_net")
    worst = m.get("worst_month_net")
    if best is None or net > best:
        m["best_month_net"] = net
        if best is not None and net > 0:
            record(world, "record", f"Best month ever: €{net:+,.0f}", month_label, 2, "good")
    if worst is None or net < worst:
        m["worst_month_net"] = net
        if worst is not None and net < 0:
            record(world, "record", f"Worst month ever: €{net:+,.0f}", month_label, 2, "bad")


def after_day(world: World, valuation: float, status_before: str, status_after: str, day_pnl: float) -> None:
    m = world.milestones
    start = world.config.starting_capital
    # valuation thresholds
    for mult, label in ((1.25, "+25%"), (1.5, "+50%"), (2.0, "doubled"), (3.0, "tripled")):
        if valuation >= start * mult and _flag(world, f"value_{mult}"):
            record(world, "record", f"Company value {label}: €{valuation:,.0f}",
                   "A new record valuation.", 3, "good")
    for frac, label in ((0.75, "-25%"), (0.5, "-50%"), (0.25, "-75%")):
        if valuation <= start * frac and _flag(world, f"value_down_{frac}"):
            record(world, "record", f"Company value {label}: €{valuation:,.0f}",
                   "Drawdown from the founding capital.", 3, "bad")
    if status_before != status_after:
        if status_after == "distress":
            first = _flag(world, "first_distress")
            record(world, "distress", "Financial distress" if first else "Back in distress",
                   "Runway is critically short. Cuts and desperation loom.", 3, "bad")
            m["in_distress_since"] = world.today.isoformat()
        elif status_before == "distress" and status_after in ("stable", "thriving", "strained"):
            record(world, "recovery", "Recovery: out of distress",
                   f"Status improved to {status_after}.", 3, "good")
        elif status_after == "thriving" and _flag(world, "first_thriving"):
            record(world, "milestone", "The company is thriving", "Profitable with no cash burn.", 3, "good")
    # company losing-days streak
    s = world.stats
    if day_pnl < 0:
        s.current_company_losing_days += 1
        if s.current_company_losing_days > s.longest_company_losing_days:
            s.longest_company_losing_days = s.current_company_losing_days
            if s.longest_company_losing_days >= 5:
                record(world, "record", f"Worst losing streak: {s.longest_company_losing_days} losing days in a row",
                       "", 2, "bad")
    elif day_pnl > 0:
        s.current_company_losing_days = 0
