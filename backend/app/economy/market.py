"""How the city's economy reaches the company. Pure functions of World (no randomness)."""

from __future__ import annotations

from datetime import timedelta

from app.domain.base import clamp
from app.domain.world import World

from . import config as C

BETTING_SECTOR = "betting"


def modifier(world: World, kind: str) -> float:
    """Product of the active news modifiers of one kind (1.0 when none)."""
    out = 1.0
    for m in world.city.modifiers:
        if m.kind == kind and m.since <= world.today <= m.until:
            out *= m.value
    return out


def sector_index(world: World, sector: str, at: int | None = None) -> float | None:
    """Average price / listing price of a sector, at history position `at` (default: latest)."""
    vals = []
    for s in world.city.stocks.values():
        if s.sector != sector or not s.history:
            continue
        i = len(s.history) - 1 if at is None else max(0, min(at, len(s.history) - 1))
        vals.append(s.history[i] / s.base)
    return sum(vals) / len(vals) if vals else None


def betting_sentiment(world: World) -> float:
    """Listed bookmakers' shares vs. their 120-day average: how much investors like betting businesses.
    Scales the subscriber goodwill in the company valuation (0.75 .. 1.25)."""
    city = world.city
    n = len(city.days)
    if n < 20:
        return 1.0
    now = sector_index(world, BETTING_SECTOR)
    window = range(max(0, n - 120), n)
    hist = [sector_index(world, BETTING_SECTOR, i) for i in window]
    hist = [h for h in hist if h]
    if not now or not hist:
        return 1.0
    avg = sum(hist) / len(hist)
    return clamp(1.0 + 1.2 * (now / avg - 1.0), 0.75, 1.25)


def economy(world: World) -> float:
    return world.city.economy


def loan_rate_monthly(world: World) -> float:
    """The credit line costs 2 %/month when the central bank rate is 3 %, and follows the rate."""
    return max(0.005, C.LOAN_INTEREST_MONTHLY + (world.city.base_rate - 3.0) / 1200.0)


def leased(world: World, key: str) -> bool:
    return key in world.office.leased


def facility_monthly_cost(world: World, key: str, heads: int | None = None) -> float:
    f = C.FACILITIES[key]
    mult = C.preset(world.config.difficulty)["cost_mult"]
    if heads is None:
        heads = len(world.active_employees())
    return mult * (float(f["rent"]) + float(f["per_head"]) * heads)  # type: ignore[arg-type]


def facilities_monthly_cost(world: World) -> float:
    heads = len(world.active_employees())
    return sum(facility_monthly_cost(world, k, heads) for k in world.office.leased if k in C.FACILITIES)


def desk_rooms(world: World) -> int:
    from app.agents.catalog import MAX_DESK_ROOMS

    return MAX_DESK_ROOMS + (1 if leased(world, "desk_wing") else 0)


def active_modifiers(world: World) -> list[dict]:
    return [{"kind": m.kind, "value": m.value, "until": m.until.isoformat(), "label": m.label,
             "days_left": (m.until - world.today).days}
            for m in world.city.modifiers if m.since <= world.today <= m.until]


def recent_press(world: World, days: int = 3, min_importance: int = 2) -> list:
    since = world.today - timedelta(days=days)
    return [p for p in world.city.press if p.day >= since and p.importance >= min_importance]
