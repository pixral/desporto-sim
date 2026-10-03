from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import Field

from .base import Model
from .betting import Bet
from .company import DailyPoint, Department, Finances, MonthlyReport
from .events import HistoryEvent, ManagementLog, Memo
from .lab import AuditFinding, Experiment
from .people import Candidate, Employee
from .sports import CompetitionInfo, Match, Team, TeamNews
from .strategy import Strategy

CEO_STYLES: tuple[str, ...] = (
    "conservative_operator",
    "aggressive_expansionist",
    "data_driven",
    "chaotic_founder",
)


class RunConfig(Model):
    company_name: str = "Desporto & Cia."
    ceo_style: str = "data_driven"
    seed: int = 7
    start_date: date = date(2026, 8, 14)
    starting_capital: float = 20000.0
    initial_tipsters: int = 8
    difficulty: str = "normal"
    sports_provider: str = "mock"
    ai_provider: str = "mock"


class ClockState(Model):
    now: datetime
    phase_index: int = 0  # index of the NEXT phase to run
    day_index: int = 0  # days since founding


class RunStats(Model):
    hired: int = 0
    fired: int = 0
    resigned: int = 0
    promotions: int = 0
    departments_created: int = 0
    departments_closed: int = 0
    strategies_invented: int = 0
    strategies_deployed: int = 0
    experiments_run: int = 0
    bets_placed: int = 0
    no_bets: int = 0
    longest_company_losing_days: int = 0
    current_company_losing_days: int = 0
    salary_cuts: int = 0
    loans_taken: int = 0


class AIStats(Model):
    calls: int = 0
    failures: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    by_purpose: dict[str, dict[str, float]] = Field(default_factory=dict)


class RunSummary(Model):
    company_name: str
    ceo_name: str
    ceo_style: str
    ended: bool
    end_reason: str | None
    founded: date
    last_day: date
    days_survived: int
    starting_capital: float
    peak_value: float
    peak_value_day: date | None
    final_value: float
    worst_drawdown: float
    employees_hired: int
    employees_fired: int
    employees_resigned: int
    bets_placed: int
    no_bet_decisions: int
    betting_profit: float
    total_expenses: float
    best_employee: str | None
    best_employee_profit: float | None
    worst_employee: str | None
    worst_employee_profit: float | None
    departments_created: int
    departments_closed: int
    strategies_invented: int
    ai_cost_usd: float
    ai_calls: int


class World(Model):
    """The complete simulation state. Serializing this object is a save game."""

    version: int = 1
    run_id: str
    config: RunConfig
    clock: ClockState
    competitions: dict[str, CompetitionInfo] = Field(default_factory=dict)
    teams: dict[str, Team] = Field(default_factory=dict)
    matches: dict[str, Match] = Field(default_factory=dict)
    news: list[TeamNews] = Field(default_factory=list)
    employees: dict[str, Employee] = Field(default_factory=dict)
    departments: dict[str, Department] = Field(default_factory=dict)
    strategies: dict[str, Strategy] = Field(default_factory=dict)
    bets: dict[str, Bet] = Field(default_factory=dict)
    open_bet_ids: list[str] = Field(default_factory=list)
    experiments: dict[str, Experiment] = Field(default_factory=dict)
    audit_findings: list[AuditFinding] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    finances: Finances
    monthly_reports: list[MonthlyReport] = Field(default_factory=list)
    daily: list[DailyPoint] = Field(default_factory=list)
    events: list[HistoryEvent] = Field(default_factory=list)
    memos: list[Memo] = Field(default_factory=list)
    management_log: list[ManagementLog] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)
    milestones: dict[str, Any] = Field(default_factory=dict)
    stats: RunStats = Field(default_factory=RunStats)
    ai_stats: AIStats = Field(default_factory=AIStats)
    rng_state: list[Any] = Field(default_factory=list)
    provider_state: dict[str, Any] = Field(default_factory=dict)
    ended: bool = False
    end_reason: str | None = None
    summary: RunSummary | None = None

    # ---- helpers -------------------------------------------------------------------------
    def next_id(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        return f"{prefix}{n}"

    @property
    def today(self) -> date:
        return self.clock.now.date()

    def active_employees(self, role: str | None = None) -> list[Employee]:
        return [
            e for e in self.employees.values() if e.active and (role is None or e.role == role)
        ]

    def tipsters(self) -> list[Employee]:
        return self.active_employees("tipster")

    def ceo(self) -> Employee:
        for e in self.employees.values():
            if e.role == "ceo" and e.active:
                return e
        raise LookupError("company has no CEO")

    def active_departments(self) -> list[Department]:
        return [d for d in self.departments.values() if d.active]

    def department_members(self, dept_id: str) -> list[Employee]:
        return [e for e in self.employees.values() if e.active and e.department_id == dept_id]

    def team_name(self, team_id: str) -> str:
        team = self.teams.get(team_id)
        return team.name if team else team_id

    def match_label(self, match: Match) -> str:
        return f"{self.team_name(match.home_id)} vs {self.team_name(match.away_id)}"
