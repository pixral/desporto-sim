"""Workplace drama: rivalries, poaching, raise demands, the board, season awards.

Deterministic and personality-driven (no AI calls, so it costs nothing to run). Every outcome
becomes history and most of it is visible in the office.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from app.agents import hiring, management
from app.agents.catalog import CEO_STYLE_INFO
from app.agents.psychology import STATUS_DISTRESS
from app.domain.base import clamp
from app.domain.events import Memo
from app.domain.people import Employee
from app.domain.world import CEO_STYLES, Award, SeasonRecap, World
from app.economy import valuation as val

from . import history, metrics

RIVAL_SYNDICATES = (
    "Nordic Edge Syndicate", "Atlas Capital Betting", "Kopa Analytics", "Lisbon Value Club",
    "Danube Quant Fund", "Red Card Partners",
)
WINNER_LINES = ("Told you. Read the xG.", "Maybe follow my calls for once.", "That's how it's done.",
                "Some of us actually do the work.")
LOSER_LINES = ("Lucky. Pure variance.", "That was MY match to call!", "Stick to your own model.",
               "Enjoy it while it lasts.")

# How each CEO style handles people asking for more money.
# counter: chance to match a rival's offer; raise: size of a counter-offer; grant: chance to grant a raise demand
PEOPLE_POLICY: dict[str, dict[str, float]] = {
    "conservative_operator": {"counter": 0.35, "raise": 0.15, "grant": 0.25},
    "aggressive_expansionist": {"counter": 0.9, "raise": 0.30, "grant": 0.75},
    "data_driven": {"counter": 0.7, "raise": 0.20, "grant": 0.6},
    "chaotic_founder": {"counter": 0.5, "raise": 0.35, "grant": 0.5},
}

BOARD_MIN_DAYS = 180


def _ord(d: date) -> int:
    return d.toordinal()


def _since(world: World, key: str, default: int = 99_999) -> int:
    last = world.milestones.get(key)
    return default if last is None else world.today.toordinal() - int(last)


def _ceo_style(world: World) -> str:
    return world.ceo().ceo_style or world.config.ceo_style


# ---------------------------------------------------------------------------------- meetings
def gather_meeting(world: World, scope: str, touched: set[str] | None = None) -> list[Employee]:
    """Who sits with the CEO this morning: anyone the review affected, plus each desk's lead
    (the head of desk, else its most senior member). The LAB joins the monthly review."""
    touched = touched or set()
    called = [world.employees[i] for i in sorted(touched) if i in world.employees]
    called = [e for e in called if e.active and e.role != "ceo" and e.status not in ("arriving", "away")]
    leads: list[Employee] = []
    for d in sorted(world.active_departments(), key=lambda d: d.room_slot):
        if d.kind == "lab" and scope == "weekly":
            continue
        members = [e for e in world.department_members(d.id) if e.role in ("tipster", "researcher")
                   and e.status not in ("arriving", "away")]
        if not members:
            continue
        head = next((e for e in members if e.id == d.head_id), None)
        leads.append(head or max(members, key=lambda e: (e.level, e.psyche.reputation, e.id)))
    seen = {e.id for e in called}
    task = {"weekly": "Monday stand-up", "monthly": "Monthly review meeting"}.get(scope, "Meeting the new CEO")
    out: list[Employee] = []
    for e in called + [x for x in leads if x.id not in seen]:
        if len(out) >= 8:  # seats around the table
            break
        e.status, e.task = "meeting", ("Called in by the CEO" if e.id in seen else task)
        out.append(e)
    return out


# ---------------------------------------------------------------------------------- daily
def daily(world: World, rng: random.Random) -> None:
    """Called after settlement: arguments, celebrations, poaching offers, simmering resentment."""
    if world.ended:
        return
    _desk_moments(world, rng)
    _poaching(world, rng)
    _resentment(world, rng)


def _desk_moments(world: World, rng: random.Random) -> None:
    for dept in world.active_departments():
        if dept.kind == "lab" or _since(world, f"desk_moment:{dept.id}") < 7:
            continue
        people = [e for e in world.department_members(dept.id) if e.role == "tipster"]
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                ra = a.relationships.get(b.id)
                rb = b.relationships.get(a.id)
                if ra is None or rb is None:
                    continue
                rivalry = max(ra.rivalry, rb.rivalry)
                opposite = a.day_profit * b.day_profit < 0 and min(abs(a.day_profit), abs(b.day_profit)) >= 5
                temper = (a.traits.aggressive + b.traits.aggressive + a.traits.stubborn + b.traits.stubborn) / 4
                if rivalry >= 30 and opposite and rng.random() < 0.15 + 0.3 * temper:
                    winner, loser = (a, b) if a.day_profit > 0 else (b, a)
                    argue(world, rng, winner, loser, dept.id)
                    return
                friends = min(ra.trust, rb.trust) >= 70
                if friends and a.day_profit > 0 and b.day_profit > 0 and rng.random() < 0.3:
                    world.milestones[f"desk_moment:{dept.id}"] = _ord(world.today)
                    history.record(world, "high_five", f"{a.name} and {b.name} celebrate together",
                                   "A good day at the desk.", 1, "good", [a.id, b.id], dept.id,
                                   {"lines": {a.id: "Team work!", b.id: "Team work!"}})
                    return


def argue(world: World, rng: random.Random, winner: Employee, loser: Employee, dept_id: str | None,
          w_line: str | None = None) -> None:
    """A clash between two desk-mates: trust drops, rivalry and stress rise, everyone hears it."""
    w_line = w_line or rng.choice(WINNER_LINES)
    l_line = rng.choice(LOSER_LINES)
    rivalry = max(winner.relationships[loser.id].rivalry, loser.relationships[winner.id].rivalry)
    for x, y in ((winner, loser), (loser, winner)):
        rel = x.relationships[y.id]
        rel.trust = clamp(rel.trust - 5, 0, 100)
        rel.rivalry = clamp(rel.rivalry + 6, 0, 100)
        x.psyche.stress = clamp(x.psyche.stress + 0.04, 0.02, 0.98)
    world.stats.arguments += 1
    if dept_id:
        world.milestones[f"desk_moment:{dept_id}"] = _ord(world.today)
    dept = world.departments.get(dept_id or "")
    history.record(world, "argument", f"{winner.name} and {loser.name} clash at the {dept.name if dept else 'office'}",
                   f'{winner.name}: "{w_line}" — {loser.name}: "{l_line}"',
                   2 if rivalry >= 55 else 1, "drama", [winner.id, loser.id], dept_id,
                   {"lines": {winner.id: w_line, loser.id: l_line}})


def _is_star(world: World, e: Employee) -> metrics.PerfStats | None:
    if e.role != "tipster" or e.tenure_days(world.today) < 120 or e.psyche.reputation < 62:
        return None
    career = metrics.PerfStats.from_bets(metrics.settled_bets(world, e))
    return career if career.bets >= 120 and career.z >= 1.0 else None


def _poaching(world: World, rng: random.Random) -> None:
    distress = STATUS_DISTRESS.get(world.finances.status, 0.2)
    for e in sorted(world.tipsters(), key=lambda e: e.id):
        if _since(world, f"poach:{e.id}") < 120:
            continue
        p = 0.0035 * (1 + 1.5 * e.psyche.stress) * (1 + distress)
        if rng.random() >= p:
            continue
        career = _is_star(world, e)
        if career is None:
            continue
        rival = rng.choice(RIVAL_SYNDICATES)
        world.milestones[f"poach:{e.id}"] = _ord(world.today)
        world.stats.poach_offers += 1
        history.record(world, "poach_offer", f"{rival} tries to poach {e.name}",
                       f"Career ROI {career.roi:+.1%} over {career.bets} bets has been noticed.", 2, "drama",
                       [e.id], e.department_id, {"rival": rival})
        policy = PEOPLE_POLICY[_ceo_style(world)]
        raise_pct = policy["raise"]
        affordable = world.finances.cash > e.salary * raise_pct * 12
        willing = policy["counter"] * (1.0 if career.z >= 1.5 or _ceo_style(world) != "data_driven" else 0.4)
        if affordable and rng.random() < willing:
            e.salary = round(e.salary * (1 + raise_pct), 0)
            e.psyche.stress = clamp(e.psyche.stress - 0.05, 0.02, 0.98)
            e.psyche.reputation = clamp(e.psyche.reputation + 2, 0, 100)
            e.add_career(world.today, "raise", f"Counter-offer accepted: +{raise_pct:.0%} to stay.")
            history.record(world, "counter_offer", f"{e.name} stays after a {raise_pct:.0%} raise",
                           f"The CEO matched {rival}'s offer.", 2, "good", [e.id], e.department_id)
        elif rng.random() < 0.55 + 0.35 * e.traits.ambitious:
            world.stats.poached += 1
            management.depart(world, e, f"poached by {rival}", fired=False)
            history.record(world, "poached", f"{e.name} leaves for {rival}",
                           f"{e.title}, career P/L €{e.profit:+,.0f}. Nobody matched the offer.", 3, "bad",
                           [e.id], e.department_id, {"rival": rival})
        else:
            history.record(world, "loyal", f"{e.name} turns down {rival}", "Loyal, for now.", 1, "good",
                           [e.id], e.department_id)


def _resentment(world: World, rng: random.Random) -> None:
    """People refused a raise stay restless for a while."""
    for e in sorted(world.tipsters(), key=lambda e: e.id):
        if _since(world, f"denied:{e.id}") > 90:
            continue
        if rng.random() < 0.004 * (1 + e.traits.ambitious):
            management.depart(world, e, "quit after being denied a raise", fired=False)
            history.record(world, "resignation", f"{e.name} quits over pay",
                           "Denied a raise, and decided not to wait around.", 3, "drama", [e.id], e.department_id)


# ---------------------------------------------------------------------------------- monthly
def monthly(world: World, rng: random.Random) -> None:
    """Called on the 1st after the month close, before the CEO's monthly review."""
    if world.ended:
        return
    _board_review(world, rng)
    _raise_demands(world, rng)
    if world.today.month == 6:
        season_awards(world)


def _raise_demands(world: World, rng: random.Random) -> None:
    style = _ceo_style(world)
    policy = PEOPLE_POLICY[style]
    distress = world.finances.status == "distress"
    for e in sorted(world.tipsters(), key=lambda e: e.id):
        if e.under_review or e.tenure_days(world.today) < 150 or e.traits.ambitious < 0.45:
            continue
        if _since(world, f"raise:{e.id}") < 150 or any(
                c.kind in ("promoted", "raise") and (world.today - c.day).days < 150 for c in e.career):
            continue
        p90 = metrics.period_stats(world, e, 90)
        if p90.bets < 40 or p90.z < 1.2 or rng.random() > 0.5:
            continue
        world.milestones[f"raise:{e.id}"] = _ord(world.today)
        history.record(world, "raise_demand", f"{e.name} demands a raise",
                       f"ROI {p90.roi:+.1%} over the last {p90.bets} bets.", 2, "drama", [e.id], e.department_id)
        grant = policy["grant"] * (1.3 if p90.z >= 1.5 else 0.8)
        if distress and style != "aggressive_expansionist":
            grant *= 0.3
        if rng.random() < grant:
            e.salary = round(e.salary * 1.15, 0)
            e.psyche.stress = clamp(e.psyche.stress - 0.06, 0.02, 0.98)
            e.add_career(world.today, "raise", "Raise granted: +15%.")
            world.stats.raises_granted += 1
            history.record(world, "raise_granted", f"{e.name} gets a raise", "+15% salary.", 1, "good",
                           [e.id], e.department_id)
        else:
            e.psyche.stress = clamp(e.psyche.stress + 0.12, 0.02, 0.98)
            e.psyche.confidence = clamp(e.psyche.confidence - 0.03, 0.05, 0.95)
            rel = e.relationships.get(world.ceo().id)
            if rel:
                rel.trust = clamp(rel.trust - 15, 0, 100)
            e.add_career(world.today, "raise_refused", "Asked for a raise and was refused.")
            world.milestones[f"denied:{e.id}"] = _ord(world.today)
            world.stats.raises_refused += 1
            history.record(world, "raise_refused", f"{e.name}'s raise is refused", "Resentment builds.", 2, "bad",
                           [e.id], e.department_id)


def _board_review(world: World, rng: random.Random) -> None:
    """Investors fire a CEO who has wrecked the company. No money comes with the new one."""
    ceo = world.ceo()
    if world.clock.day_index < BOARD_MIN_DAYS or ceo.tenure_days(world.today) < BOARD_MIN_DAYS:
        return
    if _since(world, "board_fired") < 365:
        return
    value = val.valuation(world)
    capital = world.config.starting_capital
    collapsed = value < 0.45 * capital or (val.drawdown(world) >= 0.6 and world.finances.status in ("strained", "distress"))
    if not collapsed or rng.random() > 0.5:
        return
    old_style = ceo.ceo_style or world.config.ceo_style
    new_style = rng.choice([s for s in CEO_STYLES if s != old_style])
    history.record(world, "board_fires_ceo", f"The board fires CEO {ceo.name}",
                   f"Company value €{value:,.0f} ({value / capital - 1:+.0%} since founding). Investors lost patience.",
                   3, "bad", [ceo.id])
    replace_ceo(world, rng, new_style, "fired by the board")
    world.milestones["board_fired"] = _ord(world.today)


def replace_ceo(world: World, rng: random.Random, new_style: str, reason: str) -> Employee:
    """Out with the old CEO, in with a new one of the given style (who calls the team together)."""
    ceo = world.ceo()
    management.depart(world, ceo, reason, fired=True)
    new = hiring.make_ceo(world, rng, new_style)
    management.add_employee(world, rng, new)
    new.status, new.task = "meeting", "Meeting the team"
    gather_meeting(world, "new_ceo")
    world.config.ceo_style = new_style
    world.stats.ceo_changes += 1
    label = CEO_STYLE_INFO[new_style]["label"]
    history.record(world, "new_ceo", f"{new.name} takes over as CEO ({label})", CEO_STYLE_INFO[new_style]["description"],
                   3, "drama", [new.id])
    memo = (f"Team — I'm {new.name}. I've been asked to turn this around. I run things as a "
            f"{label.lower()}: {CEO_STYLE_INFO[new_style]['description'].lower()} Expect changes.")
    world.memos.append(Memo(time=world.clock.now, author_id=new.id, scope="monthly", text=memo))
    return new


# ---------------------------------------------------------------------------------- season awards
def season_awards(world: World) -> SeasonRecap | None:
    end = world.today - timedelta(days=1)
    start = date(end.year - 1, 7, 1)
    season = f"{start.year}/{(start.year + 1) % 100:02d}"
    if any(r.season == season for r in world.recaps):
        return None
    lo = max(start, world.config.start_date)
    bets = [b for b in world.bets.values() if b.status != "open" and b.settled and lo <= b.settled.date() <= end]
    if not bets:
        return None
    per: dict[str, list] = {}
    for b in bets:
        per.setdefault(b.employee_id, []).append(b)
    name = lambda eid: world.employees[eid].name if eid in world.employees else "?"
    stats = {eid: metrics.PerfStats.from_bets(bs) for eid, bs in per.items()}
    awards: list[Award] = []
    eligible = {eid: s for eid, s in stats.items() if s.bets >= 30}
    if eligible:
        mvp = max(eligible, key=lambda eid: eligible[eid].profit)
        awards.append(Award(title="MVP", name=name(mvp), employee_id=mvp, value=round(eligible[mvp].profit, 2),
                            text=f"€{eligible[mvp].profit:+,.0f} over {eligible[mvp].bets} bets"))
        flop = min(eligible, key=lambda eid: eligible[eid].profit)
        if flop != mvp:
            awards.append(Award(title="Flop of the season", name=name(flop), employee_id=flop,
                                value=round(eligible[flop].profit, 2),
                                text=f"€{eligible[flop].profit:+,.0f} over {eligible[flop].bets} bets"))
    sharp = {eid: s for eid, s in stats.items() if s.bets >= 60}
    if sharp:
        best = max(sharp, key=lambda eid: sharp[eid].roi)
        awards.append(Award(title="Sharpest", name=name(best), employee_id=best, value=round(sharp[best].roi, 4),
                            text=f"ROI {sharp[best].roi:+.1%} over {sharp[best].bets} bets"))
    top = max(bets, key=lambda b: b.profit)
    if top.profit > 0:
        awards.append(Award(title="Biggest win", name=name(top.employee_id), employee_id=top.employee_id,
                            value=round(top.profit, 2),
                            text=f"{top.selection} @ {top.odds} in {top.match_label} (+€{top.profit:,.0f})"))
    desk_profit: dict[str, float] = {}
    for b in bets:
        desk_profit[b.department_id] = desk_profit.get(b.department_id, 0.0) + b.profit
    if desk_profit:
        d = max(desk_profit, key=lambda k: desk_profit[k])
        awards.append(Award(title="Desk of the season", name=world.departments[d].name, value=round(desk_profit[d], 2),
                            text=f"€{desk_profit[d]:+,.0f}"))
    lab_ideas = [s for s in world.strategies.values() if s.origin == "lab" and s.live_bets >= 30]
    if lab_ideas:
        idea = max(lab_ideas, key=lambda s: s.live_roi)
        awards.append(Award(title="LAB idea of the season", name=idea.name, value=round(idea.live_roi, 4),
                            text=f"live ROI {idea.live_roi:+.1%} over {idea.live_bets} bets"))
    months = [r for r in world.monthly_reports if lo.strftime("%Y-%m") <= r.month <= end.strftime("%Y-%m")]
    points = [p for p in world.daily if p.day >= lo]
    kinds = [e.kind for e in world.events if lo <= e.time.date() <= end]
    recap = SeasonRecap(
        id=world.next_id("r"), season=season, created=world.today, awards=awards,
        net=round(sum(r.lines.net for r in months), 2), betting=round(sum(b.profit for b in bets), 2),
        value_start=points[0].valuation if points else world.config.starting_capital,
        value_end=round(val.valuation(world), 2), bets=len(bets), hires=kinds.count("hire"),
        fires=kinds.count("fire"), quits=kinds.count("resignation") + kinds.count("poached"),
    )
    change = recap.value_end - recap.value_start
    recap.headline = (f"Season {season}: company value {'up' if change >= 0 else 'down'} €{abs(change):,.0f}"
                      + (f", MVP {awards[0].name}" if awards and awards[0].title == "MVP" else ""))
    world.recaps.append(recap)
    history.record(world, "season_awards", f"Season {season} awards", recap.headline, 3, "good",
                   [awards[0].employee_id] if awards and awards[0].employee_id else [], data={"recap_id": recap.id})
    return recap

