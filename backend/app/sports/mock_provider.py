"""A self-contained football world: believable fixtures, odds, news and results.

Hidden "truth" (team quality, latent form, injuries, league goal levels) drives results.
Three fictional bookmakers price matches from *imperfect* views of that truth:

* they track latent form with a lag (the soft book lags most),
* they price team news only partially until kick-off,
* they shade prices towards popular clubs (popularity bias drifts per league),
* they carry a margin that hits longshots hardest,
* their league goal-level estimate lags the true level (over/under inefficiency).

That is where edges can exist — small, noisy and drifting, so strategies can work for a while
and then stop working. Analysts never see the truth; only results, odds and news.

The provider owns its own RNG stream, so a given seed always produces the same football
regardless of what the company does.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, time, timedelta
from typing import Any, NamedTuple

from pydantic import Field

from app.analysis.poisson import outcome_probs, sample_poisson
from app.domain.base import Model, clamp
from app.domain.sports import MATCH_DURATION_MINUTES, CompetitionInfo, Match, OddsLine, Team, TeamNews

from .pricing import price
from .provider import MatchResult, OddsSnapshot
from .schedule import (
    double_round_robin,
    league_anchor_dates,
    spread_kickoffs,
    ucl_knockout_dates,
    ucl_league_dates,
    ucl_league_phase,
)
from .teams_data import CLUBS, COMPETITIONS, COUNTRY, DOMESTIC_LEAGUES, LEAGUE_BASE_GOALS, UCL_QUOTA

HOME_ADV = 0.22
RATING_SCALE = 0.014
FORM_DECAY = 0.92
FORM_NOISE = 0.055
INJURY_RATE = 0.011
INJURY_EFFECT = 0.08  # per severity point, on the log goal rate
ODDS_OPEN_DAYS = 6
XG_NOISE = 0.22


class BookProfile(NamedTuple):
    name: str
    margin: float
    ou_margin: float
    k_rating: float  # how strongly each result moves the book's team ratings
    xg_use: float  # share of expected goals (vs goals) in the book's rating updates
    phi_day: float  # share of known injury impact priced in on matchday
    pop_factor: float  # how much popularity bias leaks into this book's prices
    noise: float  # random pricing error (log-probability scale)
    mu_rate: float  # weekly learning rate of league goal levels
    rating_err_sd: float  # start-of-season misjudgement of team quality
    copy_sharp: float  # share of the price copied from the sharp book (soft books follow the market)


# Books rate teams from results (the sharp one leans on expected goals), price injuries only
# partially, shade towards popular clubs and copy part of the sharp line.
BOOKS: tuple[BookProfile, ...] = (
    BookProfile("Atlas", 0.040, 0.045, 0.08, 0.60, 0.70, 0.2, 0.007, 0.08, 0.025, 0.0),
    BookProfile("Nordbet", 0.055, 0.060, 0.07, 0.35, 0.50, 0.6, 0.011, 0.06, 0.035, 0.65),
    BookProfile("Kicko", 0.070, 0.075, 0.06, 0.15, 0.30, 1.0, 0.018, 0.04, 0.045, 0.55),
)

_PLAYERS = (
    "Almeida", "Novak", "Schreiber", "Okafor", "Lindqvist", "Moreau", "Petrović", "Kaya", "Haddad",
    "Brennan", "Duarte", "Kowalski", "Rossetti", "Varga", "Iversen", "Mbeki", "Castells", "Hoffmann",
    "Takahashi", "Delacroix", "Ferreira", "Nyström", "Barros", "Ilić", "Quintero", "Abara", "Weiss",
    "Laurent", "Sandoval", "Kranjčar", "Osei", "Vidal", "Engström", "Marchetti", "Ruiz", "Doumbia",
    "Halvorsen", "Pereira", "Zieliński", "Arnaud", "Tchouaméni-Kahn", "Bellucci", "Sørensen", "Yilmaz",
)


class Injury(Model):
    news_id: str
    att: float = 0.0
    deff: float = 0.0
    start: date
    until: date
    player: str


class TeamTruth(Model):
    att: float
    deff: float
    form: float = 0.0
    injuries: list[Injury] = Field(default_factory=list)


class BookState(Model):
    xg_use: float | None = None  # current reliance on expected goals (drifts each season)
    att: dict[str, float] = Field(default_factory=dict)
    deff: dict[str, float] = Field(default_factory=dict)
    prior_att: dict[str, float] = Field(default_factory=dict)
    prior_def: dict[str, float] = Field(default_factory=dict)
    mu_est: dict[str, float] = Field(default_factory=dict)


class UclState(Model):
    year: int
    season: str
    stage: str = "league"  # league, r16, qf, sf, final, done
    participants: list[str] = Field(default_factory=list)
    table: dict[str, list[int]] = Field(default_factory=dict)  # team -> [pts, gd, gf]
    ties: list[list[Any]] = Field(default_factory=list)  # [a, b, [match ids]]
    champion: str | None = None


class MockState(Model):
    seed: int
    rng_state: list[Any] = Field(default_factory=list)
    processed_through: date | None = None
    truth: dict[str, TeamTruth] = Field(default_factory=dict)
    books: dict[str, BookState] = Field(default_factory=dict)
    pop_bias: dict[str, float] = Field(default_factory=dict)
    mu: dict[str, float] = Field(default_factory=dict)
    schedule: dict[str, Match] = Field(default_factory=dict)
    open_at: dict[str, datetime] = Field(default_factory=dict)
    news: list[TeamNews] = Field(default_factory=list)
    tables: dict[str, dict[str, list[int]]] = Field(default_factory=dict)  # "2026:BL1" -> team -> [pts,gd,gf,played]
    counters: dict[str, int] = Field(default_factory=dict)
    ucl: UclState | None = None


def _rng_dump(rng: random.Random) -> list[Any]:
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _rng_load(state: list[Any]) -> random.Random:
    rng = random.Random()
    rng.setstate((state[0], tuple(state[1]), state[2]))
    return rng


def season_label(year: int) -> str:
    return f"{year}/{(year + 1) % 100:02d}"


def season_year_for(d: date) -> int:
    return d.year if d.month >= 7 else d.year - 1


class MockSportsDataProvider:
    name = "mock"

    def __init__(self, seed: int = 7) -> None:
        self._teams: dict[str, Team] = {}
        self._strength: dict[str, int] = {}
        for comp, clubs in CLUBS.items():
            for tid, name, short, strength, popular in clubs:
                self._teams[tid] = Team(id=tid, name=name, short=short, competition=comp,
                                        country=COUNTRY[comp], popular=popular)
                self._strength[tid] = strength
        self.state = MockState(seed=seed)
        self.rng = random.Random(seed * 7919 + 17)
        self._by_day: dict[date, list[str]] = {}
        self._init_truth()

    # ------------------------------------------------------------------ interface
    def competitions(self) -> list[CompetitionInfo]:
        return list(COMPETITIONS.values())

    def teams(self) -> list[Team]:
        return [t.model_copy() for t in self._teams.values()]

    def bootstrap_history(self, start: date) -> list[Match]:
        year = season_year_for(start)
        history: list[Match] = []
        first_day = date(year - 1, 7, 1)
        if self.state.processed_through is None:
            self.state.processed_through = first_day - timedelta(days=1)
        d = self.state.processed_through + timedelta(days=1)
        while d < start:
            history.extend(self._process_day(d))
            d += timedelta(days=1)
        return [m.model_copy(deep=True) for m in history]

    def fixtures(self, start: date, end: date, as_of: datetime) -> list[Match]:
        self._advance(as_of)
        out = []
        for m in self.state.schedule.values():
            if start <= m.kickoff.date() <= end and m.status == "scheduled":
                out.append(Match(id=m.id, competition=m.competition, season=m.season, stage=m.stage,
                                 home_id=m.home_id, away_id=m.away_id, kickoff=m.kickoff, neutral=m.neutral))
        out.sort(key=lambda m: (m.kickoff, m.id))
        return out

    def odds(self, match_ids: list[str], as_of: datetime) -> dict[str, OddsSnapshot]:
        self._advance(as_of)
        out: dict[str, OddsSnapshot] = {}
        for mid in match_ids:
            m = self.state.schedule.get(mid)
            if m is None:
                continue
            snap = OddsSnapshot()
            if m.odds_open and as_of >= self.state.open_at.get(mid, m.kickoff):
                snap.open = {k: v.model_copy() for k, v in m.odds_open.items()}
            if m.odds and as_of >= datetime.combine(m.kickoff.date(), time(8, 0)):
                snap.current = {k: v.model_copy() for k, v in m.odds.items()}
            if m.odds_close and as_of >= m.kickoff:
                snap.close = {k: v.model_copy() for k, v in m.odds_close.items()}
            out[mid] = snap
        return out

    def results(self, match_ids: list[str], as_of: datetime) -> dict[str, MatchResult]:
        self._advance(as_of)
        out: dict[str, MatchResult] = {}
        for mid in match_ids:
            m = self.state.schedule.get(mid)
            if m is None or m.home_goals is None:
                continue
            if as_of >= m.kickoff + timedelta(minutes=MATCH_DURATION_MINUTES):
                out[mid] = MatchResult(home_goals=m.home_goals, away_goals=m.away_goals or 0,
                                       home_xg=m.home_xg, away_xg=m.away_xg, note=m.note)
        return out

    def news(self, since: datetime, as_of: datetime) -> list[TeamNews]:
        self._advance(as_of)
        return [n.model_copy() for n in self.state.news if since < n.published <= as_of]

    def export_state(self) -> dict[str, Any]:
        self.state.rng_state = _rng_dump(self.rng)
        return self.state.model_dump(mode="json")

    def import_state(self, state: dict[str, Any]) -> None:
        self.state = MockState.model_validate(state)
        self.rng = _rng_load(self.state.rng_state)
        self._rebuild_day_index()

    # ------------------------------------------------------------------ world setup
    def _init_truth(self) -> None:
        rng = self.rng
        for tid, s in self._strength.items():
            self.state.truth[tid] = TeamTruth(
                att=(s + rng.gauss(0, 2.5) - 75) * RATING_SCALE,
                deff=(s + rng.gauss(0, 2.5) - 75) * RATING_SCALE,
            )
        for comp, base in LEAGUE_BASE_GOALS.items():
            self.state.mu[comp] = math.log(base)
            self.state.pop_bias[comp] = clamp(rng.uniform(0.005, 0.025), 0.0, 0.03)
        for book in BOOKS:
            bs = BookState()
            for comp in LEAGUE_BASE_GOALS:
                bs.mu_est[comp] = self.state.mu[comp] + rng.gauss(0, 0.02)
            self.state.books[book.name] = bs
            self._preseason_book(book, bs)

    def _preseason_book(self, book: BookProfile, bs: BookState) -> None:
        """Books know squad quality reasonably well before a season, but not form."""
        for tid, truth in self.state.truth.items():
            err = self.rng.gauss(0, book.rating_err_sd)
            bs.prior_att[tid] = truth.att + err
            bs.prior_def[tid] = truth.deff + 0.5 * err
            bs.att[tid] = bs.prior_att[tid]
            bs.deff[tid] = bs.prior_def[tid]

    def _next(self, key: str) -> int:
        n = self.state.counters.get(key, 0) + 1
        self.state.counters[key] = n
        return n

    def _rebuild_day_index(self) -> None:
        self._by_day = {}
        for m in self.state.schedule.values():
            self._by_day.setdefault(m.kickoff.date(), []).append(m.id)

    def _add_match(self, comp: str, year: int, stage: str, home: str, away: str, kickoff: datetime,
                   neutral: bool = False) -> Match:
        mid = f"{comp}-{year}-{self._next(f'm:{comp}:{year}'):04d}"
        m = Match(id=mid, competition=comp, season=season_label(year), stage=stage, home_id=home,
                  away_id=away, kickoff=kickoff, neutral=neutral)
        self.state.schedule[mid] = m
        self._by_day.setdefault(kickoff.date(), []).append(mid)
        return m

    # ------------------------------------------------------------------ seasons
    def _generate_season(self, year: int) -> None:
        rng = self.rng
        first_season = not self.state.tables
        if not first_season:
            for tid, t in self.state.truth.items():
                t.att += rng.gauss(0, 0.035)
                t.deff += rng.gauss(0, 0.035)
                t.form *= 0.4
            for book in BOOKS:
                bs = self.state.books[book.name]
                # The market slowly (and unevenly) changes how much it trusts expected goals,
                # so xG-based edges wax and wane over seasons.
                current = book.xg_use if bs.xg_use is None else bs.xg_use
                bs.xg_use = clamp(current + rng.gauss(0.03, 0.12), 0.0, 0.95)
                self._preseason_book(book, bs)
        ucl_days = ucl_league_dates(year)
        blocked = set(ucl_days) | {d + timedelta(days=1) for d in ucl_days}
        for comp in DOMESTIC_LEAGUES:
            team_ids = [t for t, team in self._teams.items() if team.competition == comp]
            rounds = double_round_robin(team_ids, rng)
            anchors = league_anchor_dates(comp, year, len(rounds), blocked)
            self.state.tables[f"{year}:{comp}"] = {t: [0, 0, 0, 0] for t in team_ids}
            for r, (anchor, pairs) in enumerate(zip(anchors, rounds)):
                for home, away, ko in spread_kickoffs(comp, anchor, pairs, rng):
                    self._add_match(comp, year, f"Matchday {r + 1}", home, away, ko)
        participants = self._ucl_participants(year)
        pairings = ucl_league_phase(participants, rng)
        for md, (tuesday, pairs) in enumerate(zip(ucl_days, pairings)):
            for i, (home, away) in enumerate(pairs):
                day = tuesday if i % 2 == 0 else tuesday + timedelta(days=1)
                hm = time(18, 45) if i % 9 == 0 else time(21, 0)
                self._add_match("UCL", year, f"League phase MD{md + 1}", home, away, datetime.combine(day, hm))
        self.state.ucl = UclState(year=year, season=season_label(year), participants=participants,
                                  table={t: [0, 0, 0] for t in participants})

    def _ucl_participants(self, year: int) -> list[str]:
        chosen: list[str] = []
        for comp, quota in UCL_QUOTA.items():
            table = self.state.tables.get(f"{year - 1}:{comp}")
            team_ids = [t for t, team in self._teams.items() if team.competition == comp]
            if table:
                ranked = sorted(team_ids, key=lambda t: (-table[t][0], -table[t][1], -table[t][2]))
            else:
                ranked = sorted(team_ids, key=lambda t: -self._strength[t])
            chosen.extend(ranked[:quota])
        chosen.extend(t for t, team in self._teams.items() if team.competition == "OTHER")
        return chosen

    # ------------------------------------------------------------------ time
    def _advance(self, as_of: datetime) -> None:
        target = as_of.date()
        if self.state.processed_through is None:
            # Always simulate from the start of the season so the calendar is complete.
            self.state.processed_through = date(season_year_for(target), 7, 1) - timedelta(days=1)
        d = self.state.processed_through + timedelta(days=1)
        while d <= target:
            self._process_day(d)
            d += timedelta(days=1)

    def _process_day(self, d: date) -> list[Match]:
        rng = self.rng
        if d.month == 7 and d.day == 1:
            self._generate_season(d.year)
        morning = datetime.combine(d, time(7, 0))
        self._expire_injuries(d, morning)
        self._generate_news(d, morning)
        if d.weekday() == 0:
            self._weekly_drift()
        open_time = datetime.combine(d, time(8, 0))
        for offset in range(1, ODDS_OPEN_DAYS + 1):
            for mid in self._by_day.get(d + timedelta(days=offset), []):
                m = self.state.schedule.get(mid)
                if m and not m.odds_open:
                    m.odds_open = self._price(m, "open", d)
                    self.state.open_at[mid] = open_time
        todays = [self.state.schedule[mid] for mid in self._by_day.get(d, []) if mid in self.state.schedule]
        todays.sort(key=lambda m: (m.kickoff, m.id))
        for m in todays:
            if not m.odds_open:
                m.odds_open = self._price(m, "open", d)
                self.state.open_at[m.id] = open_time
            m.odds = self._price(m, "day", d)
        finished: list[Match] = []
        for m in todays:
            if m.status == "finished":
                continue
            m.odds_close = self._price(m, "close", d)
            self._play(m, d, rng)
            finished.append(m)
        self._ucl_progress(d)
        self._prune(d)
        self.state.processed_through = d
        return finished

    def _prune(self, d: date) -> None:
        cutoff = d - timedelta(days=14)
        keep = {mid for tie in self.state.ucl.ties for mid in tie[2]} if self.state.ucl else set()
        stale = [mid for mid, m in self.state.schedule.items()
                 if m.status == "finished" and m.kickoff.date() < cutoff and mid not in keep]
        for mid in stale:
            m = self.state.schedule.pop(mid)
            self.state.open_at.pop(mid, None)
            day_list = self._by_day.get(m.kickoff.date())
            if day_list and mid in day_list:
                day_list.remove(mid)
        news_cutoff = datetime.combine(d - timedelta(days=60), time(0, 0))
        self.state.news = [n for n in self.state.news if n.published >= news_cutoff]

    def _weekly_drift(self) -> None:
        rng = self.rng
        for comp in LEAGUE_BASE_GOALS:
            base = math.log(LEAGUE_BASE_GOALS[comp])
            mu = self.state.mu[comp] + rng.gauss(0, 0.02)
            self.state.mu[comp] = clamp(mu + 0.03 * (base - mu), base - 0.15, base + 0.15)
            self.state.pop_bias[comp] = clamp(self.state.pop_bias[comp] + rng.gauss(0, 0.003), 0.0, 0.03)
            for book in BOOKS:
                bs = self.state.books[book.name]
                bs.mu_est[comp] += book.mu_rate * (self.state.mu[comp] - bs.mu_est[comp]) + rng.gauss(0, 0.004)

    # ------------------------------------------------------------------ news
    def _active_teams(self, d: date) -> list[str]:
        active: set[str] = set()
        for offset in range(0, 11):
            for mid in self._by_day.get(d + timedelta(days=offset), []):
                m = self.state.schedule.get(mid)
                if m:
                    active.add(m.home_id)
                    active.add(m.away_id)
        return sorted(active)

    def _publish(self, team_id: str, when: datetime, expires: date, kind: str, severity: int, headline: str) -> TeamNews:
        news = TeamNews(id=f"n{self._next('news')}", team_id=team_id, published=when, expires=expires,
                        kind=kind, severity=severity, headline=headline)  # type: ignore[arg-type]
        self.state.news.append(news)
        return news

    def _generate_news(self, d: date, when: datetime) -> None:
        rng = self.rng
        for tid in self._active_teams(d):
            truth = self.state.truth[tid]
            name = self._teams[tid].short
            u = rng.random()
            if u < INJURY_RATE:
                severity = rng.choices((1, 2, 3), weights=(0.5, 0.35, 0.15))[0]
                attack = rng.random() < 0.55
                suspension = severity <= 2 and rng.random() < 0.2
                days = 7 if suspension else 6 + 9 * severity + rng.randint(0, 14)
                until = d + timedelta(days=days)
                player = rng.choice(_PLAYERS)
                weeks = max(1, round(days / 7))
                if suspension:
                    headline = f"{name}'s {player} suspended after a red card"
                elif attack:
                    headline = [
                        f"{name}: forward {player} picks up a knock, out for about {weeks} week(s)",
                        f"{name} lose top scorer {player} for around {weeks} weeks",
                        f"Blow for {name}: star striker {player} ruled out for {weeks} weeks",
                    ][severity - 1]
                else:
                    headline = [
                        f"{name} defender {player} sidelined with a minor injury",
                        f"{name} without first-choice centre-back {player} for {weeks} weeks",
                        f"{name} goalkeeper {player} out long-term ({weeks} weeks)",
                    ][severity - 1]
                kind = "injury_attack" if attack else "injury_defense"
                news = self._publish(tid, when, until, kind, severity, headline)
                effect = -INJURY_EFFECT * severity
                truth.injuries.append(Injury(news_id=news.id, att=effect if attack else 0.0,
                                             deff=0.0 if attack else effect, start=d, until=until, player=player))
            elif truth.form < -0.17 and u < INJURY_RATE + 0.012:
                self._publish(tid, when, d + timedelta(days=28), "manager_change", 2,
                              f"{name} sack their manager after a dismal run; new coach appointed")
                truth.form = truth.form * 0.3 + 0.06

    def _expire_injuries(self, d: date, when: datetime) -> None:
        for tid, truth in self.state.truth.items():
            remaining = []
            for inj in truth.injuries:
                if inj.until <= d:
                    self._publish(tid, when, d, "return", 1,
                                  f"{self._teams[tid].short}: {inj.player} back in full training")
                else:
                    remaining.append(inj)
            truth.injuries = remaining

    # ------------------------------------------------------------------ pricing & results
    def _rating(self, tid: str, book: BookProfile | None, phase: str) -> tuple[float, float]:
        t = self.state.truth[tid]
        inj_att = sum(i.att for i in t.injuries)
        inj_def = sum(i.deff for i in t.injuries)
        if book is None:
            return t.att + t.form + inj_att, t.deff + 0.6 * t.form + inj_def
        bs = self.state.books[book.name]
        att, deff = bs.att[tid], bs.deff[tid]
        if phase == "close":  # informed money moves the closing line towards reality
            att += 0.3 * (t.att + t.form - att)
            deff += 0.3 * (t.deff + 0.6 * t.form - deff)
        phi = {"open": 0.6 * book.phi_day, "day": book.phi_day, "close": min(1.0, book.phi_day + 0.2)}[phase]
        return att + phi * inj_att, deff + phi * inj_def

    def _lambdas(self, m: Match, book: BookProfile | None, phase: str) -> tuple[float, float]:
        mu = self.state.mu[m.competition] if book is None else self.state.books[book.name].mu_est[m.competition]
        ah, dh = self._rating(m.home_id, book, phase)
        aa, da = self._rating(m.away_id, book, phase)
        h = 0.0 if m.neutral else HOME_ADV
        return math.exp(mu + h / 2 + ah - da), math.exp(mu - h / 2 + aa - dh)

    def _price(self, m: Match, phase: str, d: date) -> dict[str, OddsLine]:
        rng = self.rng
        lines: dict[str, OddsLine] = {}
        home_pop = self._teams[m.home_id].popular
        away_pop = self._teams[m.away_id].popular
        sharp: tuple[float, float, float, float] | None = None
        for book in BOOKS:
            lam_h, lam_a = self._lambdas(m, book, phase)
            own = outcome_probs(lam_h, lam_a)
            if sharp is None:
                sharp = own
            w = book.copy_sharp
            p1, px, p2, pov = (w * s_ + (1 - w) * o_ for s_, o_ in zip(sharp, own))
            shade = self.state.pop_bias[m.competition] * book.pop_factor
            if home_pop and not away_pop:
                take = min(shade, (px + p2) * 0.5)
                p1, px, p2 = p1 + take, px - take * px / (px + p2), p2 - take * p2 / (px + p2)
            elif away_pop and not home_pop:
                take = min(shade, (px + p1) * 0.5)
                p2, px, p1 = p2 + take, px - take * px / (px + p1), p1 - take * p1 / (px + p1)
            noise = book.noise * (0.6 if phase == "close" else 1.0)
            probs = [p * math.exp(rng.gauss(0, noise)) for p in (p1, px, p2)]
            s = sum(probs)
            probs = [p / s for p in probs]
            pov = clamp(pov * math.exp(rng.gauss(0, noise)), 0.05, 0.95)
            h, dr, a = price(probs, book.margin)
            ov, un = price([pov, 1.0 - pov], book.ou_margin)
            lines[book.name] = OddsLine(home_win=h, draw=dr, away_win=a, over_2_5=ov, under_2_5=un)
        return lines

    def _play(self, m: Match, d: date, rng: random.Random) -> None:
        lam_h, lam_a = self._lambdas(m, None, "day")
        book_view = {book.name: self._lambdas(m, book, "day") for book in BOOKS}
        hg = sample_poisson(lam_h, rng.random())
        ag = sample_poisson(lam_a, rng.random())
        m.home_goals, m.away_goals, m.status = hg, ag, "finished"
        # Expected goals: a noisy but much less noisy view of the true scoring rates than goals.
        m.home_xg = round(lam_h * math.exp(rng.gauss(0, XG_NOISE)), 2)
        m.away_xg = round(lam_a * math.exp(rng.gauss(0, XG_NOISE)), 2)
        for book in BOOKS:
            self._book_learn(book, m, *book_view[book.name])
        for tid in (m.home_id, m.away_id):
            t = self.state.truth[tid]
            t.form = FORM_DECAY * t.form + rng.gauss(0, FORM_NOISE)
        year = int(m.id.split("-")[1])
        if m.competition in DOMESTIC_LEAGUES:
            table = self.state.tables.get(f"{year}:{m.competition}")
            if table is not None:
                self._table_update(table, m.home_id, m.away_id, hg, ag)
        elif m.competition == "UCL" and self.state.ucl and m.stage.startswith("League"):
            self._table_update(self.state.ucl.table, m.home_id, m.away_id, hg, ag)

    def _book_learn(self, book: BookProfile, m: Match, exp_h: float, exp_a: float) -> None:
        bs = self.state.books[book.name]
        xu = book.xg_use if bs.xg_use is None else bs.xg_use
        obs_h = (1 - xu) * (m.home_goals or 0) + xu * (m.home_xg or 0.0)
        obs_a = (1 - xu) * (m.away_goals or 0) + xu * (m.away_xg or 0.0)
        # Linear (unbiased) residuals; a log residual would drift ratings down via Jensen's inequality.
        r_h = (obs_h - exp_h) / (exp_h + 0.3)
        r_a = (obs_a - exp_a) / (exp_a + 0.3)
        # Update the rate *multiplier* (1 + k*r) so the expected change in lambda is ~zero.
        k = 1.8 * book.k_rating
        h, a = m.home_id, m.away_id
        bs.att[h] += math.log1p(0.55 * k * r_h)
        bs.deff[a] -= math.log1p(0.45 * k * r_h)
        bs.att[a] += math.log1p(0.55 * k * r_a)
        bs.deff[h] -= math.log1p(0.45 * k * r_a)
        for tid in (h, a):
            bs.att[tid] += 0.015 * (bs.prior_att[tid] - bs.att[tid])
            bs.deff[tid] += 0.015 * (bs.prior_def[tid] - bs.deff[tid])

    @staticmethod
    def _table_update(table: dict[str, list[int]], home: str, away: str, hg: int, ag: int) -> None:
        for tid, gf, ga in ((home, hg, ag), (away, ag, hg)):
            row = table.setdefault(tid, [0, 0, 0, 0])
            row[0] += 3 if gf > ga else 1 if gf == ga else 0
            row[1] += gf - ga
            row[2] += gf
            if len(row) > 3:
                row[3] += 1

    # ------------------------------------------------------------------ Champions League knockouts
    def _ucl_progress(self, d: date) -> None:
        ucl = self.state.ucl
        if ucl is None or ucl.stage == "done":
            return
        ucl_matches = [m for m in self.state.schedule.values()
                       if m.competition == "UCL" and m.season == ucl.season]
        if ucl.stage == "league":
            league = [m for m in ucl_matches if m.stage.startswith("League")]
            if league and all(m.finished for m in league) and max(m.kickoff.date() for m in league) <= d:
                ranked = sorted(ucl.participants,
                                key=lambda t: (-ucl.table[t][0], -ucl.table[t][1], -ucl.table[t][2], t))
                seeds = ranked[:16]
                order = [(0, 15), (7, 8), (4, 11), (3, 12), (2, 13), (5, 10), (6, 9), (1, 14)]
                self._schedule_ties(ucl, "r16", [(seeds[a], seeds[b]) for a, b in order])
            return
        stage_matches = {mid for tie in ucl.ties for mid in tie[2]}
        if not stage_matches:
            return
        played = [self.state.schedule.get(mid) for mid in stage_matches]
        if any(m is None or not m.finished for m in played):
            return
        winners = [self._tie_winner(tie) for tie in ucl.ties]
        nxt = {"r16": "qf", "qf": "sf", "sf": "final", "final": "done"}[ucl.stage]
        if nxt == "done":
            ucl.champion = winners[0]
            ucl.stage = "done"
            ucl.ties = []
            return
        self._schedule_ties(ucl, nxt, [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)])

    def _tie_winner(self, tie: list[Any]) -> str:
        a, b, mids = tie
        goals = {a: 0, b: 0}
        last: Match | None = None
        for mid in mids:
            m = self.state.schedule[mid]
            goals[m.home_id] += m.home_goals or 0
            goals[m.away_id] += m.away_goals or 0
            last = m
        if goals[a] != goals[b]:
            return a if goals[a] > goals[b] else b
        winner = a if self.rng.random() < 0.5 else b
        if last is not None:
            last.note = f"{self._teams[winner].short} win on penalties"
        return winner

    def _schedule_ties(self, ucl: UclState, stage: str, pairs: list[tuple[str, str]]) -> None:
        labels = {"r16": "Round of 16", "qf": "Quarter-final", "sf": "Semi-final", "final": "Final"}
        dates = ucl_knockout_dates(ucl.year, stage)
        ucl.ties = []
        for i, (higher, lower) in enumerate(pairs):
            mids: list[str] = []
            if stage == "final":
                ko = datetime.combine(dates[0], time(21, 0))
                mids.append(self._add_match("UCL", ucl.year, labels[stage], higher, lower, ko, neutral=True).id)
            else:
                for leg, tuesday in enumerate(dates):
                    day = tuesday if i % 2 == 0 else tuesday + timedelta(days=1)
                    home, away = (lower, higher) if leg == 0 else (higher, lower)
                    ko = datetime.combine(day, time(21, 0))
                    mids.append(self._add_match("UCL", ucl.year, f"{labels[stage]} · leg {leg + 1}",
                                                home, away, ko).id)
            ucl.ties.append([higher, lower, mids])
        ucl.stage = stage
