"""Strategy models: turn observable data into probabilities, fair prices, edges and candidates.

Only public information is used: finished results before `as_of`, published news, and the
odds on offer. This is the same code for live tipsters and for LAB backtests.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.base import Model
from app.domain.sports import MARKET_GROUPS, Match, OddsLine
from app.domain.strategy import Strategy

from .index import SportsIndex
from .poisson import outcome_probs

NEWS_ASSUMED_EFFECT = 0.08  # analysts' belief about impact per severity point


class MatchEstimate(Model):
    match_id: str
    probs: dict[str, float]  # final blended probabilities per selection
    model_probs: dict[str, float]
    market_probs: dict[str, float]
    lam_home: float
    lam_away: float
    sample_home: float
    sample_away: float


class BetCandidate(Model):
    market: str
    book: str
    odds: float
    prob: float
    edge: float
    fair_odds: float
    meets_strategy: bool
    blocked_by: str = ""


def _weighted_rates(index: SportsIndex, team_id: str, as_of: datetime, s: Strategy,
                    opp: dict[str, tuple[float, float]] | None) -> tuple[float, float, float]:
    """Attack and defensive-weakness multipliers relative to league average, plus sample weight."""
    key = (team_id, as_of.date(), s.window, round(s.half_life, 2), round(s.shrinkage, 2), round(s.xg_weight, 2),
           opp is not None)
    cache = index.strength_cache()
    if key in cache:
        return cache[key]
    history = index.team_history(team_id, as_of, s.window)
    att_num = weak_num = wsum = 0.0
    xw = s.xg_weight
    n = len(history)
    for rank, m in enumerate(reversed(history)):  # rank 0 = most recent
        w = 0.5 ** (rank / s.half_life)
        avg_h, avg_a = index.league_averages(m.competition, as_of, league_sample(s))
        hg, ag = _blend(m.home_goals, m.home_xg, xw), _blend(m.away_goals, m.away_xg, xw)
        if m.home_id == team_id:
            gf, ga, exp_f, exp_a, other = hg, ag, avg_h, avg_a, m.away_id
        else:
            gf, ga, exp_f, exp_a, other = ag, hg, avg_a, avg_h, m.home_id
        if opp is not None and other in opp:
            o_att, o_weak = opp[other]
            exp_f *= o_weak
            exp_a *= o_att
        att_num += w * gf / max(exp_f, 0.2)
        weak_num += w * ga / max(exp_a, 0.2)
        wsum += w
    k = s.shrinkage
    result = ((att_num + k) / (wsum + k), (weak_num + k) / (wsum + k), float(n))
    cache[key] = result
    return result


def league_sample(s: Strategy) -> int:
    """How many recent league matches the strategy uses to estimate league scoring levels."""
    return int(min(380, max(60, s.window * 10)))


def _blend(goals: int | None, xg: float | None, xg_weight: float) -> float:
    if xg is None or xg_weight <= 0:
        return float(goals or 0)
    return xg_weight * xg + (1 - xg_weight) * (goals or 0)


def _team_rates(index: SportsIndex, team_id: str, as_of: datetime, s: Strategy) -> tuple[float, float, float]:
    if not s.opponent_adjust:
        return _weighted_rates(index, team_id, as_of, s, None)
    opp: dict[str, tuple[float, float]] = {}
    for m in index.team_history(team_id, as_of, s.window):
        other = m.away_id if m.home_id == team_id else m.home_id
        if other not in opp:
            a, w, _ = _weighted_rates(index, other, as_of, s, None)
            opp[other] = (a, w)
    return _weighted_rates(index, team_id, as_of, s, opp)


def _news_multipliers(index: SportsIndex, team_id: str, as_of: datetime, weight: float) -> tuple[float, float]:
    att = weak = 1.0
    if weight <= 0:
        return att, weak
    for n in index.active_news(team_id, as_of):
        if n.kind == "injury_attack":
            att *= 1 - NEWS_ASSUMED_EFFECT * n.severity * weight
        elif n.kind == "injury_defense":
            weak *= 1 + NEWS_ASSUMED_EFFECT * n.severity * weight
        elif n.kind == "manager_change":
            att *= 1 + 0.04 * weight
            weak *= 1 - 0.02 * weight
    return max(att, 0.5), max(weak, 0.5)


def devig(odds: list[float]) -> list[float]:
    """Remove the overround assuming longshots carry more of it (better than proportional)."""
    q = [1.0 / o for o in odds]
    margin = sum(q) - 1.0
    n = len(q)
    p = [max(1e-4, (qi - 0.5 * margin / n) / (1 + 0.5 * margin)) for qi in q]
    total = sum(p)
    return [x / total for x in p]


def market_consensus(lines: dict[str, OddsLine]) -> dict[str, float]:
    """Margin-free probabilities averaged across books, weighting sharper (lower-margin) books more."""
    out: dict[str, float] = {}
    if not lines:
        return out
    for markets in MARKET_GROUPS.values():
        acc = {m: 0.0 for m in markets}
        wsum = 0.0
        for line in lines.values():
            odds = [line.get(m) for m in markets]
            margin = max(0.005, sum(1.0 / o for o in odds) - 1.0)
            w = 1.0 / margin
            for m, p in zip(markets, devig(odds)):
                acc[m] += w * p
            wsum += w
        for m in markets:
            out[m] = acc[m] / wsum
    return out


def estimate_match(index: SportsIndex, match: Match, s: Strategy, as_of: datetime,
                   popular: set[str] | None = None, lines: dict[str, OddsLine] | None = None) -> MatchEstimate:
    lines = lines if lines is not None else match.odds
    avg_h, avg_a = index.league_averages(match.competition, as_of, league_sample(s))
    if match.neutral:
        avg_h = avg_a = (avg_h + avg_a) / 2
    att_h, weak_h, n_h = _team_rates(index, match.home_id, as_of, s)
    att_a, weak_a, n_a = _team_rates(index, match.away_id, as_of, s)
    na_h, nw_h = _news_multipliers(index, match.home_id, as_of, s.news_weight)
    na_a, nw_a = _news_multipliers(index, match.away_id, as_of, s.news_weight)
    home_adv = 1.0 if match.neutral else s.home_adv
    lam_h = avg_h * home_adv * att_h * na_h * weak_a * nw_a
    lam_a = avg_a * att_a * na_a * weak_h * nw_h
    p1, px, p2, pov = outcome_probs(lam_h, lam_a)
    model = {"home_win": p1, "draw": px, "away_win": p2, "over_2_5": pov, "under_2_5": 1 - pov}
    if s.underdog_bias:
        dog, fav = ("away_win", "home_win") if p2 < p1 else ("home_win", "away_win")
        shift = min(s.underdog_bias, model[fav] - 0.02) if s.underdog_bias > 0 else max(s.underdog_bias, -(model[dog] - 0.02))
        model[dog] += shift
        model[fav] -= shift
    market = market_consensus(lines)
    w = s.model_weight if market else 1.0
    probs = {k: w * model[k] + (1 - w) * market.get(k, model[k]) for k in model}
    for markets in MARKET_GROUPS.values():
        total = sum(probs[m] for m in markets)
        for m in markets:
            probs[m] /= total
    return MatchEstimate(match_id=match.id, probs=probs, model_probs=model, market_probs=market,
                         lam_home=lam_h, lam_away=lam_a, sample_home=n_h, sample_away=n_a)


def candidates(match: Match, est: MatchEstimate, s: Strategy, popular: set[str] | None = None,
               lines: dict[str, OddsLine] | None = None) -> list[BetCandidate]:
    """Every priced selection with its edge at the best available price, best first."""
    lines = lines if lines is not None else match.odds
    out: list[BetCandidate] = []
    if not lines:
        return out
    popular = popular or set()
    for market, prob in est.probs.items():
        book, odds = max(((b, ln.get(market)) for b, ln in lines.items()), key=lambda x: x[1])
        edge = prob * odds - 1.0
        blocked = ""
        if market not in s.markets:
            blocked = "market not in strategy"
        elif odds < s.min_odds or odds > s.max_odds:
            blocked = "odds outside strategy range"
        elif s.fade_popular and not _fades_popular(match, market, popular):
            blocked = "not a fade of a popular club"
        elif edge < s.min_edge:
            blocked = "edge below strategy minimum"
        out.append(BetCandidate(market=market, book=book, odds=odds, prob=prob, edge=edge,
                                fair_odds=1.0 / max(prob, 1e-6), meets_strategy=not blocked, blocked_by=blocked))
    out.sort(key=lambda c: (-c.meets_strategy, -c.edge))
    return out


def _fades_popular(match: Match, market: str, popular: set[str]) -> bool:
    home_pop, away_pop = match.home_id in popular, match.away_id in popular
    if home_pop == away_pop:
        return False
    if home_pop:
        return market in ("draw", "away_win")
    return market in ("draw", "home_win")


def best_candidate(match: Match, est: MatchEstimate, s: Strategy, popular: set[str] | None = None,
                   lines: dict[str, OddsLine] | None = None) -> BetCandidate | None:
    for c in candidates(match, est, s, popular, lines):
        if c.meets_strategy:
            return c
    return None


def kelly_stake_fraction(prob: float, odds: float) -> float:
    if odds <= 1.0:
        return 0.0
    return max(0.0, (prob * odds - 1.0) / (odds - 1.0))
