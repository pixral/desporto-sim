"""Founding a company: the initial world for a new run."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, time, timedelta

from app.agents import hiring, management
from app.agents.catalog import DEPARTMENT_KINDS
from app.domain.company import Finances
from app.domain.world import ClockState, RunConfig, World
from app.economy import config as EC
from app.economy import valuation as val
from app.sports.provider import ISportsDataProvider

from . import city, history
from .rng import dump_rng

INITIAL_DESKS = ["germany", "england", "europe", "markets"]
INITIAL_SPECIALTIES = {
    "germany": ["bundesliga", "form"],
    "england": ["premier_league", "statistical"],
    "europe": ["champions_league", "la_liga"],
    "markets": ["market", "contrarian"],
}


def agent_rng(seed: int) -> random.Random:
    return random.Random(seed * 1_000_003 + 11)


def create_world(config: RunConfig, sports: ISportsDataProvider) -> World:
    start = config.start_date
    finances = Finances(
        cash=config.starting_capital * (1 - EC.BANKROLL_SHARE),
        subscribers=int(EC.preset(config.difficulty)["start_subs"]),
        subscription_price=EC.SUBSCRIPTION_PRICE,
        marketing_budget=EC.DEFAULT_MARKETING,
        lab_budget=EC.DEFAULT_LAB_BUDGET,
    )
    world = World(run_id=uuid.uuid4().hex[:12], config=config,
                  clock=ClockState(now=datetime.combine(start, time(7, 0))), finances=finances)
    rng = agent_rng(config.seed)

    world.competitions = {c.code: c for c in sports.competitions()}
    world.teams = {t.id: t for t in sports.teams()}
    for m in sports.bootstrap_history(start):
        world.matches[m.id] = m
    world.news = sports.news(datetime.combine(start - timedelta(days=60), time(0, 0)),
                             datetime.combine(start, time(7, 0)))
    world.milestones["last_news_sync"] = datetime.combine(start, time(7, 0)).isoformat()
    world.milestones["months_since_salary_cut"] = 99

    ceo = hiring.make_ceo(world, rng, config.ceo_style)
    if config.player_ceo and config.player_name.strip():
        ceo.name = config.player_name.strip()[:40]  # the player; the same seed still founds the same company
    world.employees[ceo.id] = ceo

    bankroll_each = config.starting_capital * EC.BANKROLL_SHARE / len(INITIAL_DESKS)
    desks = {kind: management.create_department(world, kind, bankroll_each) for kind in INITIAL_DESKS}
    lab = management.create_department(world, "lab", 0.0)

    plan: list[tuple[str, str]] = []
    queues = {k: list(v) for k, v in INITIAL_SPECIALTIES.items()}
    i = 0
    while len(plan) < config.initial_tipsters:
        kind = INITIAL_DESKS[i % len(INITIAL_DESKS)]
        q = queues[kind]
        specialty = q.pop(0) if q else rng.choice(DEPARTMENT_KINDS[kind].specialties)
        plan.append((kind, specialty))
        i += 1
    for kind, specialty in plan:
        level = rng.choices((0, 1, 2), weights=(0.25, 0.55, 0.2))[0]
        emp = hiring.make_tipster(world, rng, specialty, desks[kind].id, level=level)
        management.add_employee(world, rng, emp)
        emp.status, emp.task = "idle", "Setting up their desk"
    researcher = hiring.make_researcher(world, rng, "quant_research", lab.id)
    management.add_employee(world, rng, researcher)
    for e in world.active_employees():
        e.status = "idle"
    world.stats.hired = len(world.active_employees()) - 1
    world.candidates = hiring.generate_candidates(world, rng, 4)
    city.ensure_city(world)  # the city's market, with some price history
    world.finances.peak_value = val.valuation(world)
    world.milestones["founding_value"] = round(world.finances.peak_value, 2)
    world.finances.peak_value_day = start
    history.record(world, "founded", f"{config.company_name} founded",
                   f"CEO {ceo.name} opens the doors with €{config.starting_capital:,.0f}, "
                   f"{config.initial_tipsters} tipsters and a one-person LAB.", 3, "good", [ceo.id])
    world.rng_state = dump_rng(rng)
    return world
