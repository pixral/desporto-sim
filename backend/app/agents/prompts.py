"""Render agent contexts into prompts for real LLM providers.

The text is derived only from the structured context, which is also what the mock policies
consume. Prompts are stored with every AI call for observability.
"""

from __future__ import annotations

import json
from typing import Any

PAPER_NOTICE = ("This is a paper-betting simulation: all money is simulated and nothing is placed with a real "
                "bookmaker.")


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.1%}"


def tipster_system(ctx: dict[str, Any]) -> str:
    a = ctx["agent"]
    return (
        f"You are {a['name']}, {a['title']} ({a['specialty_label']}) at {ctx['company']['name']}, a sports betting "
        f"company staffed by AI agents. {PAPER_NOTICE}\n"
        f"Your personality: {a['traits_text']}. Stay in character: your personality, mood and situation should "
        "shape your choices, but you are free to decide how.\n"
        "For each assigned match decide BET or NO_BET. You are never obliged to bet, and passing is often right. "
        "Your strategy model's probabilities and edges are provided; you may follow, override or ignore them. "
        "If you bet, choose one market, a stake within your limits, and give a one-sentence reason. "
        "Return one decision per match, plus a one-sentence inner thought. Answer with JSON only."
    )


def tipster_user(ctx: dict[str, Any]) -> str:
    a, d, co, st, cons = ctx["agent"], ctx["department"], ctx["company"], ctx["strategy"], ctx["constraints"]
    lines = [
        f"TODAY: {ctx['weekday']} {ctx['date']}",
        "",
        "YOUR SITUATION",
        *[f"- {n}" for n in ctx["situation"]],
        f"- Stress {a['stress']:.0%}, confidence {a['confidence']:.0%}, risk tolerance {a['risk_tolerance']:.0%}, mood: {a['mood']}.",
        f"- Career: {a['career']['bets']} bets, P/L €{a['career']['profit']:+.2f} (ROI {_pct(a['career']['roi'])}). "
        f"This month: €{a['month_profit']:+.2f}. Passed on {a['no_bet_rate']:.0%} of recent opportunities.",
        "",
        "COMPANY",
        f"- Status: {co['status']}. Runway: {'not burning cash' if co['runway_months'] is None else str(co['runway_months']) + ' months'}. "
        f"Month-to-date net: €{co['month_net']:+.0f}. CEO: {co['ceo_name']} ({co['ceo_style']}).",
    ]
    if co["memo"]:
        lines.append(f"- Latest CEO memo: \"{co['memo']}\"")
    if d["colleagues"]:
        lines.append("- Desk colleagues: " + "; ".join(
            f"{c['name']} (recent ROI {_pct(c['recent_roi'])}, your trust {c['trust']:.0f}/100)" for c in d["colleagues"]))
    lines += [
        "",
        f"YOUR STRATEGY: {st['name']} — {st['summary']}. Minimum edge {st['min_edge']:.1%}, Kelly fraction {st['kelly_fraction']}.",
        f"LIMITS: at most {cons['max_bets']} bets today; stake between €{cons['min_stake']:.0f} and €{cons['max_stake']:.2f}; "
        f"desk bankroll €{cons['available_bankroll']:.2f} (your allocation €{d['allocation']:.2f}).",
        "",
        "MATCHES",
    ]
    for m in ctx["matches"]:
        lines.append(f"[{m['match_id']}] {m['label']} — {m['competition']} {m['stage']}, {m['kickoff']}")
        lines.append(f"  Form (last 5, oldest first): {m['home']['name']} {m['home']['form'] or '-'} "
                     f"(scores {m['home']['gf']}, concedes {m['home']['ga']}) | {m['away']['name']} {m['away']['form'] or '-'} "
                     f"(scores {m['away']['gf']}, concedes {m['away']['ga']})")
        for n in m["news"]:
            lines.append(f"  News: {n}")
        for c in m["candidates"]:
            flag = "fits strategy" if c["meets_strategy"] else c["blocked_by"]
            lines.append(f"  {c['market']:<10} {c['selection']:<24} best {c['odds']:.2f} @{c['book']:<8} "
                         f"model {c['prob']:.1%}  edge {c['edge']:+.1%}  ({flag})")
        for cw in m["coworkers"]:
            lines.append(f"  Colleague {cw['name']} (trust {cw['trust']:.0f}) leans {cw['selection']} (their edge {cw['edge']:+.1%})")
    lines += ["", "Respond with JSON: {\"thought\": str, \"decisions\": [{\"match_id\", \"decision\": \"BET\"|\"NO_BET\", "
              "\"market\", \"selection\", \"odds\", \"stake\", \"confidence\" (0-1), \"reason\", \"influenced_by\": [names]}]}"]
    return "\n".join(lines)


def ceo_system(ctx: dict[str, Any]) -> str:
    c = ctx["ceo"]
    return (
        f"You are {c['name']}, CEO of {ctx['company']['name']}, a sports betting company staffed by AI tipsters. "
        f"{PAPER_NOTICE}\nYour management style: {c['style_label']} — {c['style_description']} "
        f"Personality: {c['traits_text']}.\n"
        "You do not predict matches. You run the company: people, money, risk and strategy. Review the report and "
        "decide on management actions using only the listed action types and ids. Doing nothing is allowed. "
        "Write a short memo to staff (it will be read by every employee and may affect morale). Answer with JSON only."
    )


def ceo_user(ctx: dict[str, Any]) -> str:
    co = ctx["company"]
    lines = [f"{ctx['scope'].upper()} REVIEW — {ctx['date']}", "", "COMPANY"]
    lines.append(json.dumps(co, ensure_ascii=False))
    lines += ["", "DEPARTMENTS"] + [json.dumps(d, ensure_ascii=False) for d in ctx["departments"]]
    lines += ["", "EMPLOYEES (90-day stats; z = profit vs. luck, |z|<1 is mostly noise)"]
    lines += [json.dumps(e, ensure_ascii=False) for e in ctx["employees"]]
    lines += ["", "LAB", json.dumps(ctx["lab"], ensure_ascii=False)]
    lines += ["", "CANDIDATES"] + [json.dumps(c, ensure_ascii=False) for c in ctx["candidates"]]
    lines += ["", "DEPARTMENT KINDS YOU COULD OPEN", json.dumps(ctx["available_department_kinds"])]
    lines += ["", "LIMITS", json.dumps(ctx["limits"])]
    lines += ["", "RECENT EVENTS"] + [f"- {e}" for e in ctx["recent_events"]]
    if "office" in ctx:
        lines += ["", "OFFICE SPACE (the east wing next door is for lease)", json.dumps(ctx["office"], ensure_ascii=False)]
    if "city" in ctx:
        lines += ["", "THE CITY (this morning's paper and the economy)", json.dumps(ctx["city"], ensure_ascii=False)]
    lines += ["", "ACTIONS: FIRE(employee_id) HIRE(candidate_id, department_id) PROMOTE(employee_id) WARN(employee_id) "
              "CLEAR_REVIEW(employee_id) TRANSFER_EMPLOYEE(employee_id, department_id) SET_STAKE_LIMIT(department_id, pct) "
              "FUND_DEPARTMENT(department_id, amount) WITHDRAW_BANKROLL(department_id, amount) "
              "CREATE_DEPARTMENT(department_kind, amount) CLOSE_DEPARTMENT(department_id) SET_LAB_BUDGET(amount) "
              "SET_MARKETING_BUDGET(amount) DEPLOY_STRATEGY(experiment_id, employee_id) "
              "ADJUST_STRATEGY(employee_id, field, value) FREEZE_HIRING UNFREEZE_HIRING CUT_SALARIES(pct) "
              "TAKE_LOAN(amount) REPAY_LOAN(amount) LEASE_SPACE(facility) RELEASE_SPACE(facility) "
              "(facility: canteen, desk_wing or studio; leases only at monthly reviews). "
              "Each action may include a short reason.",
              "Respond with JSON: {\"thought\": str, \"memo\": str, \"actions\": [ ... ]}"]
    return "\n".join(lines)


def lab_system(ctx: dict[str, Any]) -> str:
    r = ctx["researcher"]
    return (
        f"You are {r['name']}, a {r['specialty_label']} in the LAB of a sports betting company staffed by AI agents. "
        f"{PAPER_NOTICE} Personality: {r['traits_text']}.\n"
        "Propose ONE testable betting strategy hypothesis expressed as model parameters. It will be backtested "
        "walk-forward on historical matches with the odds that were available at the time. Use only the parameter "
        "names given, within the bounds. Answer with JSON only."
    )


def lab_user(ctx: dict[str, Any]) -> str:
    lines = [
        f"DATE: {ctx['date']}. LAB budget €{ctx['budget']:.0f}/month. {ctx['history_matches']} historical matches available.",
        f"Competitions the company covers: {', '.join(ctx['competitions_covered'])}.",
        "",
        "PARAMETERS (name: [min, max]):",
        json.dumps(ctx["param_bounds"]),
        "Also: competitions (list of BL1, PL, LL, SA, UCL), markets (home_win, draw, away_win, over_2_5, under_2_5), "
        "opponent_adjust (bool), fade_popular (bool). model_weight 0 = pure market consensus, 1 = pure goal model; "
        "xg_weight 1 = rate teams on expected goals instead of goals; half_life = recency weighting in matches.",
        "",
        "STRATEGIES CURRENTLY IN USE (live results):",
        *[json.dumps(s, ensure_ascii=False) for s in ctx["live_strategies"]],
        "",
        "PAST EXPERIMENTS:",
        *[json.dumps(x, ensure_ascii=False) for x in ctx["past_experiments"]],
        "",
        "AUDIT HINTS:",
        *[f"- {h}" for h in ctx["audit_hints"]],
        "",
        "Respond with JSON: {\"name\": str, \"hypothesis\": str, \"rationale\": str, \"params\": {...}}",
    ]
    return "\n".join(lines)
