"""End-of-run (or any-time) statistics."""

from __future__ import annotations

from app.domain.world import RunSummary, World
from app.economy import valuation as val


def build_summary(world: World) -> RunSummary:
    ceo = next((e for e in world.employees.values() if e.role == "ceo" and e.active), None) or next(
        (e for e in reversed(list(world.employees.values())) if e.role == "ceo"), None)
    tipsters = [e for e in world.employees.values() if e.role == "tipster" and e.bets_total > 0]
    best = max(tipsters, key=lambda e: e.profit, default=None)
    worst = min(tipsters, key=lambda e: e.profit, default=None)
    f = world.finances
    return RunSummary(
        company_name=world.config.company_name,
        ceo_name=ceo.name if ceo else "?",
        ceo_style=ceo.ceo_style if ceo and ceo.ceo_style else world.config.ceo_style,
        ended=world.ended,
        end_reason=world.end_reason,
        founded=world.config.start_date,
        last_day=world.today,
        days_survived=world.clock.day_index,
        starting_capital=world.config.starting_capital,
        peak_value=round(f.peak_value, 2),
        peak_value_day=f.peak_value_day,
        final_value=round(max(0.0, val.valuation(world)) if world.ended else val.valuation(world), 2),
        worst_drawdown=round(f.max_drawdown, 4),
        employees_hired=world.stats.hired,
        employees_fired=world.stats.fired,
        employees_resigned=world.stats.resigned,
        bets_placed=world.stats.bets_placed,
        no_bet_decisions=world.stats.no_bets,
        betting_profit=round(f.totals.betting_pnl, 2),
        total_expenses=round(f.totals.expenses, 2),
        best_employee=best.name if best else None,
        best_employee_profit=round(best.profit, 2) if best else None,
        worst_employee=worst.name if worst else None,
        worst_employee_profit=round(worst.profit, 2) if worst else None,
        departments_created=world.stats.departments_created,
        departments_closed=world.stats.departments_closed,
        strategies_invented=world.stats.strategies_invented,
        ai_cost_usd=round(world.ai_stats.cost_usd, 4),
        ai_calls=world.ai_stats.calls,
        ceo_changes=world.stats.ceo_changes,
        seasons=len(world.recaps),
    )
