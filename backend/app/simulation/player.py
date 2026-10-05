"""Player mode rules: briefings, the advisor, office hours, the action queue, seasons and the board.

The player's decisions go through the same `management.apply_actions` validation as the AI CEO's.
Nothing here touches the football: the sports provider has its own random state.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from app.agents import management
from app.agents.catalog import CEO_STYLE_INFO, DEPARTMENT_KINDS
from app.ai.schemas import CEOAction, CEOReviewOutput
from app.domain.events import ActionRecord, ManagementLog
from app.domain.player import PendingReview, Proposal
from app.domain.world import World
from app.economy import config as EC
from app.economy import valuation as val

from . import history, metrics
from .summary import build_summary

CAREER_SEASONS = 5
# Between reviews the CEO can still walk the floor. Everything else waits for the monthly review.
OFFICE_ACTIONS = frozenset({"WARN", "CLEAR_REVIEW", "TRANSFER_EMPLOYEE", "GIVE_TIME_OFF", "SET_STAKE_LIMIT",
                            "FUND_DEPARTMENT", "WITHDRAW_BANKROLL", "FIRE", "TALK", "TEST_CANDIDATE"})
WEEKLY_LIMITS = {"FIRE": 1, "TALK": 3}
# Calls the advisor never makes on its own when it handles a review for you.
BIG_CALLS = frozenset({"FIRE", "CLOSE_DEPARTMENT", "CUT_SALARIES"})
QUEUE_MAX = 12
BOARD_MIN_DAYS = 180
BOARD_GRACE_DAYS = 28  # between the board's warning and its decision

AREAS = {
    "FIRE": "people", "PROMOTE": "people", "WARN": "people", "CLEAR_REVIEW": "people", "TRANSFER_EMPLOYEE": "people",
    "GIVE_TIME_OFF": "people", "TALK": "people", "TEAM_EVENT": "people",
    "HIRE": "hiring", "FREEZE_HIRING": "hiring", "UNFREEZE_HIRING": "hiring",
    "SET_STAKE_LIMIT": "desks", "FUND_DEPARTMENT": "desks", "WITHDRAW_BANKROLL": "desks",
    "CREATE_DEPARTMENT": "desks", "CLOSE_DEPARTMENT": "desks",
    "SET_MARKETING_BUDGET": "money", "CUT_SALARIES": "money", "TAKE_LOAN": "money", "REPAY_LOAN": "money",
    "SET_LAB_BUDGET": "lab", "DEPLOY_STRATEGY": "lab", "ADJUST_STRATEGY": "lab", "SET_LAB_BRIEF": "lab",
    "SHELVE_STRATEGY": "lab", "TEST_CANDIDATE": "hiring",
    "LEASE_SPACE": "office", "RELEASE_SPACE": "office",
}
_KEYS = ("employee_id", "candidate_id", "department_id", "experiment_id", "facility", "department_kind")


def active(world: World) -> bool:
    return world.config.player_ceo


def awaiting(world: World) -> bool:
    r = world.player.review
    return r is not None and r.status == "open"


def decides(world: World, scope: str) -> bool:
    """Which reviews wait for the player (the others are handled by the advisor)."""
    mode = world.config.pause_mode
    if mode == "every_review":
        return True
    if mode == "events_only":
        return False
    return scope == "monthly"


def advisor_label(world: World) -> str:
    return CEO_STYLE_INFO.get(world.config.ceo_style, {"label": world.config.ceo_style})["label"]


# ---------------------------------------------------------------------------------- labels
def _name(world: World, emp_id: Any) -> str:
    e = world.employees.get(str(emp_id or ""))
    return e.name if e else "someone"


def _dept(world: World, dept_id: Any) -> str:
    d = world.departments.get(str(dept_id or ""))
    return d.name if d else "a desk"


def describe(world: World, a: dict[str, Any]) -> str:
    """A short, readable line for an action (for briefings, the queue and the log)."""
    t = a.get("type", "")
    who = _name(world, a.get("employee_id"))
    desk = _dept(world, a.get("department_id"))
    amount = float(a.get("amount") or 0)
    if t == "FIRE":
        return f"Fire {who}"
    if t == "HIRE":
        cand = next((c for c in world.candidates if c.id == a.get("candidate_id")), None)
        return f"Hire {cand.name if cand else 'a candidate'} into the {desk}"
    if t == "PROMOTE":
        return f"Promote {who}"
    if t == "WARN":
        return f"Warn {who}"
    if t == "CLEAR_REVIEW":
        return f"Lift {who}'s review"
    if t == "TRANSFER_EMPLOYEE":
        return f"Move {who} to the {desk}"
    if t == "GIVE_TIME_OFF":
        return f"Give {who} {int(a.get('value') or 3)} day(s) off"
    if t == "TALK":
        return f"Talk with {who}"
    if t == "TEAM_EVENT":
        return "Team night out"
    if t == "SET_STAKE_LIMIT":
        d = world.departments.get(str(a.get("department_id") or ""))
        now = f"{d.stake_limit_pct:.1%} → " if d else ""
        return f"{desk}: max stake {now}{float(a.get('pct') or 0):.1%} of bankroll"
    if t == "FUND_DEPARTMENT":
        return f"Move €{amount:,.0f} into the {desk}"
    if t == "WITHDRAW_BANKROLL":
        return f"Withdraw €{amount:,.0f} from the {desk}"
    if t == "CREATE_DEPARTMENT":
        kind = DEPARTMENT_KINDS.get(str(a.get("department_kind") or ""))
        return f"Open the {kind.name if kind else 'new desk'} with €{amount:,.0f}"
    if t == "CLOSE_DEPARTMENT":
        return f"Close the {desk}"
    if t == "SET_LAB_BUDGET":
        return f"LAB budget €{world.finances.lab_budget:,.0f} → €{amount:,.0f}/month"
    if t == "SET_MARKETING_BUDGET":
        return f"Marketing €{world.finances.marketing_budget:,.0f} → €{amount:,.0f}/month"
    if t == "DEPLOY_STRATEGY":
        x = world.experiments.get(str(a.get("experiment_id") or ""))
        return f"Roll out '{x.name if x else 'a LAB strategy'}' to {who}"
    if t == "ADJUST_STRATEGY":
        return f"{who}: set {a.get('field')} to {a.get('value')}"
    if t == "FREEZE_HIRING":
        return "Freeze hiring"
    if t == "UNFREEZE_HIRING":
        return "Lift the hiring freeze"
    if t == "CUT_SALARIES":
        return f"Cut every salary by {float(a.get('pct') or 0.1):.0%}"
    if t == "TAKE_LOAN":
        return f"Borrow €{amount:,.0f}"
    if t == "REPAY_LOAN":
        return f"Repay €{amount:,.0f} of debt"
    if t == "SET_LAB_BRIEF":
        return brief_label(world, a)
    if t == "TEST_CANDIDATE":
        cand = next((c for c in world.candidates if c.id == a.get("candidate_id")), None)
        return f"LAB: test {cand.name if cand else 'an applicant'}'s method"
    if t == "SHELVE_STRATEGY":
        x = world.experiments.get(str(a.get("experiment_id") or ""))
        return f"Shelve '{x.name if x else 'a LAB strategy'}'"
    if t in ("LEASE_SPACE", "RELEASE_SPACE"):
        name = str(EC.FACILITIES.get(str(a.get("facility") or ""), {"name": "space"})["name"])
        name = name[4:] if name.startswith("The ") else name
        return f"{'Lease' if t == 'LEASE_SPACE' else 'Give up'} the {name}"
    return t.replace("_", " ").capitalize()


def brief_label(world: World, a: dict[str, Any]) -> str:
    kind, _, value = str(a.get("field") or "").partition(":")
    if kind == "competition":
        comp = world.competitions.get(value)
        return f"LAB brief: {comp.name if comp else value}"
    if kind == "market":
        return f"LAB brief: {management.MARKET_NAMES.get(value, value)}"
    if kind == "underdogs":
        return "LAB brief: underdogs at longer odds"
    if kind == "desk":
        return f"LAB brief: ideas for the {_dept(world, a.get('department_id'))}"
    return "LAB brief: researchers' own ideas"


def proposal(world: World, action: CEOAction) -> Proposal:
    data = action.model_dump(exclude_none=True)
    return Proposal(action=data, label=describe(world, data), reason=action.reason,
                    area=AREAS.get(action.type, "people"))


def make_review(world: World, scope: str, out: CEOReviewOutput) -> PendingReview:
    return PendingReview(id=world.next_id("rv"), scope=scope, created=world.clock.now,  # type: ignore[arg-type]
                         thought=out.thought.strip(), memo=out.memo.strip(),
                         proposals=[proposal(world, a) for a in out.actions])


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("type") == b.get("type") and all(a.get(k) == b.get(k) for k in _KEYS)


def compare_with_advice(review: PendingReview, actions: list[CEOAction]) -> tuple[int, list[str]]:
    """How many of the advisor's suggestions the player took, and which ones they turned down."""
    chosen = [a.model_dump(exclude_none=True) for a in actions]
    taken, skipped = 0, []
    for p in review.proposals:
        if any(_same(p.action, c) for c in chosen):
            taken += 1
        else:
            skipped.append(p.label)
    return taken, skipped


def auto_actions(world: World, scope: str, review: PendingReview) -> tuple[list[CEOAction], list[str]]:
    """The advisor handles a review for the player: queued orders first (monthly), never the big calls."""
    actions: list[CEOAction] = []
    if scope == "monthly":
        actions += [CEOAction(**q.action) for q in world.player.queue]
        world.player.queue = []
    left: list[str] = []
    for p in review.proposals:
        if p.action.get("type") in BIG_CALLS:
            left.append(p.label)
        else:
            actions.append(CEOAction(**p.action))
    return actions, left


# ---------------------------------------------------------------------------------- office hours
def week_key(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _roll_week(world: World) -> None:
    key = week_key(world.today)
    if world.player.week != key:
        world.player.week = key
        world.player.used = {}


def limits_left(world: World) -> dict[str, int]:
    _roll_week(world)
    return {t: max(0, n - world.player.used.get(t, 0)) for t, n in WEEKLY_LIMITS.items()}


def talked_this_week(world: World) -> list[str]:
    _roll_week(world)
    return [k.split(":", 1)[1] for k in world.player.used if k.startswith("talk:")]


def office_action(world: World, rng: random.Random, action: CEOAction) -> ActionRecord:
    """Act between reviews. Review-only decisions are refused (the player can queue them instead)."""
    params = action.model_dump(exclude_none=True, exclude={"type", "reason"})
    if not active(world) or world.ended:
        return ActionRecord(type=action.type, params=params, applied=False, result="you are not running this company")
    if action.type not in OFFICE_ACTIONS:
        return ActionRecord(type=action.type, params=params, applied=False,
                            result="that is decided at the monthly review; queue it for then")
    _roll_week(world)
    if action.type == "TALK" and world.player.used.get(f"talk:{action.employee_id}"):
        return ActionRecord(type=action.type, params=params, applied=False,
                            result=f"you already talked with {_name(world, action.employee_id)} this week")
    limit = WEEKLY_LIMITS.get(action.type)
    if limit is not None and world.player.used.get(action.type, 0) >= limit:
        word = {"FIRE": "firing", "TALK": "one-to-ones"}[action.type]
        return ActionRecord(type=action.type, params=params, applied=False,
                            result=f"you have used this week's {word} ({limit}); try again next week")
    rec = management.apply_actions(world, rng, [action], "office")[0]
    if rec.applied:
        count_used(world, [rec])
        log = world.management_log[-1] if world.management_log else None
        if log and log.scope == "office" and log.time.date() == world.today:
            log.actions.append(rec)
        else:
            world.management_log.append(ManagementLog(time=world.clock.now, scope="office", by="player", actions=[rec]))
            world.management_log = world.management_log[-120:]
    return rec


def count_used(world: World, records: list[ActionRecord]) -> None:
    """Weekly office-hours budget: firings and one-to-ones (talks in a briefing count too)."""
    _roll_week(world)
    for rec in records:
        if not rec.applied or rec.type not in WEEKLY_LIMITS:
            continue
        world.player.used[rec.type] = world.player.used.get(rec.type, 0) + 1
        if rec.type == "TALK":
            world.player.used[f"talk:{rec.params.get('employee_id')}"] = 1


def queue(world: World, action: CEOAction) -> Proposal:
    if action.type in OFFICE_ACTIONS:
        raise ValueError("you can do that right away; no need to wait for the review")
    if len(world.player.queue) >= QUEUE_MAX:
        raise ValueError(f"the queue holds {QUEUE_MAX} decisions at most")
    if action.type == "HIRE":
        cand = next((c for c in world.candidates if c.id == action.candidate_id), None)
        if cand is None:
            raise ValueError("no such candidate")
        cand.expires = max(cand.expires, next_month_start(world.today) + timedelta(days=1))  # they'll wait for the 1st
    p = proposal(world, action)
    world.player.queue.append(p)
    return p


def next_month_start(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def unqueue(world: World, index: int) -> None:
    if not 0 <= index < len(world.player.queue):
        raise ValueError("no such queued decision")
    del world.player.queue[index]


# ---------------------------------------------------------------------------------- career
def seasons_completed(world: World, today: date | None = None) -> int:
    """Seasons end on 1 June; one that started less than six months before doesn't count."""
    today = today or world.today
    start = world.config.start_date
    n = 0
    for year in range(start.year, today.year + 1):
        end = date(year, 6, 1)
        if start < end <= today and (end - start).days >= 180:
            n += 1
    return n


def season_label(world: World) -> str:
    d = world.today
    y = d.year if d >= date(d.year, 6, 1) else d.year - 1
    return f"{y}/{(y + 1) % 100:02d}"


def check_retirement(world: World) -> None:
    """After the fifth season's awards the player retires (the run ends with the full score)."""
    if not active(world) or world.ended or seasons_completed(world) < CAREER_SEASONS:
        return
    ceo = world.ceo()
    value = val.valuation(world)
    capital = world.config.starting_capital
    world.ended = True
    world.end_kind = "retired"
    world.end_reason = (f"{ceo.name} retires after {CAREER_SEASONS} seasons, leaving a company worth €{value:,.0f} "
                        f"({value / capital - 1:+.0%} on the starting capital).")
    for e in world.active_employees():
        e.status, e.task = "celebrating", "Farewell drinks for the boss"
    history.record(world, "retired", f"{ceo.name} retires", world.end_reason, 3, "good", [ceo.id])
    world.summary = build_summary(world)


def board_review(world: World, collapsed: bool, value: float) -> None:
    """The board warns the player first; still collapsed a month later, it fires them (on Easy it only warns)."""
    p = world.player
    capital = world.config.starting_capital
    ceo = world.ceo()
    if not collapsed:
        if p.board_warned and value >= 0.6 * capital:
            p.board_warned = None
            history.record(world, "board_relief", "The board backs you again",
                           f"Company value is back to €{value:,.0f}.", 2, "good", [ceo.id])
        return
    easy = world.config.difficulty == "easy"
    if p.board_warned is None:
        p.board_warned = world.clock.now
        then = "On Easy they grumble but keep you." if easy else             "Turn it around by the next monthly review or you're out."
        history.record(world, "board_warning", "The board is losing patience",
                       f"Company value €{value:,.0f} ({value / capital - 1:+.0%} since founding). {then}",
                       3, "bad", [ceo.id])
        return
    if easy or (world.today - p.board_warned.date()).days < BOARD_GRACE_DAYS:
        return
    world.ended = True
    world.end_kind = "fired"
    world.end_reason = (f"Fired by the board: the company was worth €{value:,.0f} "
                        f"({value / capital - 1:+.0%} since founding) after their warning.")
    ceo.status, ceo.task = "leaving", "Clearing out the corner office"
    ceo.thought = ""
    history.record(world, "board_fires_ceo", f"The board fires {ceo.name}", world.end_reason, 3, "bad", [ceo.id])
    world.summary = build_summary(world)


def board_line(world: World) -> dict[str, Any]:
    """What the board watches, in numbers (shown in briefings)."""
    capital = world.config.starting_capital
    floor = 0.45 * capital
    return {
        "floor_value": round(floor, 0),
        "drawdown_limit": 0.6,
        "active_from_day": BOARD_MIN_DAYS,
        "watching": world.clock.day_index >= BOARD_MIN_DAYS,
        "warned": world.player.board_warned.date().isoformat() if world.player.board_warned else None,
        "easy": world.config.difficulty == "easy",
    }


# ---------------------------------------------------------------------------------- the advisor's view
def advisor_note(world: World, emp_id: str) -> str:
    """A one-line read on a person from the advisor (open review first, then their numbers)."""
    e = world.employees.get(emp_id)
    if e is None or not e.active or e.role == "ceo":
        return ""
    r = world.player.review
    if r and r.status == "open":
        for p in r.proposals:
            if p.action.get("employee_id") == emp_id:
                return f"Suggests: {p.label.lower()}. {p.reason}".strip()
    if e.is_away(world.today):
        return f"Away ({e.away_reason}) until {e.away_until.strftime('%d %b') if e.away_until else 'soon'}."
    if e.tilt_on == world.today:
        return "On tilt after yesterday's losses: expect a desperate stake today."
    if e.frozen_until is not None and world.today <= e.frozen_until:
        return "Has lost their nerve. A talk or a few days off may bring them back."
    if e.psyche.stress >= 0.75:
        return f"Running hot (stress {e.psyche.stress:.0%}). A talk or a few days off would help."
    if e.role == "tipster":
        p90 = metrics.period_stats(world, e, 90)
        if e.under_review and p90.bets >= 20 and p90.z >= 0.3:
            return f"Back in form since the warning (ROI {p90.roi:+.1%}). You could lift the review."
        if p90.bets >= 40 and p90.z <= -1.3:
            verdict = "Firing them is defensible." if e.under_review else "A warning would be fair."
            return f"Losing for a while: ROI {p90.roi:+.1%} over {p90.bets} bets. {verdict}"
        if p90.bets >= 90 and p90.z >= 1.5 and e.level < 3:
            return f"One of your best (ROI {p90.roi:+.1%} over {p90.bets} bets). A promotion would keep them."
        if p90.bets < 30:
            return f"Too few bets lately ({p90.bets}) to judge. Give it time."
        return f"ROI {p90.roi:+.1%} over {p90.bets} bets: nothing to act on."
    return f"Stress {e.psyche.stress:.0%}, nothing worrying."


def days_to_season_end(world: World) -> int:
    d = world.today
    end = date(d.year if d < date(d.year, 6, 1) else d.year + 1, 6, 1)
    return (end - d).days


def next_review(world: World) -> dict[str, Any]:
    """When the next briefing that waits for the player happens."""
    d = world.today + timedelta(days=1)
    for _ in range(40):
        scope = "monthly" if d.day == 1 else "weekly" if d.weekday() == 0 else None
        if scope and decides(world, scope):
            return {"date": d.isoformat(), "scope": scope}
        d += timedelta(days=1)
    return {"date": None, "scope": None}
