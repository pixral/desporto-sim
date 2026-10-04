"""Validate and apply CEO decisions. The CEO proposes; this module enforces reality.

Invalid actions (unknown ids, frozen hiring, no cash, full desks...) are rejected with a reason
and logged, never silently fixed.
"""

from __future__ import annotations

import random

from app.domain.base import clamp
from app.domain.company import Department
from app.domain.events import ActionRecord
from app.domain.people import Employee
from app.domain.strategy import PARAM_BOUNDS
from app.domain.world import World
from app.economy import accounting
from app.economy import config as EC
from app.economy import market
from app.simulation import history

from . import relationships
from .catalog import (
    DEPARTMENT_KINDS,
    LEVEL_BANKROLL_WEIGHT,
    LEVEL_SALARY,
    MAX_DESK_SIZE,
    TIPSTER_TITLES,
)
from .hiring import hire_candidate, pay, seed_relationships


MIN_STRATEGY_DAYS = 60  # a strategy needs time before it can be judged (and replaced)


# ------------------------------------------------------------------ shared helpers
def free_desk_index(world: World, dept_id: str) -> int | None:
    used = {e.desk_index for e in world.department_members(dept_id)}
    for i in range(MAX_DESK_SIZE):
        if i not in used:
            return i
    return None


def free_room_slot(world: World) -> int | None:
    """Slots 0-5 are the original floor; slot 6 exists once the east desk wing is leased."""
    used = {d.room_slot for d in world.active_departments() if d.kind != "lab"}
    for i in range(market.desk_rooms(world)):
        if i not in used:
            return i
    return None


def lease_facility(world: World, key: str, free: bool = False) -> tuple[bool, str]:
    """Sign a lease in the east wing and pay the fit-out. `free` is for the sandbox tools."""
    if key not in EC.FACILITIES:
        return False, "unknown facility"
    if market.leased(world, key):
        return False, "already leased"
    spec = EC.FACILITIES[key]
    fit_out = 0.0 if free else float(spec["fit_out"]) * EC.preset(world.config.difficulty)["cost_mult"]  # type: ignore[arg-type]
    if not free and world.finances.cash < fit_out + 100:
        return False, f"not enough cash for the €{fit_out:,.0f} fit-out"
    f = world.finances
    f.cash -= fit_out
    f.month.other_costs += fit_out
    f.totals.other_costs += fit_out
    world.office.leased[key] = world.today
    world.stats.facilities_leased += 1
    rent = market.facility_monthly_cost(world, key)
    history.record(world, "facility_leased", f"{spec['name']} opens", f"{spec['effect']} Fit-out €{fit_out:,.0f}, "
                   f"running cost about €{rent:,.0f}/month.", 3, "good", data={"facility": key})
    return True, f"{spec['name']} leased (fit-out €{fit_out:,.0f}, ~€{rent:,.0f}/month)"


def release_facility(world: World, key: str, free: bool = False) -> tuple[bool, str]:
    if not market.leased(world, key):
        return False, "not leased"
    if key == "desk_wing" and any(d.room_slot == 6 and d.kind != "lab" for d in world.active_departments()):
        return False, "a desk still works in the east wing; close or move it first"
    spec = EC.FACILITIES[key]
    fee = 0.0 if free else EC.LEASE_BREAK_MONTHS * market.facility_monthly_cost(world, key)
    f = world.finances
    f.cash -= fee
    f.month.other_costs += fee
    f.totals.other_costs += fee
    del world.office.leased[key]
    history.record(world, "facility_released", f"{spec['name']} closes", f"Lease given up (break fee €{fee:,.0f}).",
                   2, "bad", data={"facility": key})
    return True, f"{spec['name']} given up (fee €{fee:,.0f})"


def depart(world: World, emp: Employee, reason: str, fired: bool, severance: bool = True) -> None:
    """Remove an employee (fired, resigned, laid off). Keeps them in the world for history."""
    emp.active = False
    emp.left = world.today
    emp.leave_reason = reason
    emp.status = "leaving"
    emp.task = "Packing up their desk"
    emp.under_review = False
    if severance and fired:
        accounting.pay_severance(world, emp)
    emp.add_career(world.today, "left", reason[0].upper() + reason[1:] + ".")
    for d in world.departments.values():
        if d.head_id == emp.id:
            d.head_id = None
    if fired:
        world.stats.fired += 1
    else:
        world.stats.resigned += 1
    relationships.on_departure(world, emp, fired)


def create_department(world: World, kind: str, bankroll: float) -> Department:
    dk = DEPARTMENT_KINDS[kind]
    slot = 99 if kind == "lab" else (free_room_slot(world) or 0)
    dept = Department(id=world.next_id("d"), name=dk.name, kind=kind, competitions=list(dk.competitions),
                      bankroll=bankroll, stake_limit_pct=EC.DEFAULT_STAKE_LIMIT, founded=world.today, room_slot=slot)
    world.departments[dept.id] = dept
    return dept


def add_employee(world: World, rng: random.Random, emp: Employee) -> None:
    if emp.department_id:
        emp.desk_index = free_desk_index(world, emp.department_id) or 0
    world.employees[emp.id] = emp
    seed_relationships(world, rng, emp)
    emp.status = "arriving"
    emp.task = "First day: finding the coffee machine"


# ------------------------------------------------------------------ action application
class _Ctx:
    def __init__(self, world: World, rng: random.Random, scope: str) -> None:
        self.world = world
        self.rng = rng
        self.scope = scope
        self.fires = 0
        self.hires = 0
        self.max_fires = 2 if scope == "monthly" else 1
        self.max_hires = 2 if scope == "monthly" else 0
        self.touched: set[str] = set()


def apply_actions(world: World, rng: random.Random, actions: list, scope: str) -> list[ActionRecord]:
    ctx = _Ctx(world, rng, scope)
    out: list[ActionRecord] = []
    for action in actions:
        params = {k: v for k, v in action.model_dump().items() if k not in ("type", "reason") and v is not None}
        handler = _HANDLERS.get(action.type)
        if handler is None:
            out.append(ActionRecord(type=action.type, params=params, reason=action.reason, applied=False,
                                    result="unknown action"))
            continue
        try:
            ok, result = handler(ctx, action)
        except Exception as exc:  # defensive: a bad action must never crash the simulation
            ok, result = False, f"error: {exc}"
        out.append(ActionRecord(type=action.type, params=params, reason=action.reason, applied=ok, result=result))
    return out


def _emp(ctx: _Ctx, emp_id: str | None, roles: tuple[str, ...] = ("tipster", "researcher")) -> Employee | None:
    e = ctx.world.employees.get(emp_id or "")
    if e is None or not e.active or e.role not in roles:
        return None
    return e


def _dept(ctx: _Ctx, dept_id: str | None) -> Department | None:
    d = ctx.world.departments.get(dept_id or "")
    return d if d is not None and d.active else None


def _fire(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    if ctx.fires >= ctx.max_fires:
        return False, "firing limit for this review reached"
    e = _emp(ctx, a.employee_id)
    if e is None:
        return False, "no such active employee"
    reason = a.reason or "performance"
    depart(w, e, f"fired: {reason}", fired=True)
    if reason.startswith("Replaced by"):
        w.milestones["last_swap"] = w.today.toordinal()
    ctx.fires += 1
    ctx.touched.add(e.id)
    big = e.level >= 2 or e.profit > 150
    history.record(w, "fire", f"{e.name} fired", f"{e.title}, {e.tenure_days(w.today)} days. CEO: \"{reason}\"",
                   3 if big else 2, "bad", [e.id], e.department_id)
    return True, f"{e.name} fired (severance €{e.salary * EC.SEVERANCE_MONTHS:.0f})"


def _hire(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    if ctx.hires >= ctx.max_hires:
        return False, "hiring limit for this review reached"
    if w.finances.hiring_frozen:
        return False, "hiring is frozen"
    cand = next((c for c in w.candidates if c.id == a.candidate_id), None)
    if cand is None:
        return False, "no such candidate"
    dept = _dept(ctx, a.department_id)
    if dept is None:
        return False, "no such active department"
    if (cand.role == "researcher") != (dept.kind == "lab"):
        return False, "researchers go to the LAB, tipsters to betting desks"
    if free_desk_index(w, dept.id) is None:
        return False, "desk is full"
    if w.finances.cash < cand.salary_ask * 2:
        return False, "not enough cash to take on salary"
    emp = hire_candidate(w, ctx.rng, cand, dept.id)
    add_employee(w, ctx.rng, emp)
    w.candidates = [c for c in w.candidates if c.id != cand.id]
    ctx.hires += 1
    ctx.touched.add(emp.id)
    w.stats.hired += 1
    history.record(w, "hire", f"{emp.name} hired", f"{emp.title}, {dept.name}. {cand.pitch}",
                   3 if cand.cv_rating >= 80 else 2, "good", [emp.id], dept.id)
    return True, f"{emp.name} joins {dept.name} at €{emp.salary:.0f}/month"


def _promote(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    e = _emp(ctx, a.employee_id, ("tipster",))
    if e is None:
        return False, "no such active tipster"
    if e.level >= 3:
        return False, "already at the top level"
    dept = w.departments.get(e.department_id or "")
    if e.level == 2 and dept and dept.head_id and dept.head_id != e.id:
        return False, "the desk already has a head"
    e.level += 1
    e.title = TIPSTER_TITLES[e.level]
    e.salary = round(max(e.salary * 1.2, pay(w, LEVEL_SALARY[e.level])), 0)
    e.bankroll_weight = LEVEL_BANKROLL_WEIGHT[e.level]
    e.promotions += 1
    e.psyche.reputation = clamp(e.psyche.reputation + 5, 0, 100)
    e.psyche.confidence = clamp(e.psyche.confidence + 0.1, 0.05, 0.95)
    e.psyche.stress = clamp(e.psyche.stress - 0.1, 0.02, 0.98)
    if e.level == 3 and dept:
        dept.head_id = e.id
    e.add_career(w.today, "promoted", f"Promoted to {e.title}.")
    relationships.on_promotion(w, e)
    w.stats.promotions += 1
    ctx.touched.add(e.id)
    history.record(w, "promotion", f"{e.name} promoted to {e.title}", a.reason, 2, "good", [e.id], e.department_id)
    return True, f"{e.name} is now {e.title} (€{e.salary:.0f}/month)"


def _warn(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    e = _emp(ctx, a.employee_id)
    if e is None:
        return False, "no such active employee"
    e.under_review = True
    e.warnings += 1
    e.psyche.stress = clamp(e.psyche.stress + 0.12, 0.02, 0.98)
    e.add_career(w.today, "warning", f"Formal warning from the CEO: {a.reason}")
    ctx.touched.add(e.id)
    history.record(w, "warning", f"{e.name} placed under review", a.reason, 1, "drama", [e.id], e.department_id)
    return True, f"{e.name} warned"


def _clear(ctx: _Ctx, a) -> tuple[bool, str]:
    e = _emp(ctx, a.employee_id)
    if e is None or not e.under_review:
        return False, "employee is not under review"
    e.under_review = False
    e.psyche.stress = clamp(e.psyche.stress - 0.08, 0.02, 0.98)
    e.add_career(ctx.world.today, "review_cleared", "Review lifted.")
    return True, f"{e.name} cleared"


def _transfer(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    e = _emp(ctx, a.employee_id)
    dept = _dept(ctx, a.department_id)
    if e is None or dept is None:
        return False, "unknown employee or department"
    if (e.role == "researcher") != (dept.kind == "lab"):
        return False, "role does not fit that department"
    idx = free_desk_index(w, dept.id)
    if idx is None:
        return False, "desk is full"
    for d in w.departments.values():
        if d.head_id == e.id:
            d.head_id = None
    e.department_id = dept.id
    e.desk_index = idx
    e.add_career(w.today, "transfer", f"Transferred to {dept.name}.")
    history.record(w, "transfer", f"{e.name} moves to the {dept.name}", a.reason, 1, "neutral", [e.id], dept.id)
    return True, f"{e.name} → {dept.name}"


def _stake_limit(ctx: _Ctx, a) -> tuple[bool, str]:
    dept = _dept(ctx, a.department_id)
    if dept is None or dept.kind == "lab" or a.pct is None:
        return False, "unknown desk or missing pct"
    old = dept.stake_limit_pct
    dept.stake_limit_pct = clamp(a.pct, 0.005, 0.10)
    if dept.stake_limit_pct > old * 1.25 and dept.stake_limit_pct >= 0.05:
        history.record(ctx.world, "limits", f"{dept.name} limits raised to {dept.stake_limit_pct:.1%}", a.reason, 2,
                       "drama", department_id=dept.id)
    return True, f"{dept.name} max stake {old:.1%} → {dept.stake_limit_pct:.1%}"


def _fund(ctx: _Ctx, a) -> tuple[bool, str]:
    dept = _dept(ctx, a.department_id)
    if dept is None or dept.kind == "lab" or not a.amount or a.amount <= 0:
        return False, "unknown desk or bad amount"
    moved = accounting.transfer_to_department(ctx.world, dept, min(a.amount, max(0.0, ctx.world.finances.cash - 100)))
    if moved <= 0:
        return False, "not enough cash"
    return True, f"€{moved:,.0f} → {dept.name} bankroll"


def _withdraw(ctx: _Ctx, a) -> tuple[bool, str]:
    dept = _dept(ctx, a.department_id)
    if dept is None or not a.amount or a.amount <= 0:
        return False, "unknown desk or bad amount"
    moved = accounting.withdraw_from_department(ctx.world, dept, a.amount)
    if moved <= 0:
        return False, "desk has no bankroll"
    return True, f"€{moved:,.0f} withdrawn from {dept.name}"


def _create_dept(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    kind = a.department_kind or ""
    if kind not in DEPARTMENT_KINDS or kind == "lab":
        return False, "unknown department kind"
    if any(d.kind == kind for d in w.active_departments()):
        return False, "that desk already exists"
    if free_room_slot(w) is None:
        return False, "no office space left"
    amount = max(0.0, min(a.amount or 0.0, w.finances.cash - 100))
    if amount < 300:
        return False, "not enough cash to fund a new desk"
    w.finances.cash -= amount
    dept = create_department(w, kind, amount)
    w.stats.departments_created += 1
    history.record(w, "department_founded", f"{dept.name} founded", f"Seeded with €{amount:,.0f}. {a.reason}", 3,
                   "good", department_id=dept.id)
    return True, f"{dept.name} opened with €{amount:,.0f}"


def _close_dept(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    dept = _dept(ctx, a.department_id)
    if dept is None or dept.kind == "lab":
        return False, "unknown desk"
    members = w.department_members(dept.id)
    dept.active = False
    dept.closed = w.today
    returned = dept.bankroll
    w.finances.cash += returned
    dept.bankroll = 0.0
    moved, laid_off = [], []
    for e in members:
        target = next((d for d in w.active_departments() if d.kind != "lab"
                       and e.specialty in DEPARTMENT_KINDS[d.kind].specialties and free_desk_index(w, d.id) is not None),
                      None)
        if target is not None and ctx.rng.random() < 0.5:
            e.department_id = target.id
            e.desk_index = free_desk_index(w, target.id) or 0
            e.add_career(w.today, "transfer", f"Moved to {target.name} after the {dept.name} closed.")
            moved.append(e.name)
        else:
            depart(w, e, f"fired: laid off when the {dept.name} closed", fired=True)
            laid_off.append(e.name)
    w.stats.departments_closed += 1
    w.milestones["last_desk_closed"] = w.today.toordinal()
    text = f"€{returned:,.0f} returned to cash."
    if laid_off:
        text += f" Laid off: {', '.join(laid_off)}."
    if moved:
        text += f" Reassigned: {', '.join(moved)}."
    history.record(w, "department_closed", f"{dept.name} closed", text, 3, "bad",
                   [e.id for e in members], dept.id)
    return True, text


def _lab_budget(ctx: _Ctx, a) -> tuple[bool, str]:
    if a.amount is None:
        return False, "missing amount"
    old = ctx.world.finances.lab_budget
    ctx.world.finances.lab_budget = clamp(a.amount, 0.0, 400.0)
    return True, f"LAB budget €{old:.0f} → €{ctx.world.finances.lab_budget:.0f}"


def _marketing(ctx: _Ctx, a) -> tuple[bool, str]:
    if a.amount is None:
        return False, "missing amount"
    old = ctx.world.finances.marketing_budget
    ctx.world.finances.marketing_budget = clamp(a.amount, 0.0, 600.0)
    return True, f"Marketing €{old:.0f} → €{ctx.world.finances.marketing_budget:.0f}"


def _deploy(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    exp = w.experiments.get(a.experiment_id or "")
    if exp is None or exp.status not in ("completed", "deployed"):
        return False, "no completed experiment with that id"
    e = _emp(ctx, a.employee_id, ("tipster",))
    if e is None:
        return False, "no such active tipster"
    if e.strategy_id == exp.strategy_id:
        return False, "already using it"
    age = e.strategy_age_days(w.today)
    if age < MIN_STRATEGY_DAYS:
        return False, f"{e.name} switched strategy only {age} days ago; give it time"
    refuse = 0.5 * e.traits.stubborn * (0.5 if e.under_review else 1.0)
    if ctx.rng.random() < refuse:
        e.psyche.stress = clamp(e.psyche.stress + 0.05, 0.02, 0.98)
        e.add_career(w.today, "refused", f"Refused to adopt the LAB strategy '{exp.name}'.")
        history.record(w, "refusal", f"{e.name} refuses the LAB's '{exp.name}'",
                       "Loyal to their own model.", 2, "drama", [e.id], e.department_id)
        return False, f"{e.name} refused to switch strategies"
    old = w.strategies.get(e.strategy_id or "")
    e.strategy_id = exp.strategy_id
    exp.status = "deployed"
    exp.deployed_to.append(e.id)
    if old and not any(x.strategy_id == old.id for x in w.tipsters()):
        old.retired = True
    e.add_career(w.today, "strategy", f"Switched to the LAB strategy '{exp.name}'.")
    w.stats.strategies_deployed += 1
    history.record(w, "strategy_deployed", f"LAB strategy '{exp.name}' deployed to {e.name}",
                   exp.hypothesis, 2, "good", [e.id, exp.researcher_id], e.department_id)
    return True, f"{e.name} now runs '{exp.name}'"


def _adjust(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    e = _emp(ctx, a.employee_id, ("tipster",))
    if e is None or not e.strategy_id or a.field not in PARAM_BOUNDS or a.value is None:
        return False, "unknown tipster or parameter"
    s = w.strategies[e.strategy_id]
    if sum(1 for x in w.tipsters() if x.strategy_id == s.id) > 1:  # fork shared strategies
        s = s.model_copy(deep=True, update={"id": w.next_id("s"), "name": f"{s.name} ({e.name} tweak)",
                                            "live_bets": 0, "live_staked": 0.0, "live_profit": 0.0})
        w.strategies[s.id] = s
        e.strategy_id = s.id
    lo, hi = PARAM_BOUNDS[a.field]
    value = clamp(float(a.value), lo, hi)
    setattr(s, a.field, int(round(value)) if a.field == "window" else value)
    for f in w.audit_findings:
        if f.employee_id == e.id and f.suggestion.get("field") == a.field:
            f.resolved = True
    e.add_career(w.today, "strategy", f"Strategy adjusted: {a.field} = {value:g}.")
    return True, f"{e.name}: {a.field} → {value:g}"


def _freeze(ctx: _Ctx, a) -> tuple[bool, str]:
    if ctx.world.finances.hiring_frozen:
        return False, "already frozen"
    ctx.world.finances.hiring_frozen = True
    history.record(ctx.world, "hiring_freeze", "Hiring freeze", a.reason, 2, "bad")
    return True, "hiring frozen"


def _unfreeze(ctx: _Ctx, a) -> tuple[bool, str]:
    if not ctx.world.finances.hiring_frozen:
        return False, "hiring is not frozen"
    ctx.world.finances.hiring_frozen = False
    history.record(ctx.world, "hiring_unfreeze", "Hiring freeze lifted", a.reason, 2, "good")
    return True, "hiring unfrozen"


def _cut_salaries(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    pct = clamp(a.pct or 0.1, 0.05, 0.3)
    for e in w.active_employees():
        e.salary = round(e.salary * (1 - pct), 2)
        if e.role != "ceo":
            e.psyche.stress = clamp(e.psyche.stress + EC.SALARY_CUT_STRESS, 0.02, 0.98)
            e.add_career(w.today, "salary_cut", f"Salary cut by {pct:.0%}.")
    w.milestones["months_since_salary_cut"] = 0
    w.stats.salary_cuts += 1
    history.record(w, "salary_cut", f"Company-wide salary cut of {pct:.0%}", a.reason, 3, "bad")
    return True, f"salaries cut {pct:.0%}"


def _loan(ctx: _Ctx, a) -> tuple[bool, str]:
    got = accounting.take_loan(ctx.world, a.amount or 0.0)
    if got <= 0:
        return False, "no credit available"
    ctx.world.stats.loans_taken += 1
    history.record(ctx.world, "loan", f"Borrowed €{got:,.0f}", a.reason, 2, "drama")
    return True, f"borrowed €{got:,.0f}"


def _lease(ctx: _Ctx, a) -> tuple[bool, str]:
    w = ctx.world
    if ctx.scope != "monthly":
        return False, "leases are signed at the monthly review"
    if w.finances.status == "distress":
        return False, "no landlord signs with a company in distress"
    return lease_facility(w, a.facility or "")


def _release(ctx: _Ctx, a) -> tuple[bool, str]:
    return release_facility(ctx.world, a.facility or "")


def _repay(ctx: _Ctx, a) -> tuple[bool, str]:
    paid = accounting.repay_loan(ctx.world, a.amount or 0.0)
    if paid <= 0:
        return False, "nothing to repay"
    return True, f"repaid €{paid:,.0f}"


_HANDLERS = {
    "FIRE": _fire, "HIRE": _hire, "PROMOTE": _promote, "WARN": _warn, "CLEAR_REVIEW": _clear,
    "TRANSFER_EMPLOYEE": _transfer, "SET_STAKE_LIMIT": _stake_limit, "FUND_DEPARTMENT": _fund,
    "WITHDRAW_BANKROLL": _withdraw, "CREATE_DEPARTMENT": _create_dept, "CLOSE_DEPARTMENT": _close_dept,
    "SET_LAB_BUDGET": _lab_budget, "SET_MARKETING_BUDGET": _marketing, "DEPLOY_STRATEGY": _deploy,
    "ADJUST_STRATEGY": _adjust, "FREEZE_HIRING": _freeze, "UNFREEZE_HIRING": _unfreeze,
    "CUT_SALARIES": _cut_salaries, "TAKE_LOAN": _loan, "REPAY_LOAN": _repay,
    "LEASE_SPACE": _lease, "RELEASE_SPACE": _release,
}

