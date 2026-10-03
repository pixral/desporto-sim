"""The simulation loop. One `step()` runs one phase of one simulated day.

    08:00 morning     month close / CEO reviews / sync fixtures, odds, news / LAB
    11:00 analysis    assign matches, run strategies, tipsters decide BET or NO_BET
    16:00 matches     kick-offs, closing prices, tipsters watch
    23:30 settlement  results, settlement, psychology, accounting, insolvency, milestones

The engine is decoupled from wall-clock time; the runner decides how fast steps happen.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from app.agents import management, prompts, psychology, relationships
from app.agents.context import (
    Leaning,
    MatchAnalysis,
    allocation_for,
    build_ceo_context,
    build_tipster_context,
    recent_layoffs,
    selection_label,
)
from app.agents.hiring import cleanup_candidate_strategies, generate_candidates
from app.ai.gateway import AICallRecord, AIGateway
from app.ai.provider import IAgentModelProvider
from app.ai.schemas import CEOReviewOutput, TipsterDayOutput
from app.analysis.index import SportsIndex
from app.analysis.models import candidates as strategy_candidates
from app.analysis.models import estimate_match
from app.domain.base import clamp
from app.domain.betting import Bet
from app.domain.events import ManagementLog, Memo
from app.domain.people import DecisionLog, Employee
from app.domain.world import World
from app.economy import accounting
from app.economy import valuation as val
from app.sports.provider import ISportsDataProvider

from . import history, lab, metrics
from .rng import dump_rng, load_rng
from .summary import build_summary

PHASES: list[tuple[str, time]] = [
    ("morning", time(8, 0)),
    ("analysis", time(11, 0)),
    ("matches", time(16, 0)),
    ("settlement", time(23, 30)),
]
MAX_MATCHES_PER_DAY = 6
MAX_BETS_BY_LEVEL = {0: 2, 1: 3, 2: 4, 3: 4}
DECISION_LOG_SIZE = 150
MATCH_RETENTION_DAYS = 450


class SimulationEngine:
    def __init__(self, world: World, sports: ISportsDataProvider, provider: IAgentModelProvider,
                 ai_sink: Callable[[AICallRecord], None] | None = None) -> None:
        self.world = world
        self.sports = sports
        self.rng = load_rng(world.rng_state, world.config.seed)
        self.index = SportsIndex(world.matches, world.news)
        self.popular = {t.id for t in world.teams.values() if t.popular}
        self.ai_sink = ai_sink
        self.gateway = AIGateway(provider, world.run_id, sink=self._on_ai_record)
        self.steps = 0

    # ------------------------------------------------------------------ public API
    @property
    def next_phase(self) -> str:
        return PHASES[self.world.clock.phase_index][0]

    async def step(self) -> str:
        w = self.world
        if w.ended:
            return "ended"
        name, t = PHASES[w.clock.phase_index]
        day = w.clock.now.date()
        if w.clock.phase_index == 0 and w.clock.now.time() > t:  # last step was the night settlement
            day += timedelta(days=1)
        w.clock.now = datetime.combine(day, t)
        await getattr(self, f"_{name}")()
        if w.clock.phase_index + 1 >= len(PHASES):
            # stay at 23:30 until the next step, so the night (and the day's results) are visible
            w.clock.phase_index = 0
            w.clock.day_index += 1
        else:
            w.clock.phase_index += 1
        w.rng_state = dump_rng(self.rng)
        self.steps += 1
        return name

    async def run_days(self, days: int) -> None:
        target = self.world.clock.day_index + days
        while self.world.clock.day_index < target and not self.world.ended:
            await self.step()

    def sync_provider_state(self) -> None:
        """Copy the sports provider's hidden state into the world before saving."""
        self.world.provider_state = self.sports.export_state()

    # ------------------------------------------------------------------ AI bookkeeping
    def _on_ai_record(self, rec: AICallRecord) -> None:
        s = self.world.ai_stats
        s.calls += 1
        s.failures += int(not rec.ok)
        s.retries += rec.retries
        s.input_tokens += rec.input_tokens
        s.output_tokens += rec.output_tokens
        s.cost_usd += rec.cost_usd
        p = s.by_purpose.setdefault(rec.purpose, {"calls": 0, "cost_usd": 0.0, "failures": 0})
        p["calls"] += 1
        p["cost_usd"] += rec.cost_usd
        p["failures"] += int(not rec.ok)
        accounting.charge_ai(self.world, rec.cost_usd)
        if self.ai_sink:
            self.ai_sink(rec)

    # ------------------------------------------------------------------ phases
    async def _morning(self) -> None:
        w = self.world
        d = w.today
        for e in w.employees.values():
            e.day_profit = 0.0
            if e.active:
                e.status, e.task = "idle", "Morning coffee"
        for dept in w.departments.values():
            dept.day_profit = 0.0
        if d.day == 1 and w.clock.day_index > 0:
            self._month_close(d - timedelta(days=1))
            if w.ended:
                return
        self._sync_sports()
        if d.day == 1 and w.clock.day_index > 0:
            lab.run_audit(w)
            self._refresh_candidates(force=True)
            lab.evaluate_candidates(w, self.index, self.popular)
            await self._ceo_review("monthly")
        elif d.weekday() == 0 and w.clock.day_index > 0:
            self._refresh_candidates(force=False)
            await self._ceo_review("weekly")
        await lab.lab_morning(w, self.index, self.popular, self.gateway, self.rng)
        ceo = w.ceo()
        if ceo.status == "idle":
            ceo.status, ceo.task = "ceo_office", "Reading the overnight numbers"

    async def _analysis(self) -> None:
        w = self.world
        today = w.today
        todays = sorted((m for m in w.matches.values()
                         if m.kickoff.date() == today and m.status == "scheduled" and m.odds),
                        key=lambda m: (m.kickoff, m.id))
        analyses: dict[str, list[MatchAnalysis]] = {}
        leanings: dict[str, list[Leaning]] = {}
        for emp in sorted(w.tipsters(), key=lambda e: e.id):
            dept = w.departments.get(emp.department_id or "")
            strat = w.strategies.get(emp.strategy_id or "")
            if dept is None or not dept.active or strat is None:
                emp.status, emp.task = "idle", "No desk or strategy"
                continue
            comps = set(dept.competitions)
            if strat.competitions:
                comps &= set(strat.competitions)
            relevant = [m for m in todays if m.competition in comps]
            rows: list[MatchAnalysis] = []
            for m in relevant:
                est = estimate_match(self.index, m, strat, w.clock.now, self.popular)
                cands = strategy_candidates(m, est, strat, self.popular)
                rows.append(MatchAnalysis(match=m, estimate=est, candidates=cands))
            rows.sort(key=lambda r: -max((c.edge for c in r.candidates if c.meets_strategy), default=-1.0))
            rows = rows[:MAX_MATCHES_PER_DAY]
            if not rows:
                emp.status, emp.task = "idle", "No matches today — on the bench"
                continue
            analyses[emp.id] = rows
            emp.status, emp.task = "analyzing", f"Analyzing {w.match_label(rows[0].match)}"
            for r in rows:
                best = next((c for c in r.candidates if c.meets_strategy), None)
                if best:
                    leanings.setdefault(r.match.id, []).append(
                        Leaning(employee_id=emp.id, market=best.market, edge=best.edge))
        if not analyses:
            return
        jobs = []
        order = sorted(analyses)
        for emp_id in order:
            emp = w.employees[emp_id]
            ctx = build_tipster_context(w, self.index, emp, analyses[emp_id], leanings,
                                        MAX_BETS_BY_LEVEL.get(emp.level, 3))
            jobs.append(self.gateway.run(
                purpose="tipster_day", agent_id=emp.id, agent_name=emp.name, sim_time=w.clock.now,
                system=prompts.tipster_system(ctx), user=prompts.tipster_user(ctx), context=ctx,
                output_model=TipsterDayOutput, seed=self.rng.randrange(1 << 30),
                fallback=lambda: TipsterDayOutput(thought="My screen froze. Sitting this one out.", decisions=[]),
            ))
        results = await asyncio.gather(*jobs)
        for emp_id, (out, rec) in zip(order, results):
            self._apply_tipster_day(w.employees[emp_id], analyses[emp_id], out, rec.ok)

    def _apply_tipster_day(self, emp: Employee, rows: list[MatchAnalysis], out: TipsterDayOutput, ok: bool) -> None:
        w = self.world
        dept = w.departments[emp.department_id or ""]
        by_id = {r.match.id: r for r in rows}
        seen: set[str] = set()
        bets_placed = 0
        max_bets = MAX_BETS_BY_LEVEL.get(emp.level, 3)
        coworker_ids = {e.name: e.id for e in w.active_employees()}
        for dec in out.decisions:
            row = by_id.get(dec.match_id)
            if row is None or dec.match_id in seen:
                continue
            seen.add(dec.match_id)
            m = row.match
            log = DecisionLog(time=w.clock.now, match_id=m.id, match_label=w.match_label(m), decision="NO_BET",
                              confidence=clamp(dec.confidence, 0, 1), reason=dec.reason[:400])
            if dec.decision == "BET":
                notes: list[str] = []
                best = m.best_price(dec.market) if dec.market else None
                allocation, max_stake = allocation_for(w, emp)
                stake = min(float(dec.stake or 0.0), max_stake, dept.bankroll)
                if dec.stake and dec.stake > max_stake + 0.01:
                    notes.append(f"stake {dec.stake:.2f} clamped to limit {max_stake:.2f}")
                if best is None:
                    notes.append("unknown market; treated as NO_BET")
                elif bets_placed >= max_bets:
                    notes.append("daily bet limit reached; treated as NO_BET")
                elif stake < 1.0:
                    notes.append("stake below €1; treated as NO_BET")
                else:
                    book, price = best
                    if dec.odds and abs(dec.odds - price) / price > 0.03:
                        notes.append(f"quoted {dec.odds:.2f}, booked at best available {price:.2f}")
                    cand = next((c for c in row.candidates if c.market == dec.market), None)
                    infl = [coworker_ids[n] for n in dec.influenced_by if n in coworker_ids and coworker_ids[n] != emp.id]
                    bet = Bet(
                        id=w.next_id("b"), placed=w.clock.now, employee_id=emp.id, department_id=dept.id,
                        match_id=m.id, match_label=w.match_label(m), competition=m.competition,
                        market=dec.market, selection=selection_label(w, m, dec.market), book=book, odds=price,
                        stake=round(stake, 2), confidence=log.confidence,
                        model_prob=round(cand.prob, 4) if cand else None,
                        model_edge=round(cand.edge, 4) if cand else None,
                        strategy_id=emp.strategy_id, reason=dec.reason[:400], influenced_by=infl,
                    )
                    accounting.register_bet(w, bet)
                    bets_placed += 1
                    log.decision, log.market, log.selection = "BET", bet.market, bet.selection
                    log.odds, log.stake, log.bet_id = bet.odds, bet.stake, bet.id
                    log.model_edge = bet.model_edge
                    log.influenced_by = [w.employees[i].name for i in infl]
                    # memorable punts only (a maxed-out stake on a longshot, or a moonshot), at most weekly per person
                    memorable = (bet.stake >= 0.95 * max_stake and max_stake >= 20 and bet.odds >= 4.5) or bet.odds >= 8.0
                    last = w.milestones.get(f"swing:{emp.id}", 0)
                    if memorable and w.today.toordinal() - int(last) >= 7:
                        w.milestones[f"swing:{emp.id}"] = w.today.toordinal()
                        history.record(w, "big_swing", f"{emp.name} swings big: €{bet.stake:.0f} on {bet.selection} @ {bet.odds}",
                                       bet.reason, 1, "drama", [emp.id], dept.id)
                log.notes = notes
            if log.decision == "NO_BET":
                w.stats.no_bets += 1
            emp.no_bet_flags.append(1 if log.decision == "NO_BET" else 0)
            emp.decisions.append(log)
        emp.no_bet_flags = emp.no_bet_flags[-40:]
        emp.decisions = emp.decisions[-DECISION_LOG_SIZE:]
        emp.thought = out.thought[:240]
        if bets_placed:
            emp.status, emp.task = "working", f"Placed {bets_placed} bet(s) for today"
        else:
            emp.status, emp.task = ("idle", "Passed on every match today") if ok else ("stressed", "AI call failed")

    async def _matches(self) -> None:
        w = self.world
        today_ids = [m.id for m in w.matches.values() if m.kickoff.date() == w.today and m.status != "finished"]
        snaps = self.sports.odds(today_ids, w.clock.now)
        for mid in today_ids:
            m = w.matches[mid]
            snap = snaps.get(mid)
            if snap and snap.close:
                m.odds_close = snap.close
            if m.kickoff <= w.clock.now:
                m.status = "live"
        open_by_emp: dict[str, int] = {}
        for bid in w.open_bet_ids:
            b = w.bets[bid]
            open_by_emp[b.employee_id] = open_by_emp.get(b.employee_id, 0) + 1
        for e in w.tipsters():
            n = open_by_emp.get(e.id, 0)
            if n:
                e.status, e.task = "watching", f"Watching {n} open bet(s)"
            elif e.status != "stressed":
                e.status, e.task = "idle", "Taking a break"
        ceo = w.ceo()
        if ceo.status not in ("meeting",):
            ceo.status, ceo.task = "ceo_office", "Reviewing desk exposure"

    async def _settlement(self) -> None:
        w = self.world
        now = w.clock.now
        pending = [m.id for m in w.matches.values() if m.status != "finished" and m.kickoff <= now]
        results = self.sports.results(pending, now)
        snaps = self.sports.odds(pending, now)
        for mid, res in results.items():
            m = w.matches[mid]
            m.home_goals, m.away_goals = res.home_goals, res.away_goals
            m.home_xg, m.away_xg, m.note = res.home_xg, res.away_xg, res.note
            m.status = "finished"
            snap = snaps.get(mid)
            if snap and snap.close:
                m.odds_close = snap.close
            self.index.add_finished(m)
        status_before = w.finances.status
        for bid in list(w.open_bet_ids):
            bet = w.bets[bid]
            m = w.matches.get(bet.match_id)
            if m is None or not m.finished:
                continue
            close = m.best_price(bet.market, "odds_close")
            bet.closing_odds = close[1] if close else None
            bet.score = f"{m.home_goals}-{m.away_goals}"
            accounting.settle_bet(w, bet, bet.market in m.winning_markets(), now)
            emp = w.employees[bet.employee_id]
            _, max_stake = allocation_for(w, emp)
            psychology.on_bet_settled(emp, bet, max_stake or bet.stake)
            if bet.influenced_by:
                relationships.on_influenced_bet(w, emp, bet)
            big = 0.01 * w.config.starting_capital
            if bet.status == "won" and (bet.profit >= big or (bet.odds >= 6.0 and bet.profit >= big / 3)):
                history.record(w, "big_win", f"{emp.name} lands {bet.selection} @ {bet.odds} (+€{bet.profit:.0f})",
                               f"{bet.match_label} finished {bet.score}.", 2 if bet.profit >= 2 * big else 1, "good",
                               [emp.id], bet.department_id)
        day_pnl = sum(d.day_profit for d in w.departments.values())
        self._daily_people()
        accounting.accrue_daily_costs(w)
        for note in accounting.ensure_liquidity(w):
            history.record(w, "liquidity", note, "", 2, "bad")
        w.finances.status = val.company_status(w)
        value = val.valuation(w)
        accounting.record_daily_point(w, day_pnl)
        history.after_day(w, value, status_before, w.finances.status, day_pnl)
        self._check_insolvency()
        self._prune()

    # ------------------------------------------------------------------ helpers
    def _daily_people(self) -> None:
        w = self.world
        distress = psychology.STATUS_DISTRESS.get(w.finances.status, 0.2)
        thriving = w.finances.status == "thriving"
        layoffs = recent_layoffs(w)
        for e in sorted(w.active_employees(), key=lambda e: e.id):
            if e.role == "tipster":
                recent = metrics.recent_stats(w, e, 50)
                dept = w.departments.get(e.department_id or "")
                psychology.daily_update(e, psychology.DayContext(
                    distress=distress, company_thriving=thriving,
                    dept_month_profit=dept.month_profit if dept else 0.0, recent_layoffs=layoffs,
                    recent_roi=recent.roi, recent_bets=recent.bets, day_profit=e.day_profit))
                if e.day_profit:
                    e.pnl_flash_seq += 1
                    e.status = "celebrating" if e.day_profit > 0 else "frustrated"
                    e.task = f"Day P/L €{e.day_profit:+.2f}"
                if e.psyche.stress > 0.75:
                    e.status = "stressed"
            elif e.role == "researcher":
                psychology.researcher_daily_update(e, distress, w.finances.lab_budget / 60.0)
            e.series.append([w.clock.day_index, round(e.profit, 2), round(e.psyche.reputation, 1),
                             round(e.psyche.stress, 3), round(e.psyche.confidence, 3)])
            if len(e.series) > 1500:
                e.series = e.series[-1500:]
            if e.role != "ceo":
                reason = psychology.resignation_reason(w, e, distress, self.rng)
                if reason:
                    management.depart(w, e, reason, fired=False)
                    history.record(w, "resignation", f"{e.name} quits", f"{e.name} {reason}.",
                                   3 if e.psyche.reputation >= 65 else 2, "drama", [e.id], e.department_id)

    def _sync_sports(self) -> None:
        w = self.world
        now = w.clock.now
        for m in self.sports.fixtures(w.today, w.today + timedelta(days=7), now):
            if m.id not in w.matches:
                w.matches[m.id] = m
        ids = [m.id for m in w.matches.values()
               if m.status == "scheduled" and w.today <= m.kickoff.date() <= w.today + timedelta(days=7)]
        for mid, snap in self.sports.odds(ids, now).items():
            m = w.matches[mid]
            if snap.open:
                m.odds_open = snap.open
            if snap.current:
                m.odds = snap.current
        since = datetime.fromisoformat(w.milestones.get("last_news_sync", (now - timedelta(days=1)).isoformat()))
        for n in self.sports.news(since, now):
            w.news.append(n)
            self.index.add_news(n)
        w.milestones["last_news_sync"] = now.isoformat()

    def _refresh_candidates(self, force: bool) -> None:
        w = self.world
        before = {c.id for c in w.candidates}
        w.candidates = [c for c in w.candidates if c.expires > w.today]
        target = 5 if w.config.ceo_style == "data_driven" else 4
        if force or len(w.candidates) < 2:
            kinds = [d.kind for d in w.active_departments()]
            w.candidates.extend(generate_candidates(w, self.rng, max(0, target - len(w.candidates)), kinds))
        if before != {c.id for c in w.candidates}:
            cleanup_candidate_strategies(w, set())

    async def _ceo_review(self, scope: str) -> None:
        w = self.world
        ceo = w.ceo()
        ctx = build_ceo_context(w, scope)
        out, rec = await self.gateway.run(
            purpose="ceo_review", agent_id=ceo.id, agent_name=ceo.name, sim_time=w.clock.now,
            system=prompts.ceo_system(ctx), user=prompts.ceo_user(ctx), context=ctx, output_model=CEOReviewOutput,
            seed=self.rng.randrange(1 << 30),
            fallback=lambda: CEOReviewOutput(thought="(no decision — the AI call failed)", memo="", actions=[]),
        )
        records = management.apply_actions(w, self.rng, out.actions, scope)
        w.management_log.append(ManagementLog(time=w.clock.now, scope=scope, thought=out.thought, memo=out.memo,
                                              actions=records))
        w.management_log = w.management_log[-120:]
        ceo.thought = out.thought[:240]
        ceo.status, ceo.task = "meeting", f"{scope.capitalize()} review"
        if out.memo.strip():
            w.memos.append(Memo(time=w.clock.now, author_id=ceo.id, scope=scope, text=out.memo.strip()[:800]))
            w.memos = w.memos[-60:]
            history.record(w, "memo", f"CEO memo ({scope})", out.memo.strip()[:800], 1, "neutral", [ceo.id])
        touched = {a.params.get("employee_id") for a in records if a.applied}
        for e in w.active_employees():
            if e.id in touched and e.role != "ceo":
                e.status, e.task = "meeting", "Called into the CEO's office"
        if scope == "monthly":
            cleanup_candidate_strategies(w, set())

    def _month_close(self, last_day: date) -> None:
        w = self.world
        month = metrics.month_key(last_day)
        perf_roi, perf_bets = {}, {}
        for e in w.active_employees():
            p = metrics.period_stats(w, e, 90)
            perf_roi[e.id], perf_bets[e.id] = p.roi, p.bets
        report = accounting.monthly_close(w, month)
        for note in accounting.ensure_liquidity(w):
            history.record(w, "liquidity", note, "", 2, "bad")
        w.milestones["months_since_salary_cut"] = int(w.milestones.get("months_since_salary_cut", 99)) + 1
        relationships.monthly_update(w, perf_roi, perf_bets)
        ceo = w.ceo()
        net = report.lines.net
        ceo.psyche.confidence = clamp(ceo.psyche.confidence + (0.06 if net > 0 else -0.05), 0.05, 0.95)
        ceo.psyche.stress = clamp(ceo.psyche.stress + (-0.05 if net > 0 else 0.07), 0.02, 0.98)
        label = last_day.strftime("%B %Y")
        history.record(w, "month_close", f"{label} closed: net €{net:+,.0f}",
                       f"Betting €{report.lines.betting_pnl:+,.0f}, subscriptions €{report.lines.subscriptions:,.0f}, "
                       f"costs €{report.lines.expenses:,.0f}. {report.subscribers} subscribers.",
                       1, "good" if net >= 0 else "bad", data={"month": month})
        history.after_month_close(w, net, label, report.valuation)
        if w.finances.cash < 0:
            self._bankrupt(f"Could not make payroll at the end of {label}.")

    def _check_insolvency(self) -> None:
        w = self.world
        if w.ended:
            return
        if val.equity(w) <= 0:
            self._bankrupt("Liabilities exceed assets: the company is insolvent.")
        elif w.finances.cash < 0:
            self._bankrupt("Out of cash with no bankroll or credit left to cover obligations.")
        elif not w.tipsters() and not w.candidates and metrics.bankroll_total(w) < 50:
            self._bankrupt("No tipsters, no bankroll, no way to operate.")

    def _bankrupt(self, reason: str) -> None:
        w = self.world
        w.ended = True
        w.end_reason = reason
        w.finances.status = "bankrupt"
        for e in w.active_employees():
            e.status, e.task = "leaving", "The lights are going out"
            e.thought = "Well. That's that."
        history.record(w, "bankruptcy", f"{w.config.company_name} is bankrupt", reason, 3, "bad")
        w.summary = build_summary(w)

    def _prune(self) -> None:
        w = self.world
        if w.clock.day_index % 30 != 0:
            return
        cutoff = datetime.combine(w.today - timedelta(days=MATCH_RETENTION_DAYS), time(0, 0))
        old = [mid for mid, m in w.matches.items() if m.finished and m.kickoff < cutoff]
        for mid in old:
            del w.matches[mid]
        if old:
            self.index = SportsIndex(w.matches, w.news)
        news_cut = datetime.combine(w.today - timedelta(days=90), time(0, 0))
        w.news = [n for n in w.news if n.published >= news_cut]
        history.prune(w)

