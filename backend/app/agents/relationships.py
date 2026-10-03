"""Relationship dynamics: trust from shared calls, respect from results, rivalry from competition."""

from __future__ import annotations

from app.domain.base import clamp
from app.domain.betting import Bet
from app.domain.people import Employee, Relationship
from app.domain.world import World


def _rel(a: Employee, b_id: str) -> Relationship:
    rel = a.relationships.get(b_id)
    if rel is None:
        rel = Relationship()
        a.relationships[b_id] = rel
    return rel


def on_influenced_bet(world: World, emp: Employee, bet: Bet) -> None:
    """Following a colleague's call builds or burns trust depending on the outcome."""
    won = bet.status == "won"
    for other_id in bet.influenced_by:
        rel = _rel(emp, other_id)
        gain = (3.0 + 3.0 * emp.traits.collaborative) if won else -(4.0 + 2.0 * emp.traits.skeptical)
        rel.trust = clamp(rel.trust + gain, 0, 100)


def monthly_update(world: World, perf_roi: dict[str, float], perf_bets: dict[str, int]) -> None:
    """Respect tracks observed performance; rivalry simmers inside departments and decays outside."""
    active = world.active_employees()
    for a in active:
        for b in active:
            if a.id == b.id:
                continue
            rel = _rel(a, b.id)
            if b.id in perf_roi and perf_bets.get(b.id, 0) >= 10:
                target = clamp(50 + perf_roi[b.id] * 400, 10, 95)
                rel.respect += 0.3 * (target - rel.respect)
            same_dept = a.department_id is not None and a.department_id == b.department_id
            if same_dept and a.role == b.role == "tipster":
                # desk-mates compete; being outperformed by the person next to you stings more
                outperformed = perf_roi.get(b.id, 0.0) > perf_roi.get(a.id, 0.0)
                rel.rivalry = clamp(rel.rivalry + 4.0 * a.traits.ambitious * (1.0 if outperformed else 0.35), 0, 100)
            rel.rivalry *= 0.93
            # trust drifts towards what people's results have earned (respect), damped by rivalry;
            # sitting at the same desk every day builds familiarity
            anchor = 50 + 0.6 * (rel.respect - 50) - 0.3 * rel.rivalry + (6 if same_dept else 0)
            rel.trust += 0.08 * (anchor - rel.trust)
            rel.trust = clamp(rel.trust, 0, 100)


def on_promotion(world: World, promoted: Employee) -> None:
    for e in world.active_employees():
        if e.id == promoted.id or e.department_id != promoted.department_id:
            continue
        rel = _rel(e, promoted.id)
        rel.rivalry = clamp(rel.rivalry + 10 + 12 * e.traits.ambitious, 0, 100)
        rel.respect = clamp(rel.respect + 3, 0, 100)


def on_departure(world: World, leaver: Employee, fired: bool) -> list[tuple[Employee, float]]:
    """Colleagues who trusted the leaver get shaken. Returns (employee, stress delta) pairs applied."""
    hit: list[tuple[Employee, float]] = []
    for e in world.active_employees():
        if e.id == leaver.id:
            continue
        rel = e.relationships.get(leaver.id)
        trust = rel.trust if rel else 50.0
        delta = (0.02 if fired else 0.01) + max(0.0, trust - 60) / 400
        if e.department_id == leaver.department_id:
            delta += 0.03 if fired else 0.015
        e.psyche.stress = clamp(e.psyche.stress + delta, 0.02, 0.98)
        hit.append((e, delta))
    return hit


def top_relationships(emp: Employee, world: World, n: int = 6) -> list[tuple[Employee, Relationship]]:
    rows = [(world.employees[oid], rel) for oid, rel in emp.relationships.items()
            if oid in world.employees and world.employees[oid].active]
    rows.sort(key=lambda r: -(abs(r[1].trust - 50) + r[1].rivalry * 0.5))
    return rows[:n]
