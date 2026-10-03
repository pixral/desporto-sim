from __future__ import annotations

import random

from app.ai.schemas import CEOAction
from app.agents import management


def _apply(world, *actions, scope="monthly"):
    return management.apply_actions(world, random.Random(1), list(actions), scope)


def test_unknown_ids_are_rejected_not_crashing(fresh):
    world, _, _ = fresh()
    recs = _apply(world, CEOAction(type="FIRE", employee_id="nobody"),
                  CEOAction(type="HIRE", candidate_id="c999", department_id="d1"),
                  CEOAction(type="CLOSE_DEPARTMENT", department_id="dx"))
    assert [r.applied for r in recs] == [False, False, False]
    assert all(r.result for r in recs)


def test_fire_pays_severance_and_records_history(fresh):
    world, _, _ = fresh()
    emp = world.tipsters()[0]
    cash = world.finances.cash
    (rec,) = _apply(world, CEOAction(type="FIRE", employee_id=emp.id, reason="results"))
    assert rec.applied and not emp.active and emp.left == world.today
    assert world.finances.cash == cash - emp.salary
    assert world.stats.fired == 1
    assert world.events[-1].kind == "fire"


def test_firing_limit_per_review(fresh):
    world, _, _ = fresh()
    ids = [e.id for e in world.tipsters()[:3]]
    recs = _apply(world, *[CEOAction(type="FIRE", employee_id=i) for i in ids], scope="weekly")
    assert [r.applied for r in recs] == [True, False, False]


def test_hiring_freeze_blocks_hires(fresh):
    world, _, _ = fresh()
    world.finances.hiring_frozen = True
    cand = next(c for c in world.candidates if c.role == "tipster")
    desk = next(d for d in world.active_departments() if d.kind != "lab")
    (rec,) = _apply(world, CEOAction(type="HIRE", candidate_id=cand.id, department_id=desk.id))
    assert not rec.applied and "frozen" in rec.result


def test_hire_adds_employee_with_relationships(fresh):
    world, _, _ = fresh()
    cand = next(c for c in world.candidates if c.role == "tipster")
    desk = next(d for d in world.active_departments() if d.kind == "markets")
    before = len(world.tipsters())
    (rec,) = _apply(world, CEOAction(type="HIRE", candidate_id=cand.id, department_id=desk.id))
    assert rec.applied, rec.result
    assert len(world.tipsters()) == before + 1
    new = next(e for e in world.tipsters() if e.name == cand.name)
    assert new.relationships and new.strategy_id in world.strategies
    assert cand.id not in {c.id for c in world.candidates}


def test_promotion_and_department_lifecycle(fresh):
    world, _, _ = fresh()
    emp = min(world.tipsters(), key=lambda e: e.level)
    level, salary = emp.level, emp.salary
    (rec,) = _apply(world, CEOAction(type="PROMOTE", employee_id=emp.id))
    assert rec.applied and emp.level == level + 1 and emp.salary > salary
    cash = world.finances.cash
    (rec,) = _apply(world, CEOAction(type="CREATE_DEPARTMENT", department_kind="goals", amount=1000))
    assert rec.applied
    goals = next(d for d in world.active_departments() if d.kind == "goals")
    assert world.finances.cash == cash - 1000 and goals.bankroll == 1000
    (rec,) = _apply(world, CEOAction(type="CLOSE_DEPARTMENT", department_id=goals.id))
    assert rec.applied and not goals.active and world.finances.cash == cash


def test_salary_cut_raises_stress(fresh):
    world, _, _ = fresh()
    emp = world.tipsters()[0]
    salary, stress = emp.salary, emp.psyche.stress
    (rec,) = _apply(world, CEOAction(type="CUT_SALARIES", pct=0.1))
    assert rec.applied and abs(emp.salary - salary * 0.9) < 0.01 and emp.psyche.stress > stress
