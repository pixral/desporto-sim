"""Mock tipster judgement: a stochastic, multi-factor stand-in for an LLM.

It reads the exact context an LLM would receive and produces the same JSON. Behaviour emerges
from the interaction of traits, psychological state, career pressure, company condition and
coworker opinions — no single rule says "losing company => stupid bets". The same pressure
makes a cautious analyst freeze and an ambitious risk-seeker swing for the fences.
"""

from __future__ import annotations

import random
from typing import Any

from app.domain.base import clamp

STATUS_DISTRESS = {"thriving": 0.0, "stable": 0.15, "strained": 0.45, "distress": 0.8, "bankrupt": 1.0}

# Stake size in units of the CEO's max stake ("unit staking" with a personal touch). Tuned with headless
# batch runs: sizing strongly by perceived edge or shrinking longshot stakes made companies lose more,
# because the biggest stakes landed on the noisiest bets (see docs/ECONOMY.md).
SIZING: dict[str, float] = {
    "base": 0.5, "margin": 1.0, "margin_cap": 0.25, "risk": 0.15, "conf": 0.05, "desperation": 0.25,
    "hubris": 0.05, "fear": 0.2, "odds_exp": 0.0, "max_out_at": 0.6,
}


def _state(ctx: dict[str, Any]) -> dict[str, float]:
    a = ctx["agent"]
    t = a["traits"]
    stress, conf, rep = a["stress"], a["confidence"], a["reputation"]
    streak = a["streak"]
    distress = STATUS_DISTRESS.get(ctx["company"]["status"], 0.2)
    review = 1.0 if a["under_review"] else 0.0
    career_threat = 0.55 * review + 0.25 * clamp((45 - rep) / 30, 0, 1) + 0.2 * distress
    desperation = clamp(
        career_threat * (0.35 + 0.6 * t["risk_seeking"] + 0.35 * t["ambitious"]) * (0.4 + stress)
        - 0.35 * t["cautious"], 0, 1)
    fear = clamp(
        (0.5 - conf) * 1.6 * (0.4 + t["cautious"]) * (1 - 0.7 * desperation)
        + 0.25 * max(0, -streak - 3) / 5 * t["cautious"], 0, 1)
    hubris = clamp((conf - 0.58) * 1.8 * (0.4 + t["aggressive"] + 0.5 * t["ambitious"])
                   + 0.15 * max(0, streak - 3) / 4, 0, 1)
    inactivity = clamp((a["no_bet_rate"] - 0.75) * 3 * (0.3 + review + distress) * (0.5 + t["ambitious"]), 0, 1)
    return {"desperation": desperation, "fear": fear, "hubris": hubris, "inactivity": inactivity,
            "stress": stress, "conf": conf, "risk": a["risk_tolerance"], "distress": distress, "review": review}


def decide_day(ctx: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    a = ctx["agent"]
    t = a["traits"]
    s = _state(ctx)
    strat = ctx["strategy"]
    cons = ctx["constraints"]
    allocation = max(ctx["department"]["allocation"], 0.0)
    max_stake = cons["max_stake"]
    bankroll_left = cons["available_bankroll"]
    bets_left = cons["max_bets"]
    shift = (0.02 * t["cautious"] + 0.01 * t["skeptical"] - 0.015 * t["risk_seeking"]
             + 0.03 * s["fear"] - 0.04 * s["desperation"] - 0.025 * s["inactivity"] - 0.012 * s["hubris"])
    threshold = strat["min_edge"] + shift
    decisions: list[dict[str, Any]] = []
    for m in ctx["matches"]:
        best: dict[str, Any] | None = None
        for c in m["candidates"]:
            perceived = c["edge"] + 0.03 * s["hubris"] - 0.015 * s["fear"]
            influence: list[str] = []
            social_w = (0.6 * t["collaborative"] + 0.2 - 0.5 * t["independent"]) * (1 - 0.6 * t["stubborn"])
            for cw in m["coworkers"]:
                w = (cw["trust"] - 45) / 40 * social_w
                if cw["market"] == c["market"]:
                    perceived += 0.02 * w
                    if 0.02 * w > 0.001:
                        influence.append(cw["name"])
                elif w > 0:
                    perceived -= 0.008 * w
            longshot_push = 0.0
            if s["desperation"] > 0.4 and c["odds"] >= 3.0:
                longshot_push = 0.035 * s["desperation"]
                perceived += longshot_push
            if t["skeptical"] > 0.6 and c["odds"] >= 5.0:
                perceived -= 0.02
            perceived += rng.gauss(0, 0.01 * (1 + 1.5 * s["stress"]))
            off_strategy = not c["meets_strategy"] and c["blocked_by"] != "edge below strategy minimum"
            if off_strategy:
                discipline = 0.6 * t["stubborn"] + 0.4 * t["cautious"] - 0.8 * s["desperation"] - 0.3 * s["hubris"]
                if discipline > 0.15:
                    continue
                perceived -= 0.01
            margin = perceived - threshold
            if best is None or margin > best["margin"]:
                best = {"c": c, "margin": margin, "perceived": perceived, "influence": influence,
                        "longshot": longshot_push, "off": off_strategy}
        if best is not None and best["margin"] > 0 and bets_left > 0 and bankroll_left > 2 and max_stake >= 1:
            c = best["c"]
            odds = c["odds"]
            # Stakes are sized in "units" of the CEO's stake limit. Conviction, risk appetite and mood
            # move the size; longshots get smaller stakes; the strategy's Kelly fraction scales it all.
            z = SIZING
            size = (z["base"] + z["margin"] * min(best["margin"], z["margin_cap"]) + z["risk"] * (s["risk"] - 0.4)
                    + z["conf"] * (s["conf"] - 0.5) + z["desperation"] * s["desperation"] + z["hubris"] * s["hubris"]
                    - z["fear"] * s["fear"])
            size *= min(1.0, (2.5 / odds) ** z["odds_exp"]) * (strat["kelly_fraction"] / 0.25) ** 0.5
            size = clamp(size, 0.12, 1.0)
            if s["desperation"] > z["max_out_at"]:
                size = max(size, 0.6 + 0.4 * s["desperation"])
            stake = max_stake * size
            stake = clamp(stake, 1.0, min(max_stake, bankroll_left))
            stake = round(stake * 2) / 2
            if stake < 1.0:
                decisions.append(_no_bet(m, "Stake would be too small to matter.", 0.3))
                continue
            bets_left -= 1
            bankroll_left -= stake
            decisions.append({
                "match_id": m["match_id"], "decision": "BET", "market": c["market"], "selection": c["selection"],
                "odds": odds, "stake": stake,
                "confidence": round(clamp(0.5 + best["margin"] * 6 + 0.2 * (s["conf"] - 0.5), 0.05, 0.95), 2),
                "reason": _bet_reason(best, s, m), "influenced_by": best["influence"][:2],
            })
        else:
            decisions.append(_no_bet(m, _pass_reason(best, s, threshold, bets_left), _pass_conf(best, s)))
    return {"thought": _thought(ctx, s, decisions), "decisions": decisions}


def _no_bet(m: dict[str, Any], reason: str, conf: float) -> dict[str, Any]:
    return {"match_id": m["match_id"], "decision": "NO_BET", "confidence": round(conf, 2), "reason": reason,
            "influenced_by": []}


def _pass_conf(best: dict[str, Any] | None, s: dict[str, float]) -> float:
    if best is None:
        return 0.6
    return clamp(0.55 - best["margin"] * 5 + 0.1 * s["fear"], 0.1, 0.9)


def _bet_reason(best: dict[str, Any], s: dict[str, float], m: dict[str, Any]) -> str:
    c = best["c"]
    sel, odds, book = c["selection"], c["odds"], c["book"]
    implied = 1 / odds
    if best["influence"]:
        return f"{best['influence'][0]} likes {sel} too and they've been sharp lately. Taking {odds} at {book}."
    if best["longshot"] > 0.02:
        return f"Need a result. {sel} at {odds} has enough upside to matter; model says {c['prob']:.0%}."
    if best["off"]:
        return f"Outside my usual filters, but {sel} at {odds} looks mispriced. Breaking my own rules once."
    if s["hubris"] > 0.45:
        return f"I'm reading this league better than the books right now. {sel} at {odds} is a gift."
    if s["inactivity"] > 0.4 and best["margin"] < 0.015:
        return f"Too many passes lately. Thin edge on {sel} ({c['edge']:+.1%}) but defensible."
    return (f"Model {c['prob']:.0%} vs market {implied:.0%} on {sel}: {c['edge']:+.1%} edge at {odds} ({book}).")


def _pass_reason(best: dict[str, Any] | None, s: dict[str, float], threshold: float, bets_left: int) -> str:
    if best is not None and best["margin"] > 0 and bets_left <= 0:
        return "Daily bet limit reached; letting this one go."
    if best is None:
        return "Nothing here fits my strategy filters."
    if s["fear"] > 0.45:
        return "After this run of results I'm not forcing anything."
    if best["perceived"] < 0:
        return "Market looks efficient here. No value on any side."
    return f"Best angle is {best['c']['selection']} at {best['perceived']:+.1%} perceived edge, below my {threshold:.1%} bar."


def _thought(ctx: dict[str, Any], s: dict[str, float], decisions: list[dict[str, Any]]) -> str:
    a = ctx["agent"]
    dept = ctx["department"]
    spec = a["specialty_label"].split(" ")[0]
    streak = a["streak"]
    bets = sum(1 for d in decisions if d["decision"] == "BET")
    options: list[tuple[float, str]] = []
    if s["desperation"] > 0.5:
        options.append((s["desperation"], "Management is watching. If this week goes badly I'm out — time to swing."))
    if s["fear"] > 0.45:
        options.append((s["fear"], f"My {spec} reads have been unreliable lately. Better to sit on my hands."))
    if s["hubris"] > 0.45:
        options.append((s["hubris"], "I'm seeing things the bookies aren't. This is my moment."))
    if streak <= -4:
        options.append((0.6, f"{-streak} losses in a row. Is it variance, or is it me?"))
    if streak >= 4:
        options.append((0.5, f"{streak} winners on the bounce. Don't get cocky. ...Okay, a little cocky."))
    if s["distress"] >= 0.45:
        options.append((s["distress"] * 0.8, "Everyone's whispering about the runway. Hard to focus."))
    if dept["month_profit"] < -100:
        options.append((0.45, f"The {dept['name']} is €{-dept['month_profit']:.0f} down this month. Not great."))
    if s["review"]:
        options.append((0.55, "Being under review makes every click feel heavier."))
    if s["inactivity"] > 0.4:
        options.append((s["inactivity"], "I keep passing. Someone upstairs will start asking why."))
    if not options:
        if bets == 0:
            options.append((0.3, "Plenty of matches, few real edges. Patience is a position too."))
        else:
            options.append((0.3, "Model's ticking along. Stick to the process."))
    options.sort(key=lambda x: -x[0])
    return options[0][1]
