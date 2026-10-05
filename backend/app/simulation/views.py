"""Read models for the UI. Every number shown in the frontend comes from here."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.agents.catalog import CEO_STYLE_INFO, DEPARTMENT_KINDS, SPECIALTIES
from app.agents.context import allocation_for
from app.agents.relationships import top_relationships
from app.domain.betting import Bet
from app.domain.people import Employee
from app.domain.world import World
from app.economy import bookmakers
from app.economy import config as EC
from app.economy import market
from app.economy import valuation as val

from . import metrics
from .engine import PHASES
from .summary import build_summary


def _r(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(float(x), n)


def _downsample(rows: list, limit: int) -> list:
    if len(rows) <= limit:
        return rows
    step = len(rows) / limit
    out = [rows[int(i * step)] for i in range(limit)]
    if out[-1] is not rows[-1]:
        out.append(rows[-1])
    return out


def bet_view(world: World, b: Bet) -> dict[str, Any]:
    emp = world.employees.get(b.employee_id)
    return {
        "id": b.id, "placed": b.placed.isoformat(), "employee_id": b.employee_id,
        "employee": emp.name if emp else "?", "department_id": b.department_id, "match_id": b.match_id,
        "match": b.match_label, "competition": b.competition, "market": b.market, "selection": b.selection,
        "book": b.book, "odds": b.odds, "stake": b.stake, "status": b.status, "profit": _r(b.profit),
        "confidence": b.confidence, "model_prob": b.model_prob, "model_edge": b.model_edge,
        "closing_odds": b.closing_odds, "clv": _r(b.clv, 4), "score": b.score, "reason": b.reason,
        "influenced_by": [world.employees[i].name for i in b.influenced_by if i in world.employees],
    }


def employee_card(world: World, e: Employee) -> dict[str, Any]:
    return {
        "id": e.id, "name": e.name, "role": e.role, "title": e.title, "level": e.level,
        "specialty": e.specialty, "specialty_label": SPECIALTIES[e.specialty].label if e.specialty in SPECIALTIES else
        ("CEO — " + CEO_STYLE_INFO[e.ceo_style]["label"] if e.ceo_style else e.specialty),
        "department_id": e.department_id, "desk_index": e.desk_index, "active": e.active,
        "status": e.status, "task": e.task, "thought": e.thought, "mood": e.mood,
        "stress": _r(e.psyche.stress, 3), "confidence": _r(e.psyche.confidence, 3),
        "reputation": _r(e.psyche.reputation, 1), "risk_tolerance": _r(e.psyche.risk_tolerance, 3),
        "day_profit": _r(e.day_profit), "month_profit": _r(e.month_profit), "profit": _r(e.profit),
        "roi": _r(e.roi, 4), "bets": e.bets_total, "streak": e.streak, "under_review": e.under_review,
        "appearance": e.appearance.model_dump(), "pnl_flash_seq": e.pnl_flash_seq,
        "tenure_days": e.tenure_days(world.today), "left": e.left.isoformat() if e.left else None,
    }


def state_view(world: World, runner: dict[str, Any] | None = None, providers: dict[str, str] | None = None) -> dict[str, Any]:
    f = world.finances
    phase_idx = world.clock.phase_index
    last_phase = PHASES[(phase_idx - 1) % len(PHASES)][0]
    runway = val.runway_months(world)
    tipsters = world.tipsters()
    working = sum(1 for e in tipsters if e.status in ("analyzing", "working", "watching", "celebrating", "frustrated"))
    reports = world.monthly_reports
    total_net = sum(r.lines.net for r in reports) + f.month.net
    yesterday = world.today - timedelta(days=1)
    visible = [e for e in world.employees.values()
               if e.active or (e.left is not None and e.left >= yesterday)]
    today_matches = [m for m in world.matches.values() if m.kickoff.date() == world.today]
    ceo = next((e for e in world.employees.values() if e.role == "ceo"), None)
    return {
        "run": {
            "id": world.run_id, "company_name": world.config.company_name, "ceo_style": world.config.ceo_style,
            "ceo_style_label": CEO_STYLE_INFO[world.config.ceo_style]["label"], "seed": world.config.seed,
            "starting_capital": world.config.starting_capital, "ended": world.ended, "end_reason": world.end_reason,
            "ai_provider": (providers or {}).get("ai", world.config.ai_provider),
            "sports_provider": (providers or {}).get("sports", world.config.sports_provider),
            "founded": world.config.start_date.isoformat(),
        },
        "clock": {
            "now": world.clock.now.isoformat(), "date": world.today.isoformat(),
            "weekday": world.today.strftime("%A"), "time": world.clock.now.strftime("%H:%M"),
            "phase": last_phase, "next_phase": PHASES[phase_idx][0], "day_index": world.clock.day_index,
        },
        "runner": runner or {"running": False, "speed": "4x"},
        "kpis": {
            "cash": _r(f.cash), "bankroll": _r(metrics.bankroll_total(world)), "exposure": _r(metrics.exposure_total(world)),
            "debt": _r(f.debt), "payables": _r(f.payables), "equity": _r(val.equity(world)),
            "valuation": _r(val.valuation(world)), "peak_value": _r(f.peak_value), "drawdown": _r(val.drawdown(world), 4),
            "max_drawdown": _r(f.max_drawdown, 4), "runway_months": _r(runway, 1), "monthly_burn": _r(val.monthly_burn(world)),
            "monthly_costs": _r(val.estimated_operating_cost(world)), "status": f.status,
            "day_pnl": _r(sum(d.day_profit for d in world.departments.values())),
            "month_betting_pnl": _r(f.month.betting_pnl), "month_net": _r(f.month.net),
            "month_expenses": _r(f.month.expenses), "total_betting_pnl": _r(f.totals.betting_pnl),
            "total_net": _r(total_net), "tipsters": len(tipsters), "tipsters_working": working,
            "employees": len(world.active_employees()), "bets_total": world.stats.bets_placed,
            "bets_open": len(world.open_bet_ids), "no_bets": world.stats.no_bets,
            "ai_cost_usd": _r(world.ai_stats.cost_usd, 4), "ai_calls": world.ai_stats.calls,
            "ai_failures": world.ai_stats.failures, "ai_cost_month_eur": _r(f.month.ai),
            "subscribers": f.subscribers, "marketing_budget": _r(f.marketing_budget), "lab_budget": _r(f.lab_budget),
            "hiring_frozen": f.hiring_frozen,
        },
        "departments": [{
            "id": d.id, "name": d.name, "kind": d.kind, "color": DEPARTMENT_KINDS[d.kind].color if d.kind in DEPARTMENT_KINDS else "#888",
            "room_slot": d.room_slot, "bankroll": _r(d.bankroll), "stake_limit_pct": _r(d.stake_limit_pct, 4),
            "month_profit": _r(d.month_profit), "day_profit": _r(d.day_profit), "total_profit": _r(d.total_profit),
            "bets": d.bets, "competitions": d.competitions, "head_id": d.head_id, "active": d.active,
            "headcount": len(world.department_members(d.id)),
            "book_limits": {b: bookmakers.limit(d, b) for b in EC.BOOK_LIMITS},
        } for d in world.departments.values() if d.active],
        "employees": [employee_card(world, e) for e in visible],
        "events": [e.model_dump(mode="json") for e in world.events[-40:]],
        "ticker": [bet_view(world, world.bets[bid]) for bid in list(world.bets)[-25:]],
        "memo": world.memos[-1].model_dump(mode="json") if world.memos else None,
        "ceo_thought": ceo.thought if ceo else "",
        "lab": {
            "budget": f.lab_budget,
            "running": [{"id": x.id, "name": x.name, "researcher_id": x.researcher_id, "due": x.due.isoformat()}
                        for x in world.experiments.values() if x.status == "running"],
            "ready": sum(1 for x in world.experiments.values() if x.status == "completed"),
        },
        "today": {"matches": len(today_matches), "live": sum(1 for m in today_matches if m.status == "live"),
                  "finished": sum(1 for m in today_matches if m.status == "finished")},
        "summary": world.summary.model_dump(mode="json") if world.summary else None,
        "latest_recap": ({"id": world.recaps[-1].id, "season": world.recaps[-1].season}
                         if world.recaps else None),
        "office": office_view(world),
        "city": city_brief(world),
        "sandbox": {"god_actions": world.stats.god_actions},
    }


def office_view(world: World) -> dict[str, Any]:
    mult = EC.preset(world.config.difficulty)["cost_mult"]
    return {
        "leased": {k: d.isoformat() for k, d in world.office.leased.items()},
        "desk_rooms": market.desk_rooms(world),
        "facilities": [{"key": k, "name": v["name"], "effect": v["effect"], "leased": market.leased(world, k),
                        "since": world.office.leased[k].isoformat() if market.leased(world, k) else None,
                        "fit_out": round(float(v["fit_out"]) * mult, 0),  # type: ignore[arg-type]
                        "monthly_cost": round(market.facility_monthly_cost(world, k), 0)}
                       for k, v in EC.FACILITIES.items()],
    }


def city_brief(world: World) -> dict[str, Any]:
    city = world.city
    latest = city.editions[-1] if city.editions else None
    lead = next((p for p in reversed(city.press) if p.day == latest and p.lead), None) if latest else None
    idx = city.index
    return {
        "paper": city.paper, "name": city.name, "edition": latest.isoformat() if latest else None,
        "headline": lead.headline if lead else None,
        "index": idx[-1] if idx else None,
        "index_change": round(idx[-1] / idx[-2] - 1, 4) if len(idx) >= 2 else None,
        "betting_sentiment": round(market.betting_sentiment(world), 3),
        "modifiers": market.active_modifiers(world),
    }


def employee_detail(world: World, emp_id: str, ai_calls: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    e = world.employees.get(emp_id)
    if e is None:
        return None
    strat = world.strategies.get(e.strategy_id or "")
    bets = [world.bets[b] for b in e.bet_ids[-120:] if b in world.bets]
    recent = metrics.recent_stats(world, e, 30)
    p90 = metrics.period_stats(world, e, 90)
    allocation, max_stake = allocation_for(world, e) if e.role == "tipster" and e.active else (0.0, 0.0)
    rels = []
    for other, rel in top_relationships(e, world, n=12):
        rels.append({"id": other.id, "name": other.name, "title": other.title, "trust": _r(rel.trust, 0),
                     "respect": _r(rel.respect, 0), "rivalry": _r(rel.rivalry, 0)})
    dept = world.departments.get(e.department_id or "")
    by_market: dict[str, dict[str, float]] = {}
    for b in bets:
        if b.status == "open":
            continue
        row = by_market.setdefault(b.market, {"bets": 0, "staked": 0.0, "profit": 0.0})
        row["bets"] += 1
        row["staked"] += b.stake
        row["profit"] += b.profit
    return {
        **employee_card(world, e),
        "department": dept.name if dept else None,
        "hired": e.hired.isoformat(), "leave_reason": e.leave_reason, "salary": e.salary,
        "traits": e.traits.as_dict(), "traits_text": e.traits.describe(),
        "warnings": e.warnings, "promotions": e.promotions, "bonuses": _r(e.bonuses_earned),
        "allocation": _r(allocation), "max_stake": _r(max_stake),
        "stats": {
            "bets": e.bets_total, "wins": e.wins, "losses": e.losses, "staked": _r(e.staked), "profit": _r(e.profit),
            "roi": _r(e.roi, 4), "best_streak": e.best_streak, "worst_streak": e.worst_streak,
            "no_bet_rate": _r(e.no_bet_rate(), 3),
            "recent30": recent.model_dump(), "last90": p90.model_dump(),
            "by_market": {k: {"bets": v["bets"], "roi": _r(v["profit"] / v["staked"], 4) if v["staked"] else 0.0}
                          for k, v in by_market.items()},
        },
        "strategy": None if strat is None else {
            "id": strat.id, "name": strat.name, "origin": strat.origin, "summary": strat.summary(),
            "live_bets": strat.live_bets, "live_roi": _r(strat.live_roi, 4),
            "backtest": strat.backtest.model_dump(mode="json") if strat.backtest else None,
            "params": {k: getattr(strat, k) for k in ("competitions", "markets", "model_weight", "window", "half_life",
                                                      "xg_weight", "news_weight", "min_edge", "min_odds", "max_odds",
                                                      "kelly_fraction", "fade_popular", "underdog_bias")},
        },
        "series": _downsample(e.series, 300),
        "relationships": rels,
        "career": [c.model_dump(mode="json") for c in e.career[-60:]],
        "decisions": [d.model_dump(mode="json") for d in e.decisions[-60:]][::-1],
        "bets_list": [bet_view(world, b) for b in bets][::-1],
        "ai_calls": ai_calls or [],
    }


def department_detail(world: World, dept_id: str) -> dict[str, Any] | None:
    d = world.departments.get(dept_id)
    if d is None:
        return None
    p30 = metrics.department_stats(world, d.id, 30)
    p90 = metrics.department_stats(world, d.id, 90)
    return {
        "id": d.id, "name": d.name, "kind": d.kind, "active": d.active, "founded": d.founded.isoformat(),
        "closed": d.closed.isoformat() if d.closed else None, "competitions": d.competitions,
        "bankroll": _r(d.bankroll), "stake_limit_pct": d.stake_limit_pct, "total_profit": _r(d.total_profit),
        "total_staked": _r(d.total_staked), "bets": d.bets, "month_profit": _r(d.month_profit),
        "profit_by_month": d.profit_by_month, "last30": p30.model_dump(), "last90": p90.model_dump(),
        "members": [employee_card(world, e) for e in world.department_members(d.id)],
        "head": world.employees[d.head_id].name if d.head_id in world.employees else None,
        "book_limits": [{"book": b, "limit": bookmakers.limit(d, b), "default": v,
                         "bets": sum(1 for x in world.bets.values() if x.department_id == d.id and x.book == b)}
                        for b, v in EC.BOOK_LIMITS.items()],
    }


def finance_view(world: World) -> dict[str, Any]:
    f = world.finances
    return {
        "month_to_date": {**f.month.model_dump(), "expenses": _r(f.month.expenses), "net": _r(f.month.net)},
        "totals": {**f.totals.model_dump(), "expenses": _r(f.totals.expenses), "net": _r(f.totals.net)},
        "reports": [{**r.model_dump(mode="json"), "net": _r(r.lines.net), "expenses": _r(r.lines.expenses)}
                    for r in world.monthly_reports],
        "daily": [p.model_dump(mode="json") for p in _downsample(world.daily, 500)],
        "departments": [{"id": d.id, "name": d.name, "active": d.active, "total_profit": _r(d.total_profit),
                         "bets": d.bets, "roi": _r(d.total_profit / d.total_staked, 4) if d.total_staked else 0.0,
                         "profit_by_month": d.profit_by_month} for d in world.departments.values() if d.kind != "lab"],
        "subscribers": f.subscribers, "subscription_price": f.subscription_price,
        "credit_available": _r(val.credit_available(world)),
    }


def lab_view(world: World) -> dict[str, Any]:
    exps = sorted(world.experiments.values(), key=lambda x: x.started, reverse=True)
    users: dict[str, list[str]] = {}
    for e in world.tipsters():
        if e.strategy_id:
            users.setdefault(e.strategy_id, []).append(e.name)
    return {
        "budget": world.finances.lab_budget,
        "researchers": [employee_card(world, e) for e in world.active_employees("researcher")],
        "experiments": [{
            **x.model_dump(mode="json"),
            "researcher": world.employees[x.researcher_id].name if x.researcher_id in world.employees else "?",
            "deployed_names": [world.employees[i].name for i in x.deployed_to if i in world.employees],
            "strategy_summary": world.strategies[x.strategy_id].summary() if x.strategy_id in world.strategies else "",
        } for x in exps[:120]],
        "audit": [a.model_dump(mode="json") | {"employee": world.employees[a.employee_id].name
                                                 if a.employee_id in world.employees else "?"}
                  for a in world.audit_findings[::-1][:40]],
        "strategies": [{
            "id": s.id, "name": s.name, "origin": s.origin, "summary": s.summary(), "live_bets": s.live_bets,
            "live_roi": _r(s.live_roi, 4), "users": users.get(s.id, []), "retired": s.retired,
            "backtest_roi": _r(s.backtest.roi, 4) if s.backtest else None,
            "backtest_n": s.backtest.sample_size if s.backtest else None,
        } for s in world.strategies.values() if s.id in users or (s.live_bets > 0)],
    }


def history_view(world: World, min_importance: int = 1, limit: int = 600) -> list[dict[str, Any]]:
    rows = [e for e in world.events if e.importance >= min_importance]
    return [e.model_dump(mode="json") for e in rows[-limit:]][::-1]


def management_view(world: World) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in world.management_log[::-1][:60]]


def recaps_view(world: World) -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in reversed(world.recaps)]


def summary_view(world: World) -> dict[str, Any]:
    return (world.summary or build_summary(world)).model_dump(mode="json")
