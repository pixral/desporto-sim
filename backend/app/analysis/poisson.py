"""Independent-Poisson score model. Pure math, shared by analysts and the mock world."""

from __future__ import annotations

import math

MAX_GOALS = 10


def pmf(lam: float, max_goals: int = MAX_GOALS) -> list[float]:
    lam = max(lam, 1e-6)
    out = [math.exp(-lam)]
    for k in range(1, max_goals + 1):
        out.append(out[-1] * lam / k)
    return out


def outcome_probs(lam_home: float, lam_away: float) -> tuple[float, float, float, float]:
    """Returns (p_home_win, p_draw, p_away_win, p_over_2_5), normalized over the truncated grid."""
    ph = pmf(lam_home)
    pa = pmf(lam_away)
    home = draw = away = under = 0.0
    total = 0.0
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            p = pi * pj
            total += p
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
            if i + j <= 2:
                under += p
    return home / total, draw / total, away / total, 1.0 - under / total


def sample_poisson(lam: float, u: float) -> int:
    """Inverse-CDF sample using a supplied uniform `u` (keeps RNG streams explicit)."""
    p = math.exp(-lam)
    cdf = p
    k = 0
    while u > cdf and k < 15:
        k += 1
        p *= lam / k
        cdf += p
    return k
