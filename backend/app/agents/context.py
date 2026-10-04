"""Build the structured situation each agent sees.

The same dict feeds both the mock policies and the LLM prompt renderer, so the mock and a real
model always make decisions from identical information.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.analysis.index import SportsIndex
from app.analysis.models import BetCandidate, MatchEstimate
from app.domain.base import Model
from app.domain.people import Employee
from app.domain.sports import Match
from app.domain.strategy import PARAM_BOUNDS
from app.domain.world import World
from app.economy import bookmakers
from app.economy import config as EC
from app.economy import market
from app.economy import valuation as val
from app.simulation import metrics

from .catalog import CEO_STYLE_INFO, DEPARTMENT_KINDS, MAX_DESK_SIZE, SPECIALTIES

SELECTION_LABELS = {"draw": "Draw", "over_2_5": "Over 2.5 goals", "under_2_5": "Under 2.5 goals"}


class MatchAnalysis(Model):
    match: Match
    estimate: MatchEstimate
    candidates: list[BetCandidate]


class Leaning(Model):
    employee_id: str
    market: str
    edge: float


def selection_label(world: World, match: Match, market: str) -> str:
    if market == "home_win":
        return world.team_name(match.home_id)
    if market == "away_win":
        return world.team_name(match.away_id)
    return SELECTION_LABELS[market]


def _r(x: float, n: int = 3) -> float:
    return round(float(x), n)


def recent_layoffs(world: World, days: int = 30) -> int:
    cutoff = world.today - timedelta(days=days)
    return sum(1 for e in world.employees.values()
               if e.left and e.left > cutoff and e.leave_reason and e.leave_reason.startswith("fired"))


def latest_memo(world: World) -> str:
    return world.memos[-1].text if world.memos else ""


def company_block(world: World) -> dict[str, Any]:
    ceo = world.ceo()
    runway = val.runway_months(world)
    return {
        "name": world.config.company_name,
        "status": world.finances.status,
        "runway_months": None if runway is None else _r(runway, 1),
        "month_net": _r(world.finances.month.net, 2),
        "layoffs_30d": recent_layoffs(world),
        "hiring_frozen": world.finances.hiring_frozen,
        "ceo_name": ceo.name,
        "ceo_style": CEO_STYLE_INFO[ceo.ceo_style or "data_driven"]["label"],
        "memo": latest_memo(world),
    }


def allocation_for(world: World, emp: Employee) -> tuple[float, float]:
    """(allocation, max stake) for a tipster from their department bankroll."""
    dept = world.departments.get(emp.department_id or "")
    if dept is None or not dept.active:
        return 0.0, 0.0
    members = [e for e in world.department_members(dept.id) if e.role == "tipster"]
    total_w = sum(e.bankroll_weight for e in members) or 1.0
    allocation = max(0.0, dept.bankroll) * emp.bankroll_weight / total_w
    return allocation, allocation * dept.stake_limit_pct


def situation_notes(world: World, emp: Employee, recent: metrics.PerfStats) -> list[str]:
    notes: list[str] = []
    dept = world.departments.get(emp.department_id or "")
    if dept:
        verb = "lost" if dept.month_profit < 0 else "made"
        notes.append(f"The {dept.name} has {verb} €{abs(dept.month_profit):.0f} this month.")
        limited = [f"{b} €{v:.0f}" for b, v in sorted(dept.book_limits.items()) if v < EC.BOOK_LIMITS.get(b, v)]
        if limited:
            notes.append("Bookmakers limit your desk's stakes per bet: " + ", ".join(limited) + ".")
    reviewing = any(e.under_review for e in world.tipsters()) or recent_layoffs(world, 21) > 0
    if reviewing:
        notes.append("Management is reviewing staff.")
    if recent.bets:
        notes.append(f"Your recent ROI is {recent.roi:+.1%} over your last {recent.bets} settled bets.")
    notes.append(f"You have been with the company for {emp.tenure_days(world.today)} days.")
    notes.append(f"Your reputation is {emp.psyche.reputation:.0f}/100.")
    if emp.under_review:
        notes.append("You are formally under review after a warning from the CEO.")
    if emp.streak <= -3:
        notes.append(f"You are on a {-emp.streak}-bet losing streak.")
    elif emp.streak >= 3:
        notes.append(f"You are on a {emp.streak}-bet winning streak.")
    runway = val.runway_months(world)
    if runway is not None and runway < 12:
        notes.append(f"The company's runway is about {runway:.1f} months.")
    layoffs = recent_layoffs(world)
    if layoffs:
        notes.append(f"{layoffs} colleague(s) were let go in the last 30 days.")
    if world.finances.hiring_frozen:
        notes.append("Hiring is frozen.")
    if emp.under_review or emp.no_bet_rate() > 0.8:
        notes.append("A poor decision may hurt your career, but refusing every bet may also be viewed negatively.")
    notes.append("You earn a 10% bonus on any positive monthly profit you generate.")
    return notes


def build_tipster_context(world: World, index: SportsIndex, emp: Employee, analyses: list[MatchAnalysis],
                          leanings: dict[str, list[Leaning]], max_bets: int) -> dict[str, Any]:
    recent = metrics.recent_stats(world, emp, 30)
    dept = world.departments[emp.department_id] if emp.department_id else None
    allocation, max_stake = allocation_for(world, emp)
    strategy = world.strategies.get(emp.strategy_id or "")
    colleagues = []
    if dept:
        for other in world.department_members(dept.id):
            if other.id == emp.id or other.role != "tipster":
                continue
            rel = emp.relationships.get(other.id)
            colleagues.append({"id": other.id, "name": other.name,
                               "recent_roi": _r(metrics.recent_stats(world, other, 30).roi),
                               "trust": _r(rel.trust if rel else 50, 0)})
    matches: list[dict[str, Any]] = []
    for a in analyses:
        m = a.match
        before = m.kickoff
        news = [n.headline for tid in (m.home_id, m.away_id) for n in index.recent_news(tid, world.clock.now, 10)]
        odds: dict[str, Any] = {}
        for market in a.estimate.probs:
            best = m.best_price(market)
            if best:
                odds[market] = {"price": best[1], "book": best[0]}
        coworkers = []
        for lean in leanings.get(m.id, []):
            if lean.employee_id == emp.id:
                continue
            other = world.employees[lean.employee_id]
            rel = emp.relationships.get(other.id)
            trust = rel.trust if rel else 50.0
            if trust < 40 and other.department_id != emp.department_id:
                continue
            coworkers.append({"id": other.id, "name": other.name, "trust": _r(trust, 0),
                              "respect": _r(rel.respect if rel else 50, 0), "market": lean.market,
                              "selection": selection_label(world, m, lean.market), "edge": _r(lean.edge)})
        hg, hga = index.goal_averages(m.home_id, before)
        ag, aga = index.goal_averages(m.away_id, before)
        matches.append({
            "match_id": m.id,
            "label": world.match_label(m),
            "competition": world.competitions[m.competition].name,
            "stage": m.stage,
            "kickoff": m.kickoff.strftime("%a %H:%M"),
            "home": {"name": world.team_name(m.home_id), "form": index.form_string(m.home_id, before),
                     "gf": _r(hg, 2), "ga": _r(hga, 2)},
            "away": {"name": world.team_name(m.away_id), "form": index.form_string(m.away_id, before),
                     "gf": _r(ag, 2), "ga": _r(aga, 2)},
            "news": news[:4],
            "odds": odds,
            "model": {k: _r(v) for k, v in a.estimate.probs.items()},
            "market_implied": {k: _r(v) for k, v in a.estimate.market_probs.items()},
            "candidates": [{
                "market": c.market, "selection": selection_label(world, m, c.market), "odds": c.odds,
                "book": c.book, "prob": _r(c.prob), "edge": _r(c.edge), "meets_strategy": c.meets_strategy,
                "blocked_by": c.blocked_by,
            } for c in a.candidates[:4]],
            "coworkers": coworkers,
        })
    matches.sort(key=lambda x: -max((c["edge"] for c in x["candidates"]), default=-1))
    return {
        "date": world.today.isoformat(),
        "weekday": world.today.strftime("%A"),
        "agent": {
            "id": emp.id, "name": emp.name, "title": emp.title, "level": emp.level,
            "specialty": emp.specialty, "specialty_label": SPECIALTIES[emp.specialty].label,
            "tenure_days": emp.tenure_days(world.today),
            "traits": emp.traits.as_dict(), "traits_text": emp.traits.describe(),
            "stress": _r(emp.psyche.stress), "confidence": _r(emp.psyche.confidence),
            "risk_tolerance": _r(emp.psyche.risk_tolerance), "reputation": _r(emp.psyche.reputation, 1),
            "mood": emp.mood, "streak": emp.streak,
            "recent": {"bets": recent.bets, "roi": _r(recent.roi), "profit": _r(recent.profit, 2), "wins": recent.wins},
            "career": {"bets": emp.bets_total, "profit": _r(emp.profit, 2), "roi": _r(emp.roi)},
            "month_profit": _r(emp.month_profit, 2), "no_bet_rate": _r(emp.no_bet_rate(), 2),
            "under_review": emp.under_review, "warnings": emp.warnings, "salary": emp.salary,
        },
        "department": {
            "id": dept.id if dept else None, "name": dept.name if dept else "—",
            "bankroll": _r(dept.bankroll if dept else 0, 2), "month_profit": _r(dept.month_profit if dept else 0, 2),
            "stake_limit_pct": _r(dept.stake_limit_pct if dept else 0, 4),
            "allocation": _r(allocation, 2), "max_stake": _r(max_stake, 2), "colleagues": colleagues,
        },
        "company": company_block(world),
        "strategy": {
            "name": strategy.name if strategy else "none",
            "summary": strategy.summary() if strategy else "",
            "min_edge": strategy.min_edge if strategy else 0.03,
            "kelly_fraction": strategy.kelly_fraction if strategy else 0.25,
            "markets": strategy.markets if strategy else [],
        },
        "matches": matches,
        "constraints": {"max_bets": max_bets, "max_stake": _r(max_stake, 2), "min_stake": 1.0,
                        "available_bankroll": _r(dept.bankroll if dept else 0, 2)},
        "situation": situation_notes(world, emp, recent),
    }


# ---------------------------------------------------------------------------------- CEO
def employee_rows(world: World, days: int = 90) -> list[dict[str, Any]]:
    rows = []
    for e in world.active_employees():
        if e.role == "ceo":
            continue
        p = metrics.period_stats(world, e, days)
        career = metrics.PerfStats.from_bets(metrics.settled_bets(world, e))
        dept = world.departments.get(e.department_id or "")
        rows.append({
            "id": e.id, "name": e.name, "role": e.role, "title": e.title, "level": e.level,
            "department": dept.name if dept else None, "department_id": e.department_id,
            "specialty": SPECIALTIES[e.specialty].label if e.specialty in SPECIALTIES else e.specialty,
            "tenure_days": e.tenure_days(world.today), "salary": e.salary,
            "bets_90d": p.bets, "roi_90d": _r(p.roi), "profit_90d": _r(p.profit, 2), "z_90d": _r(p.z, 2),
            "career_profit": _r(e.profit, 2), "career_bets": career.bets, "career_roi": _r(career.roi),
            "z_career": _r(career.z, 2), "strategy_age_days": e.strategy_age_days(world.today),
            "no_bet_rate": _r(e.no_bet_rate(), 2),
            "reputation": _r(e.psyche.reputation, 1), "stress": _r(e.psyche.stress), "confidence": _r(e.psyche.confidence),
            "mood": e.mood, "under_review": e.under_review, "warnings": e.warnings, "streak": e.streak,
        })
    return rows


def build_ceo_context(world: World, scope: str) -> dict[str, Any]:
    ceo = world.ceo()
    f = world.finances
    runway = val.runway_months(world)
    reports = world.monthly_reports[-3:]
    dept_rows = []
    for d in world.active_departments():
        if d.kind == "lab":
            continue
        p30 = metrics.department_stats(world, d.id, 30)
        p90 = metrics.department_stats(world, d.id, 90)
        members = [e for e in world.department_members(d.id) if e.role == "tipster"]
        dept_rows.append({
            "id": d.id, "name": d.name, "kind": d.kind, "competitions": d.competitions,
            "preferred_specialties": DEPARTMENT_KINDS[d.kind].specialties if d.kind in DEPARTMENT_KINDS else [],
            "bankroll": _r(d.bankroll, 2),
            "stake_limit_pct": _r(d.stake_limit_pct, 4), "profit_30d": _r(p30.profit, 2),
            "bookmaker_limits": {b: bookmakers.limit(d, b) for b in EC.BOOK_LIMITS},
            "profit_90d": _r(p90.profit, 2), "roi_90d": _r(p90.roi), "bets_90d": p90.bets, "z_90d": _r(p90.z, 2),
            "headcount": len(members), "head": world.employees[d.head_id].name if d.head_id in world.employees else None,
            "age_days": (world.today - d.founded).days,
        })
    lab_dept = next((d for d in world.active_departments() if d.kind == "lab"), None)
    ready = [{
        "id": x.id, "name": x.name, "hypothesis": x.hypothesis,
        "sample": x.result.sample_size if x.result else 0, "roi": _r(x.result.roi if x.result else 0),
        "drawdown": _r(x.result.max_drawdown_pct if x.result else 0), "recommendation": x.recommendation,
        "holdout_roi": _r(x.holdout.roi) if x.holdout else None, "holdout_sample": x.holdout.sample_size if x.holdout else 0,
        "competitions": world.strategies[x.strategy_id].competitions if x.strategy_id in world.strategies else [],
        "markets": world.strategies[x.strategy_id].markets if x.strategy_id in world.strategies else [],
    } for x in world.experiments.values() if x.status == "completed"]
    audit = [{
        "id": a.id, "employee_id": a.employee_id, "employee": world.employees[a.employee_id].name,
        "text": a.text, "bets": a.bets, "roi": _r(a.roi), "field": a.suggestion.get("field"),
        "value": a.suggestion.get("value"),
    } for a in world.audit_findings if not a.resolved and a.employee_id in world.employees
        and world.employees[a.employee_id].active][-6:]
    p90 = metrics.company_stats(world, 90)
    active_kinds = {d.kind for d in world.active_departments()}
    desk_count = sum(1 for d in world.active_departments() if d.kind != "lab")
    burn = val.monthly_burn(world)
    return {
        "date": world.today.isoformat(),
        "scope": scope,
        "ceo": {"id": ceo.id, "name": ceo.name, "style": ceo.ceo_style,
                "style_label": CEO_STYLE_INFO[ceo.ceo_style or "data_driven"]["label"],
                "style_description": CEO_STYLE_INFO[ceo.ceo_style or "data_driven"]["description"],
                "traits_text": ceo.traits.describe(), "traits": ceo.traits.as_dict(),
                "confidence": _r(ceo.psyche.confidence), "stress": _r(ceo.psyche.stress)},
        "company": {
            "name": world.config.company_name, "status": f.status, "cash": _r(f.cash, 2),
            "bankroll": _r(metrics.bankroll_total(world), 2), "exposure": _r(metrics.exposure_total(world), 2),
            "debt": _r(f.debt, 2), "payables": _r(f.payables, 2), "valuation": _r(val.valuation(world), 2),
            "peak_value": _r(f.peak_value, 2), "drawdown": _r(val.drawdown(world)),
            "runway_months": None if runway is None else _r(runway, 1), "monthly_burn": _r(burn, 2),
            "monthly_costs": _r(val.estimated_operating_cost(world), 2),
            "months": [{"month": r.month, "betting": _r(r.lines.betting_pnl, 2), "expenses": _r(r.lines.expenses, 2),
                        "subscriptions": _r(r.lines.subscriptions, 2), "net": _r(r.lines.net, 2)} for r in reports],
            "month_to_date_net": _r(f.month.net, 2),
            "subscribers": f.subscribers, "marketing_budget": f.marketing_budget, "lab_budget": f.lab_budget,
            "hiring_frozen": f.hiring_frozen, "credit_available": _r(val.credit_available(world), 2),
            "starting_capital": world.config.starting_capital,
            "days_since_founding": world.clock.day_index,
            "roi_90d": _r(p90.roi), "bets_90d": p90.bets,
            "months_since_salary_cut": world.milestones.get("months_since_salary_cut", 99),
            "days_since_desk_closed": world.today.toordinal() - int(world.milestones.get("last_desk_closed", 0)),
            "days_since_swap": world.today.toordinal() - int(world.milestones.get("last_swap", 0)),
            "monthly_payroll": _r(sum(e.salary for e in world.active_employees()), 2),
        },
        "departments": dept_rows,
        "employees": employee_rows(world),
        "lab": {"department_id": lab_dept.id if lab_dept else None, "budget": f.lab_budget,
                "researchers": [e.name for e in world.active_employees("researcher")],
                "ready": ready, "audit": audit},
        "candidates": [{
            "id": c.id, "name": c.name, "role": c.role, "specialty": c.specialty,
            "specialty_label": SPECIALTIES[c.specialty].label, "cv_rating": c.cv_rating,
            "experience": c.experience_years, "salary_ask": c.salary_ask, "traits_text": c.traits.describe(),
            "pitch": c.pitch, "lab_backtest_roi": c.lab_backtest_roi, "lab_backtest_n": c.lab_backtest_n,
        } for c in world.candidates],
        "available_department_kinds": [{"kind": k, "name": v.name} for k, v in DEPARTMENT_KINDS.items()
                                       if k not in active_kinds and k != "lab"],
        "limits": {"max_fires": 2 if scope == "monthly" else 1, "max_hires": 2 if scope == "monthly" else 0,
                   "max_desks": market.desk_rooms(world), "desks": desk_count, "max_desk_size": MAX_DESK_SIZE,
                   "min_stake_pct": 0.005, "max_stake_pct": 0.08},
        "recent_events": [f"{e.time.date()}: {e.title}" for e in world.events[-12:] if e.importance >= 2],
        "office": office_context(world),
        "city": city_context(world),
    }


def office_context(world: World) -> dict[str, Any]:
    staff = [e for e in world.active_employees() if e.role != "ceo"]
    quits = sum(1 for e in world.employees.values() if e.left and (world.today - e.left).days <= 90
                and e.leave_reason and not e.leave_reason.startswith("fired"))
    mult = EC.preset(world.config.difficulty)["cost_mult"]
    return {
        "facilities": [{"key": k, "name": v["name"], "leased": market.leased(world, k),
                        "since": world.office.leased[k].isoformat() if market.leased(world, k) else None,
                        "fit_out": _r(float(v["fit_out"]) * mult, 0),  # type: ignore[arg-type]
                        "monthly_cost": _r(market.facility_monthly_cost(world, k), 0), "effect": v["effect"]}
                       for k, v in EC.FACILITIES.items()],
        "avg_staff_stress": _r(sum(e.psyche.stress for e in staff) / len(staff)) if staff else 0.0,
        "voluntary_departures_90d": quits,
    }


def city_context(world: World) -> dict[str, Any]:
    city = world.city
    return {
        "headlines": [p.headline + (f" ({p.effect})" if p.effect else "")
                      for p in market.recent_press(world, 3, 2)][-6:],
        "betting_sector_sentiment": _r(market.betting_sentiment(world), 3),
        "consumer_confidence": _r(city.economy, 2),
        "central_bank_rate_pct": city.base_rate,
        "credit_line_rate_monthly": _r(market.loan_rate_monthly(world), 4),
        "active_effects": [m["label"] + f" ({m['days_left']} days left)" for m in market.active_modifiers(world)],
    }


# ---------------------------------------------------------------------------------- LAB
def build_lab_context(world: World, researcher: Employee, history_matches: int) -> dict[str, Any]:
    live = []
    for s in world.strategies.values():
        users = [e for e in world.tipsters() if e.strategy_id == s.id]
        if not users:
            continue
        live.append({"id": s.id, "name": s.name, "summary": s.summary(), "owners": [u.name for u in users],
                     "bets": s.live_bets, "roi": _r(s.live_roi), "params": strategy_params(s)})
    past = [{"name": x.name, "hypothesis": x.hypothesis,
             "roi": _r(x.result.roi) if x.result else None, "sample": x.result.sample_size if x.result else 0,
             "recommendation": x.recommendation,
             "params": strategy_params(world.strategies[x.strategy_id]) if x.strategy_id in world.strategies else {}}
            for x in list(world.experiments.values())[-8:]]
    comps = sorted({c for d in world.active_departments() for c in d.competitions})
    return {
        "date": world.today.isoformat(),
        "researcher": {"id": researcher.id, "name": researcher.name, "specialty": researcher.specialty,
                       "specialty_label": SPECIALTIES[researcher.specialty].label,
                       "traits": researcher.traits.as_dict(), "traits_text": researcher.traits.describe(),
                       "stress": _r(researcher.psyche.stress)},
        "budget": world.finances.lab_budget,
        "history_matches": history_matches,
        "competitions_covered": comps,
        "live_strategies": sorted(live, key=lambda s: -s["bets"])[:8],
        "past_experiments": past,
        "audit_hints": [a.text for a in world.audit_findings[-5:]],
        "param_bounds": {k: list(v) for k, v in PARAM_BOUNDS.items()},
    }


def strategy_params(s) -> dict[str, Any]:
    return {
        "competitions": s.competitions, "markets": s.markets, "model_weight": _r(s.model_weight, 2),
        "window": s.window, "half_life": s.half_life, "shrinkage": s.shrinkage, "home_adv": s.home_adv,
        "news_weight": s.news_weight, "xg_weight": s.xg_weight, "opponent_adjust": s.opponent_adjust,
        "underdog_bias": s.underdog_bias, "fade_popular": s.fade_popular, "min_odds": s.min_odds,
        "max_odds": s.max_odds, "min_edge": s.min_edge, "kelly_fraction": s.kelly_fraction,
    }
