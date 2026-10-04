"""Sandbox tools: the player's hand of god.

Every intervention changes the real simulation state (cash, prices, people, office), goes through
the same books as everything else, is written into the company history, and is counted in the run
summary, so a sandboxed run is never mistaken for a clean one.
"""

from __future__ import annotations

import random
from typing import Any

from app.agents import management
from app.agents.hiring import generate_candidates
from app.domain.base import clamp
from app.domain.world import CEO_STYLES, World
from app.economy import accounting
from app.economy import config as EC
from app.economy import valuation as val

from . import city, drama, history

INVESTORS = ("Harbour Lane Ventures", "Grupo Ferraz", "Northwind Capital", "Lumen Family Office",
             "Atlantic Seed Fund", "Old Docks Partners")
WINDFALLS = {
    "sponsor": "A sponsorship bonus from a sportswear brand",
    "rebate": "A surprise tax rebate",
    "prize": "First prize in a sports-analytics competition",
}
# title, story, share of company value lost at "major" severity
DISASTERS: dict[str, tuple[str, str, float]] = {
    "fire": ("Fire in the server room", "Smoke, sprinklers and a week of chaos. Running LAB experiments were lost.", 0.10),
    "flood": ("Burst pipe floods the office", "Ruined desks, soaked paperwork, frayed nerves.", 0.06),
    "lawsuit": ("Lawsuit settled out of court", "A group of subscribers claimed the tips were misleading.", 0.12),
    "hack": ("Data breach: subscriber list leaked", "Subscribers cancel in droves.", 0.04),
    "tax": ("Tax audit finds unpaid taxes", "The bill arrives with interest and penalties.", 0.08),
}
SEVERITY = {"minor": 0.5, "major": 1.0, "catastrophic": 2.0}
SECTORS = ("betting", "media", "construction", "sportswear", "tech", "banking", "energy", "airlines", "food")


class GodError(ValueError):
    pass


def apply(world: World, rng: random.Random, action: str, params: dict[str, Any]) -> str:
    if world.ended:
        raise GodError("the company is gone; found a new one")
    handler = _HANDLERS.get(action)
    if handler is None:
        raise GodError(f"unknown sandbox action '{action}'")
    message = handler(world, rng, params)
    world.stats.god_actions += 1
    for note in accounting.ensure_liquidity(world):
        history.record(world, "liquidity", note, "", 2, "bad")
    return message


def _amount(params: dict[str, Any], default: float, lo: float = 1.0, hi: float = 10_000_000.0) -> float:
    try:
        value = float(params.get("amount", default))
    except (TypeError, ValueError) as exc:
        raise GodError("amount must be a number") from exc
    return clamp(value, lo, hi)


def _log(world: World, title: str, text: str, tone: str, importance: int = 2, **data: Any) -> None:
    history.record(world, "god", title, text, importance, tone, data={"god": True, **data})


# ---------------------------------------------------------------------------------- money
def _invest(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    amount = _amount(p, round(max(2000.0, 0.25 * val.valuation(world)), -2))
    who = str(p.get("investor") or rng.choice(INVESTORS))[:60]
    world.finances.cash += amount
    world.finances.invested += amount
    _log(world, f"{who} invests €{amount:,.0f}", "Fresh outside money lands in the company account.", "good", 3)
    city.publish_now(world, "company", f"{who} backs {world.config.company_name} with €{amount:,.0f}",
                     "The investors say they believe in AI-run tipping.", importance=2, tone="good")
    return f"€{amount:,.0f} from {who} added to cash"


def _windfall(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    amount = _amount(p, 2000.0)
    kind = str(p.get("kind") or "sponsor")
    label = WINDFALLS.get(kind, WINDFALLS["sponsor"])
    f = world.finances
    f.cash += amount
    f.month.other_income += amount
    f.totals.other_income += amount
    _log(world, f"Windfall: €{amount:,.0f}", f"{label}.", "good")
    return f"{label}: +€{amount:,.0f}"


def _disaster(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    kind = str(p.get("kind") or "fire")
    if kind not in DISASTERS:
        raise GodError(f"unknown disaster '{kind}'")
    sev_key = str(p.get("severity") or "major")
    sev = SEVERITY.get(sev_key, 1.0)
    title, story, share = DISASTERS[kind]
    base = max(val.valuation(world), 0.4 * world.config.starting_capital)
    cost = round(share * sev * base, 0)
    extra = ""
    f = world.finances
    if kind == "hack":
        lost = round(f.subscribers * min(0.6, 0.25 * sev))
        f.subscribers = max(0, f.subscribers - lost)
        extra = f" {lost} subscribers cancelled."
    if kind == "fire":
        burned = [x for x in world.experiments.values() if x.status == "running"]
        for x in burned:
            x.status = "rejected"
            x.recommendation_text = "Lost in the server-room fire."
        extra = f" {len(burned)} experiment(s) lost." if burned else ""
    stress = {"fire": 0.12, "flood": 0.15, "lawsuit": 0.06, "hack": 0.08, "tax": 0.05}[kind] * sev
    for e in world.active_employees():
        e.psyche.stress = clamp(e.psyche.stress + stress, 0.02, 0.98)
    f.cash -= cost
    f.month.other_costs += cost
    f.totals.other_costs += cost
    _log(world, title, f"{story} Cost €{cost:,.0f}.{extra}", "bad", 3 if sev >= 1 else 2, disaster=kind)
    city.publish_now(world, "company", f"{world.config.company_name}: {title.lower()}", f"{story}{extra}",
                     importance=3 if sev >= 1 else 2, tone="bad")
    return f"{title}: −€{cost:,.0f}.{extra}"


# ---------------------------------------------------------------------------------- the city
def _market(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    sector = p.get("sector") or "betting"
    if sector != "all" and sector not in SECTORS:
        raise GodError(f"unknown sector '{sector}'")
    pct = clamp(float(p.get("pct", -0.25)), -0.6, 0.6)
    city.shock_prices(world, None if sector == "all" else str(sector), pct)
    what = "Shares" if sector == "all" else f"{city.SECTOR_LABEL.get(str(sector), sector).capitalize()} shares"
    verb = "crash" if pct <= -0.15 else "slide" if pct < 0 else "soar" if pct >= 0.15 else "climb"
    headline = f"{what} {verb} {abs(pct):.0%} in a day"
    effect = "Listed bookmakers set the price of our subscriber business." if sector in ("betting", "all") else ""
    city.publish_now(world, "business", headline, "Traders struggle to explain the move.", [], pct, 3,
                     "good" if pct > 0 else "bad", effect)
    _log(world, headline, effect or "The city's market moved.", "good" if pct > 0 else "bad", sector=sector)
    return headline


def _headline(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    text = str(p.get("headline") or "").strip()[:120]
    if not text:
        raise GodError("write a headline")
    body = str(p.get("body") or "").strip()[:300]
    ticker = str(p.get("ticker") or "").upper().strip()
    move = None
    if ticker:
        if ticker not in world.city.stocks:
            raise GodError(f"no listed company '{ticker}'")
        move = clamp(float(p.get("pct", 0.0)), -0.6, 0.6)
        if move:
            city.shock_prices(world, None, move, ticker=ticker)
    city.publish_now(world, str(p.get("section") or "city") if p.get("section") in ("business", "city", "sports",
                                                                                      "company") else "city",
                     text, body, [ticker] if ticker else [], move, 3,
                     "good" if (move or 0) > 0 else "bad" if (move or 0) < 0 else "neutral")
    _log(world, f"Planted story: {text}", body, "neutral", 1)
    return f"Printed: “{text}”"


# ---------------------------------------------------------------------------------- people
def _morale(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    delta = clamp(float(p.get("delta", -0.2)), -0.5, 0.5)  # positive = calmer
    staff = [e for e in world.active_employees() if e.role != "ceo"]
    for e in staff:
        e.psyche.stress = clamp(e.psyche.stress - delta, 0.02, 0.98)
        e.psyche.confidence = clamp(e.psyche.confidence + delta * 0.3, 0.05, 0.95)
    what = "Team retreat: everyone comes back calmer" if delta > 0 else "A wave of panic sweeps the office"
    _log(world, what, f"Stress {'−' if delta > 0 else '+'}{abs(delta):.0%} for {len(staff)} people.",
         "good" if delta > 0 else "bad")
    return what


def _replace_ceo(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    style = str(p.get("style") or "")
    old = world.ceo()
    if style not in CEO_STYLES:
        style = rng.choice([s for s in CEO_STYLES if s != old.ceo_style])
    new = drama.replace_ceo(world, rng, style, "removed by the owners")
    _log(world, f"The owners replace {old.name} with {new.name}", f"New style: {style.replace('_', ' ')}.", "neutral", 3)
    return f"{new.name} is the new CEO ({style.replace('_', ' ')})"


def _star(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    cand = generate_candidates(world, rng, 1)[0]
    if cand.role != "tipster":
        cand = next((c for c in generate_candidates(world, rng, 6) if c.role == "tipster"), cand)
    strat = world.strategies.get(cand.strategy_id or "")
    if strat is not None:  # a genuinely strong method: rates teams on expected goals, picky about edges
        strat.xg_weight = max(strat.xg_weight, 0.85)
        strat.min_edge = max(strat.min_edge, 0.03)
    cand.cv_rating = 96
    cand.experience_years = max(cand.experience_years, 9)
    cand.salary_ask = round(cand.salary_ask * 1.4, 0)
    cand.pitch = "A legend on the circuit. Every syndicate in Portavia wants them."
    world.candidates.append(cand)
    _log(world, f"Star applicant: {cand.name}", "Waiting in the candidate pool for the CEO's next review.", "good")
    return f"{cand.name} joined the candidate pool"


def _subscribers(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    delta = int(clamp(float(p.get("delta", 40)), -100_000, 100_000))
    f = world.finances
    f.subscribers = max(0, f.subscribers + delta)
    what = (f"A tip goes viral: +{delta} subscribers" if delta >= 0 else f"Bad press: {-delta} subscribers cancel")
    _log(world, what, "", "good" if delta >= 0 else "bad")
    return what


# ---------------------------------------------------------------------------------- office & rules
def _facility(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    key = str(p.get("facility") or "")
    if key not in EC.FACILITIES:
        raise GodError("unknown facility")
    if p.get("op") == "release":
        ok, msg = management.release_facility(world, key, free=True)
    else:
        ok, msg = management.lease_facility(world, key, free=True)
    if not ok:
        raise GodError(msg)
    _log(world, f"Sandbox: {msg}", "", "neutral", 1)
    return msg


def _difficulty(world: World, rng: random.Random, p: dict[str, Any]) -> str:
    level = str(p.get("level") or "")
    if level not in EC.DIFFICULTY:
        raise GodError("difficulty is easy, normal or hard")
    old = world.config.difficulty
    world.config.difficulty = level
    _log(world, f"Difficulty changed: {old} → {level}", "Costs and subscriber growth follow the new preset.", "neutral")
    return f"difficulty is now {level}"


_HANDLERS = {
    "invest": _invest, "windfall": _windfall, "disaster": _disaster, "market": _market, "headline": _headline,
    "morale": _morale, "replace_ceo": _replace_ceo, "star": _star, "subscribers": _subscribers,
    "facility": _facility, "difficulty": _difficulty,
}


def catalog() -> dict[str, Any]:
    """What the UI may offer (so the panel never shows a tool the backend lacks)."""
    return {
        "actions": sorted(_HANDLERS),
        "disasters": [{"key": k, "title": v[0], "share": v[2]} for k, v in DISASTERS.items()],
        "severities": list(SEVERITY),
        "windfalls": [{"key": k, "label": v} for k, v in WINDFALLS.items()],
        "sectors": list(SECTORS),
        "facilities": [{"key": k, "name": v["name"]} for k, v in EC.FACILITIES.items()],
        "ceo_styles": list(CEO_STYLES),
        "difficulties": list(EC.DIFFICULTY),
    }
