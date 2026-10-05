"""Mock LAB researcher: proposes strategy hypotheses by mutating what the company already runs.

Researcher flavour decides which knobs get turned; personality decides how boldly.
"""

from __future__ import annotations

import random
from typing import Any

from app.domain.base import clamp

KNOBS = {
    "quant_research": ["xg_weight", "half_life", "window", "shrinkage", "opponent_adjust", "model_weight"],
    "market_research": ["model_weight", "min_edge", "max_odds", "min_odds", "markets", "fade_popular"],
    "behavioral_research": ["fade_popular", "underdog_bias", "news_weight", "min_odds", "max_odds", "half_life"],
}
COMP_NAMES = {"BL1": "Bundesliga", "PL": "Premier League", "LL": "La Liga", "SA": "Serie A", "UCL": "Champions League"}
DEFAULT = {"competitions": [], "markets": ["home_win", "draw", "away_win"], "model_weight": 0.6, "window": 15,
           "half_life": 8.0, "shrinkage": 4.0, "home_adv": 1.0, "news_weight": 0.8, "xg_weight": 0.3,
           "opponent_adjust": False, "underdog_bias": 0.0, "fade_popular": False, "min_odds": 1.4, "max_odds": 6.0,
           "min_edge": 0.03, "kelly_fraction": 0.25}


def hypothesize(ctx: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    r = ctx["researcher"]
    t = r["traits"]
    bounds = ctx["param_bounds"]
    creativity = clamp(0.3 + 0.5 * t["risk_seeking"] + 0.3 * (1 - t["cautious"]) - 0.2 * t["stubborn"], 0.1, 1.0)
    live = ctx["live_strategies"]
    proven = [s for s in live if s["bets"] >= 30]
    if proven and rng.random() < 0.6:
        base = max(proven, key=lambda s: s["roi"])
        origin = f"building on {base['name']} (live ROI {base['roi']:+.1%})"
    elif live:
        base = rng.choice(live)
        origin = f"a variation of {base['name']}"
    else:
        base = {"params": DEFAULT}
        origin = "a fresh baseline"
    params = dict(DEFAULT)
    params.update({k: v for k, v in base["params"].items() if v is not None})
    knobs = KNOBS.get(r["specialty"], KNOBS["quant_research"])
    changed: list[str] = []
    for knob in rng.sample(knobs, min(len(knobs), 1 + int(creativity * 3))):
        changed.append(knob)
        if knob == "opponent_adjust":
            params[knob] = not params.get(knob, False)
        elif knob == "fade_popular":
            params[knob] = not params.get(knob, False)
            if params[knob]:
                params["markets"] = ["home_win", "draw", "away_win"]
        elif knob == "markets":
            params["markets"] = rng.choice([["home_win", "draw", "away_win"], ["home_win", "away_win"],
                                            ["over_2_5", "under_2_5"], ["under_2_5"], ["draw"],
                                            ["home_win", "draw", "away_win", "over_2_5", "under_2_5"]])
        else:
            lo, hi = bounds[knob]
            span = (hi - lo) * (0.15 + 0.35 * creativity)
            value = float(params.get(knob, (lo + hi) / 2)) + rng.uniform(-span, span)
            if knob == "xg_weight" and rng.random() < 0.5:
                value = float(params.get(knob, 0.3)) + abs(rng.uniform(0, span))  # quants love xG
            value = clamp(value, lo, hi)
            params[knob] = int(round(value)) if knob == "window" else round(value, 3)
    if params["min_odds"] >= params["max_odds"]:
        params["max_odds"] = clamp(params["min_odds"] + 1.5, *bounds["max_odds"])
    comps = ctx["competitions_covered"] or list(COMP_NAMES)
    if rng.random() < 0.5:
        params["competitions"] = [rng.choice(comps)]
    elif not params.get("competitions"):
        params["competitions"] = list(comps)
    brief = ctx.get("brief")  # player mode only: the CEO's research brief
    if brief:
        if rng.random() < 0.6 * t["stubborn"]:
            origin += ", ignoring the CEO's brief"
        else:
            _apply_brief(params, brief, bounds)
            origin += f", following the brief ({brief['label']})"
    name = _name(params, changed, rng)
    return {"name": name, "hypothesis": _hypothesis(params), "rationale": f"{r['name']}'s idea, {origin}; "
            f"tweaking {', '.join(c.replace('_', ' ') for c in changed)}.", "params": params}


def _apply_brief(params: dict[str, Any], brief: dict[str, Any], bounds: dict[str, list[float]]) -> None:
    kind, value = brief.get("kind"), brief.get("value")
    if kind == "competition" and value:
        params["competitions"] = [value]
    elif kind == "desk" and brief.get("competitions"):
        params["competitions"] = list(brief["competitions"])
    elif kind == "market" and value:
        params["markets"] = [value]
        if value in ("over_2_5", "under_2_5"):
            params["fade_popular"] = False
    elif kind == "underdogs":
        params["underdog_bias"] = clamp(max(float(params.get("underdog_bias", 0.0)), 0.03), *bounds["underdog_bias"])
        params["min_odds"] = clamp(max(float(params["min_odds"]), 2.4), *bounds["min_odds"])
        params["max_odds"] = clamp(max(float(params["max_odds"]), 7.0), *bounds["max_odds"])
        if not set(params["markets"]) & {"home_win", "away_win"}:
            params["markets"] = ["home_win", "away_win"]


def _name(p: dict[str, Any], changed: list[str], rng: random.Random) -> str:
    comp = COMP_NAMES.get(p["competitions"][0], "Multi-league") if len(p["competitions"]) == 1 else "Multi-league"
    if p.get("fade_popular"):
        core = "Giant Killer"
    elif p.get("xg_weight", 0) >= 0.7 and p.get("half_life", 8) <= 5:
        core = "xG Momentum"
    elif p.get("xg_weight", 0) >= 0.7:
        core = "xG Engine"
    elif p.get("model_weight", 0.5) <= 0.15:
        core = "Line Shopper"
    elif set(p.get("markets", [])) <= {"over_2_5", "under_2_5"}:
        core = "Goal Line"
    elif p.get("underdog_bias", 0) > 0.015:
        core = "Underdog Bite"
    elif p.get("min_edge", 0.03) >= 0.06:
        core = "Sniper"
    else:
        core = rng.choice(["Drift", "Baseline Plus", "Signal", "Compass", "Lighthouse"])
    return f"{comp} {core} v{rng.randint(1, 9)}"


def _hypothesis(p: dict[str, Any]) -> str:
    comps = ", ".join(COMP_NAMES.get(c, c) for c in p["competitions"]) or "all covered leagues"
    markets = ", ".join(m.replace("_", " ") for m in p["markets"])
    model = ("pure market consensus" if p["model_weight"] <= 0.1 else
             f"a {int(p['model_weight'] * 100)}% model blend rating teams {int(p['xg_weight'] * 100)}% on xG "
             f"(half-life {p['half_life']:.0f} matches)")
    extra = " fading popular clubs" if p.get("fade_popular") else ""
    return (f"In {comps}, {markets} picks{extra} from {model} with edge ≥{p['min_edge']:.0%} at odds "
            f"{p['min_odds']:.2f}–{p['max_odds']:.2f} beat the closing market.")
