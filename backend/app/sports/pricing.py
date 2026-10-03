"""Bookmaker pricing helpers: margins with favourite-longshot bias, and odds ladders."""

from __future__ import annotations

import math

_LADDER = ((2.0, 0.01), (3.0, 0.02), (4.0, 0.05), (6.0, 0.1), (10.0, 0.2), (20.0, 0.5), (1e9, 1.0))


def round_odds(odds: float) -> float:
    """Round down onto a realistic price ladder (bookmakers round in their own favour)."""
    odds = max(1.01, odds)
    for limit, step in _LADDER:
        if odds < limit:
            return round(max(1.01, math.floor(odds / step + 1e-9) * step), 2)
    return round(odds, 2)


def price(probs: list[float], margin: float, longshot_bias: float = 0.5) -> list[float]:
    """Turn fair probabilities into decimal odds carrying `margin` overround.

    Longshots absorb a bigger share of the margin when `longshot_bias` > 0, which is how real
    books behave and why backing big outsiders blindly is a slow way to go broke.
    """
    n = len(probs)
    implied = [p * (1 + margin) + longshot_bias * margin * (1.0 / n - p) for p in probs]
    return [round_odds(1.0 / max(q, 1e-4)) for q in implied]


def fair_probs(odds: list[float]) -> list[float]:
    """Remove the overround proportionally."""
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]
