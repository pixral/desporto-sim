"""Mock CEO judgement. Reads the management report, returns validated management actions + memo.

Each style has different thresholds and appetites, and a dose of randomness, so the same
season produces very different company histories under different CEOs.
"""

from __future__ import annotations

import random
from typing import Any

from app.domain.base import clamp

STYLES: dict[str, dict[str, float]] = {
    "conservative_operator": dict(
        fire_z=-1.3, fire_min_bets=60, needs_warning=1, warn_z=-0.8, promote_z=1.7, promote_min_bets=90,
        hire_runway=14, target_per_desk=2, stake_base=0.035, stake_max=0.055, expand_prob=0.12,
        lab_budget=45, marketing=50, cut_runway=6, cut_prob=0.8, freeze_runway=8, loan_appetite=0.0,
        close_roi=-0.06, close_prob=0.7, randomness=0.04, double_down=0.0, follow_lab=0.5, min_lab_sample=150,
        max_promotions=1),
    "aggressive_expansionist": dict(
        fire_z=-2.0, fire_min_bets=50, needs_warning=1, warn_z=-1.3, promote_z=1.0, promote_min_bets=50,
        hire_runway=6, target_per_desk=3, stake_base=0.065, stake_max=0.12, expand_prob=0.55,
        lab_budget=70, marketing=170, cut_runway=1.5, cut_prob=0.15, freeze_runway=2.5, loan_appetite=0.9,
        close_roi=-0.15, close_prob=0.3, randomness=0.12, double_down=0.6, follow_lab=0.6, min_lab_sample=60,
        max_promotions=2),
    "data_driven": dict(
        fire_z=-1.6, fire_min_bets=80, needs_warning=1, warn_z=-1.0, promote_z=1.8, promote_min_bets=100,
        hire_runway=10, target_per_desk=2, stake_base=0.05, stake_max=0.08, expand_prob=0.35,
        lab_budget=110, marketing=80, cut_runway=4, cut_prob=0.6, freeze_runway=5, loan_appetite=0.25,
        close_roi=-0.08, close_prob=0.8, randomness=0.03, double_down=0.0, follow_lab=1.0, min_lab_sample=100,
        max_promotions=1),
    "chaotic_founder": dict(
        fire_z=-1.0, fire_min_bets=25, needs_warning=0, warn_z=-0.5, promote_z=0.8, promote_min_bets=30,
        hire_runway=7, target_per_desk=3, stake_base=0.055, stake_max=0.12, expand_prob=0.15,
        lab_budget=60, marketing=120, cut_runway=3, cut_prob=0.5, freeze_runway=3, loan_appetite=0.7,
        close_roi=-0.05, close_prob=0.5, randomness=0.35, double_down=0.45, follow_lab=0.3, min_lab_sample=30,
        max_promotions=2),
}


class _Plan:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []

    def add(self, type_: str, reason: str = "", **kw: Any) -> None:
        self.actions.append({"type": type_, "reason": reason, **{k: v for k, v in kw.items() if v is not None}})

    def count(self, type_: str) -> int:
        return sum(1 for a in self.actions if a["type"] == type_)

    def names(self, type_: str, ctx: dict[str, Any]) -> list[str]:
        by_id = {e["id"]: e["name"] for e in ctx["employees"]}
        return [by_id.get(a.get("employee_id", ""), "?") for a in self.actions if a["type"] == type_]


def review(ctx: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    style = ctx["ceo"]["style"] or "data_driven"
    st = STYLES[style]
    co = ctx["company"]
    scope = ctx["scope"]
    plan = _Plan()
    runway = co["runway_months"]
    rw = 999.0 if runway is None else runway
    burn = max(co["monthly_burn"], 50.0)
    costs = max(co["monthly_costs"], 200.0)  # fixed operating cost: the yardstick for cash buffers
    status = co["status"]
    in_trouble = status == "distress" or rw < st["cut_runway"]
    thriving = status == "thriving"
    conf = ctx["ceo"]["confidence"]
    tipsters = [e for e in ctx["employees"] if e["role"] == "tipster"]
    depts = ctx["departments"]
    limits = ctx["limits"]

    # ---- liquidity first ------------------------------------------------------------------
    if co["cash"] < costs * (0.6 if scope == "weekly" else 1.2) and depts:
        richest = max(depts, key=lambda d: d["bankroll"])
        need = costs * 1.5 - co["cash"]
        amount = round(min(need, richest["bankroll"] * 0.5), 0)
        if amount >= 50:
            plan.add("WITHDRAW_BANKROLL", "Cash is too thin to cover obligations.",
                     department_id=richest["id"], amount=amount)

    # ---- performance management -----------------------------------------------------------
    fired: set[str] = set()
    max_fires = limits["max_fires"]
    for e in sorted(tipsters, key=lambda x: x["z_90d"]):
        if len(fired) >= max_fires:
            break
        enough = e["bets_90d"] >= st["fire_min_bets"]
        bad = e["z_90d"] <= st["fire_z"] or (enough and e["roi_90d"] < -0.12)
        warned = e["under_review"] or not st["needs_warning"]
        if enough and bad and warned and (scope == "monthly" or e["z_90d"] <= st["fire_z"] - 0.8):
            plan.add("FIRE", f"ROI {e['roi_90d']:+.1%} over {e['bets_90d']} bets (z {e['z_90d']:+.1f}) after a warning.",
                     employee_id=e["id"])
            fired.add(e["id"])
    if scope == "monthly" and in_trouble and not fired and len(tipsters) > 4:
        worst = min(tipsters, key=lambda x: x["z_90d"])
        if worst["z_90d"] < 0 and worst["bets_90d"] >= 20 and rng.random() < 0.6:
            plan.add("FIRE", "Cost cutting: we cannot carry negative contributors right now.", employee_id=worst["id"])
            fired.add(worst["id"])
    if rng.random() < st["randomness"] * (0.25 if scope == "monthly" else 0.08) and tipsters and len(fired) < max_fires:
        victim = rng.choice(tipsters)
        if victim["id"] not in fired and victim["tenure_days"] > 30:
            plan.add("FIRE", "Gut feeling. The energy is wrong.", employee_id=victim["id"])
            fired.add(victim["id"])

    for e in tipsters:
        if e["id"] in fired:
            continue
        if not e["under_review"]:
            if e["bets_90d"] >= st["fire_min_bets"] * 0.5 and e["z_90d"] <= st["warn_z"] - (0.6 if scope == "weekly" else 0):
                plan.add("WARN", f"ROI {e['roi_90d']:+.1%} over {e['bets_90d']} bets is not acceptable.", employee_id=e["id"])
            elif scope == "monthly" and e["no_bet_rate"] > 0.92 and e["tenure_days"] > 45:
                plan.add("WARN", "You pass on almost everything. We pay you to find bets.", employee_id=e["id"])
        elif e["z_90d"] > 0.2 and e["no_bet_rate"] <= 0.92:
            plan.add("CLEAR_REVIEW", "Numbers have recovered. Back to normal.", employee_id=e["id"])

    if scope == "monthly":
        promos = 0
        for e in sorted(tipsters, key=lambda x: -x["z_90d"]):
            if promos >= st["max_promotions"]:
                break
            if (e["id"] not in fired and e["level"] < 3 and not e["under_review"] and e["tenure_days"] >= 60
                    and e["bets_90d"] >= st["promote_min_bets"] and e["z_90d"] >= st["promote_z"]
                    and (status != "distress" or style == "aggressive_expansionist")):
                plan.add("PROMOTE", f"Outstanding: ROI {e['roi_90d']:+.1%} over {e['bets_90d']} bets.", employee_id=e["id"])
                promos += 1

    # ---- money: limits, budgets, loans ----------------------------------------------------
    double_down = in_trouble and rng.random() < st["double_down"] * (0.7 + 0.6 * conf)
    for d in depts:
        cur = d["stake_limit_pct"]
        target = cur
        if style == "data_driven":
            # size to statistical evidence, not to noisy ROI
            target = st["stake_base"] * clamp(1 + 0.25 * d["z_90d"], 0.5, 1.6) if d["bets_90d"] >= 40 else st["stake_base"]
        elif style == "conservative_operator":
            target = st["stake_base"] * (0.6 if co["drawdown"] > 0.15 else 1.0)
            if status == "distress":
                target = 0.015
        elif style == "aggressive_expansionist":
            if double_down:
                target = cur * 1.3
            elif d["profit_30d"] > 0:
                target = cur * (1.1 + 0.1 * conf)
        else:  # chaotic
            if rng.random() < (0.5 if scope == "monthly" else 0.15):
                target = cur * rng.uniform(0.65, 1.55)
        if scope == "weekly" and style == "conservative_operator" and d["profit_30d"] < -0.08 * max(d["bankroll"], 1):
            target = min(target, cur * 0.8)
        target = clamp(target, limits["min_stake_pct"] * 2, st["stake_max"])
        if abs(target - cur) > 0.003:
            why = "Doubling down — we bet our way out of this." if double_down else (
                "Sizing to recent performance." if target < cur else "This desk has earned more room.")
            plan.add("SET_STAKE_LIMIT", why, department_id=d["id"], pct=round(target, 4))

    if scope == "monthly":
        if in_trouble:
            if co["months_since_salary_cut"] >= 3 and rng.random() < st["cut_prob"]:
                plan.add("CUT_SALARIES", "Everyone takes a hit so the company survives.", pct=0.1)
            credit = co["credit_available"]
            if credit > 100 and rng.random() < st["loan_appetite"]:
                plan.add("TAKE_LOAN", "Buying time with borrowed money.", amount=round(min(credit, costs * 2), 0))
        if not co["hiring_frozen"] and rw < st["freeze_runway"]:
            plan.add("FREEZE_HIRING", "No new hires until the runway improves.")
        elif co["hiring_frozen"] and rw > st["freeze_runway"] * 1.6:
            plan.add("UNFREEZE_HIRING", "Runway is healthy again.")
        lab_target = st["lab_budget"] * (0.5 if in_trouble and style != "data_driven" else 1.0) * (
            1.3 if thriving and style == "data_driven" else 1.0)
        mkt_target = st["marketing"] * (1.4 if thriving and style == "aggressive_expansionist" else 1.0) * (
            0.5 if in_trouble and style in ("conservative_operator", "data_driven") else 1.0)
        if style == "chaotic_founder" and rng.random() < 0.3:
            lab_target, mkt_target = rng.uniform(20, 160), rng.uniform(20, 260)
        if abs(lab_target - co["lab_budget"]) > 10:
            plan.add("SET_LAB_BUDGET", "Adjusting research spend.", amount=round(lab_target, 0))
        if abs(mkt_target - co["marketing_budget"]) > 10:
            plan.add("SET_MARKETING_BUDGET", "Adjusting marketing spend.", amount=round(mkt_target, 0))
        if co["debt"] > 0 and co["cash"] > costs * 4:
            plan.add("REPAY_LOAN", "Paying down debt while we can.", amount=round(min(co["debt"], co["cash"] - costs * 3), 0))
        # bankroll moves
        if style == "data_driven" and len(depts) >= 2:
            ranked = sorted((d for d in depts if d["bets_90d"] >= 60), key=lambda d: d["roi_90d"])
            if len(ranked) >= 2 and ranked[0]["roi_90d"] < -0.05 and ranked[-1]["roi_90d"] > 0.02:
                amount = round(ranked[0]["bankroll"] * 0.25, 0)
                if amount >= 100:
                    plan.add("WITHDRAW_BANKROLL", "Reallocating away from an underperforming desk.",
                             department_id=ranked[0]["id"], amount=amount)
                    plan.add("FUND_DEPARTMENT", "Backing the best-performing desk.",
                             department_id=ranked[-1]["id"], amount=amount)
        if thriving and co["cash"] > costs * 5 and depts:
            best = max(depts, key=lambda d: d["profit_90d"])
            plan.add("FUND_DEPARTMENT", "Putting surplus cash to work.", department_id=best["id"],
                     amount=round(min(1500, co["cash"] - costs * 4), 0))

        # ---- LAB ------------------------------------------------------------------------
        deployed = 0
        for x in sorted(ctx["lab"]["ready"], key=lambda r: -r["roi"]):
            if deployed >= (2 if style == "data_driven" else 1):
                break
            willing = x["recommendation"] == "DEPLOY" and x["sample"] >= st["min_lab_sample"]
            willing = willing or (x["recommendation"] == "PROMISING" and st["follow_lab"] >= 0.6
                                  and x["sample"] >= st["min_lab_sample"] and rng.random() < 0.3)
            willing = willing or (style == "chaotic_founder" and rng.random() < 0.35)
            if not willing or rng.random() > st["follow_lab"] + 0.2:
                continue
            target = _deploy_target(ctx, x, fired)
            if target:
                plan.add("DEPLOY_STRATEGY", f"LAB result: ROI {x['roi']:+.1%} on {x['sample']} bets.",
                         experiment_id=x["id"], employee_id=target)
                deployed += 1
        for a in ctx["lab"]["audit"]:
            if a["field"] and a["bets"] >= 25 and a["roi"] < -0.15 and rng.random() < st["follow_lab"] * 0.8:
                if a["employee_id"] not in fired:
                    plan.add("ADJUST_STRATEGY", f"LAB audit: {a['text']}", employee_id=a["employee_id"],
                             field=a["field"], value=a["value"])

        # ---- hiring ---------------------------------------------------------------------
        frozen = co["hiring_frozen"] or plan.count("FREEZE_HIRING") > 0
        avg_salary = co["monthly_payroll"] / max(len(ctx["employees"]) + 1, 1)
        can_afford = co["cash"] > 3 * avg_salary and rw >= st["hire_runway"] and not in_trouble
        hires = 0
        used: set[str] = set()
        if not frozen and co["cash"] > 3 * avg_salary:
            needy = []
            for d in depts:
                remaining = d["headcount"] - sum(1 for e in tipsters if e["department_id"] == d["id"] and e["id"] in fired)
                # an empty desk wastes its bankroll: restaff it even when money is tight
                if remaining == 0 or (can_afford and remaining < min(st["target_per_desk"], limits["max_desk_size"])):
                    needy.append((remaining, d))
            needy.sort(key=lambda x: (x[0], -x[1]["profit_90d"]))
            for _, d in needy:
                if hires >= limits["max_hires"]:
                    break
                cand = _pick_candidate(ctx, d, style, rng, used)
                if cand:
                    plan.add("HIRE", f"Strengthening the {d['name']}.", candidate_id=cand["id"], department_id=d["id"])
                    used.add(cand["id"])
                    hires += 1
            lab = ctx["lab"]
            if hires < limits["max_hires"] and lab["department_id"] and co["lab_budget"] > 0:
                want = len(lab["researchers"]) == 0 or (style == "data_driven" and thriving and len(lab["researchers"]) < 2)
                res = [c for c in ctx["candidates"] if c["role"] == "researcher" and c["id"] not in used]
                if want and res and (style == "data_driven" or rng.random() < 0.5):
                    best = max(res, key=lambda c: c["cv_rating"] - c["salary_ask"] / 3)
                    plan.add("HIRE", "The LAB needs hands.", candidate_id=best["id"], department_id=lab["department_id"])
                    hires += 1

        # ---- departments ----------------------------------------------------------------
        kinds = ctx["available_department_kinds"]
        expand_prob = st["expand_prob"] * (1.4 if conf > 0.7 else 1.0)
        may_expand = (thriving or (style == "aggressive_expansionist" and rw >= 10)
                      or (style == "chaotic_founder" and status != "distress"))
        if kinds and limits["desks"] < limits["max_desks"] and not frozen and may_expand and rng.random() < expand_prob:
            amount = min(co["cash"] - 2 * costs, 2500)
            if amount >= 800:
                kind = rng.choice(kinds)
                plan.add("CREATE_DEPARTMENT", f"Opening a {kind['name']} — new markets, new edges.",
                         department_kind=kind["kind"], amount=round(amount, 0))
        cooldown_ok = co["days_since_desk_closed"] >= 120
        closable = [d for d in depts if d["bets_90d"] >= 60 and d["roi_90d"] < st["close_roi"] and d["z_90d"] <= -1.5
                    and d["profit_90d"] < -200 and d["age_days"] >= 120]
        if closable and len(depts) > 2 and cooldown_ok and rng.random() < st["close_prob"]:
            d = min(closable, key=lambda d: d["roi_90d"])
            plan.add("CLOSE_DEPARTMENT", f"The {d['name']} is bleeding money (ROI {d['roi_90d']:+.1%}).", department_id=d["id"])
        elif in_trouble and len(depts) > 3 and cooldown_ok and rng.random() < 0.25:
            d = min(depts, key=lambda d: d["profit_90d"])
            plan.add("CLOSE_DEPARTMENT", f"Survival mode: shutting the {d['name']}.", department_id=d["id"])
        elif style == "chaotic_founder" and len(depts) > 2 and cooldown_ok and rng.random() < 0.04:
            d = rng.choice(depts)
            plan.add("CLOSE_DEPARTMENT", "Restructuring. Don't ask.", department_id=d["id"])

    return {"thought": _thought(ctx, style, rw, in_trouble, thriving),
            "memo": _memo(ctx, style, plan, rw, in_trouble, thriving, scope),
            "actions": plan.actions}


def _deploy_target(ctx: dict[str, Any], x: dict[str, Any], fired: set[str]) -> str | None:
    comps = set(x["competitions"])
    dept_comps = {d["id"]: set(d["competitions"]) for d in ctx["departments"]}
    pool = [e for e in ctx["employees"] if e["role"] == "tipster" and e["id"] not in fired
            and (not comps or comps & dept_comps.get(e["department_id"], set()))]
    if not pool:
        return None
    return min(pool, key=lambda e: (e["z_90d"] if e["bets_90d"] >= 20 else 0.0))["id"]


def _pick_candidate(ctx: dict[str, Any], dept: dict[str, Any], style: str, rng: random.Random,
                    used: set[str]) -> dict[str, Any] | None:
    pool = [c for c in ctx["candidates"] if c["role"] == "tipster" and c["id"] not in used
            and c["specialty"] in dept.get("preferred_specialties", [])]
    if not pool:
        pool = [c for c in ctx["candidates"] if c["role"] == "tipster" and c["id"] not in used]
    if not pool:
        return None
    if style == "chaotic_founder":
        return rng.choice(pool)
    if style == "aggressive_expansionist":
        return max(pool, key=lambda c: c["cv_rating"])
    if style == "conservative_operator":
        return max(pool, key=lambda c: c["cv_rating"] / 10 - c["salary_ask"] / 15)

    def score(c: dict[str, Any]) -> float:
        lab = 0.0
        if c.get("lab_backtest_roi") is not None and (c.get("lab_backtest_n") or 0) >= 40:
            lab = c["lab_backtest_roi"] * 100
        return lab + c["cv_rating"] / 20 - c["salary_ask"] / 40
    return max(pool, key=score)


def _thought(ctx: dict[str, Any], style: str, rw: float, in_trouble: bool, thriving: bool) -> str:
    co = ctx["company"]
    if in_trouble:
        return {
            "conservative_operator": f"Runway {rw:.1f} months. Cut, cut, cut — protect what's left.",
            "aggressive_expansionist": "We're behind. Playing small now guarantees we die slowly.",
            "data_driven": f"Burn €{co['monthly_burn']:.0f}/month with {rw:.1f} months left. Only evidence-backed bets survive.",
            "chaotic_founder": "Everything is on fire and honestly I've never felt more alive.",
        }[style]
    if thriving:
        return {
            "conservative_operator": "Good months. Don't let success make us sloppy.",
            "aggressive_expansionist": "We're printing. Time to grow before the edge closes.",
            "data_driven": "Positive expectancy confirmed. Scale what the data supports.",
            "chaotic_founder": "We're geniuses. Let's do something bold.",
        }[style]
    return {
        "conservative_operator": "Steady. Keep stakes small and costs smaller.",
        "aggressive_expansionist": "Not enough growth. Where's the next edge?",
        "data_driven": "Mixed signals. Most results are still inside the noise.",
        "chaotic_founder": "I have a feeling about this month. Not sure which feeling.",
    }[style]


def _memo(ctx: dict[str, Any], style: str, plan: _Plan, rw: float, in_trouble: bool, thriving: bool,
          scope: str) -> str:
    fired = plan.names("FIRE", ctx)
    warned = plan.names("WARN", ctx)
    promoted = plan.names("PROMOTE", ctx)
    hires = plan.count("HIRE")
    cut = plan.count("CUT_SALARIES")
    new_desk = plan.count("CREATE_DEPARTMENT")
    closed = plan.count("CLOSE_DEPARTMENT")
    if scope == "weekly" and not (fired or warned or cut):
        return ""
    opener = {
        "conservative_operator": "Team — discipline first.",
        "aggressive_expansionist": "Team — we are here to win.",
        "data_driven": "Team — here is what the numbers say.",
        "chaotic_founder": "LISTEN UP.",
    }[style]
    parts = [opener]
    if in_trouble:
        parts.append(f"Our runway is {rw:.1f} months. Every euro matters now." if rw < 900 else "Cash is tight.")
    elif thriving:
        parts.append("We are profitable. Well done — now keep it that way.")
    if fired:
        parts.append(f"We have parted ways with {', '.join(fired)}.")
    if warned:
        parts.append(f"{', '.join(warned)}: you are under review. Show me results.")
    if promoted:
        parts.append(f"Congratulations to {', '.join(promoted)} on a well-earned promotion.")
    if cut:
        parts.append("Salaries are cut by 10% effective immediately.")
    if hires:
        parts.append(f"We are bringing in {hires} new colleague(s).")
    if new_desk:
        parts.append("We are opening a new desk.")
    if closed:
        parts.append("One desk is being closed.")
    if plan.count("DEPLOY_STRATEGY"):
        parts.append("A LAB strategy is going live.")
    if plan.count("TAKE_LOAN"):
        parts.append("We have secured additional credit.")
    if len(parts) == 1:
        parts.append("No changes this month. Keep doing the work.")
    return " ".join(parts)
