"""Creating people and their personal strategies. True talent is hidden in strategy parameters."""

from __future__ import annotations

import random
from datetime import timedelta

from app.domain.base import clamp
from app.domain.people import Candidate, Employee, Psyche, Relationship, Traits
from app.domain.strategy import PARAM_BOUNDS, Strategy
from app.domain.world import World

from .catalog import (
    CEO_SALARY,
    DEPARTMENT_KINDS,
    LEVEL_BANKROLL_WEIGHT,
    LEVEL_SALARY,
    RESEARCHER_SALARY,
    SPECIALTIES,
    TIPSTER_TITLES,
)
from .names import CEO_NAMES, random_appearance, random_traits, unique_name

_XG_RANGE = {"statistical": (0.35, 1.0), "goals": (0.2, 1.0), "form": (0.0, 0.85)}


def _clamp_param(name: str, value: float) -> float:
    lo, hi = PARAM_BOUNDS[name]
    return clamp(value, lo, hi)


def personal_strategy(world: World, rng: random.Random, specialty: str, owner_name: str,
                      origin: str = "default") -> Strategy:
    """The specialty's template with personal quirks. Some quirks are genuinely good, most are not."""
    spec = SPECIALTIES[specialty]
    p = dict(spec.params)
    s = Strategy(id=world.next_id("s"), name=f"{owner_name}'s {spec.label.split(' (')[0].lower()} model",
                 origin=origin, created=world.today, competitions=list(spec.competitions), **p)
    if s.model_weight > 0.05:
        lo, hi = _XG_RANGE.get(specialty, (0.0, 0.9))
        s.xg_weight = round(rng.uniform(lo, hi), 2)
        s.model_weight = _clamp_param("model_weight", s.model_weight + rng.gauss(0, 0.1))
        s.half_life = round(_clamp_param("half_life", s.half_life * rng.uniform(0.6, 1.7)), 1)
        s.window = int(_clamp_param("window", round(s.window * rng.uniform(0.7, 1.35))))
        s.news_weight = round(_clamp_param("news_weight", s.news_weight * rng.uniform(0.5, 1.4)), 2)
    s.min_edge = round(_clamp_param("min_edge", s.min_edge * rng.uniform(0.7, 1.4)), 3)
    s.kelly_fraction = round(_clamp_param("kelly_fraction", s.kelly_fraction * rng.uniform(0.7, 1.3)), 2)
    world.strategies[s.id] = s
    return s


def _initial_psyche(rng: random.Random, traits: Traits, reputation: float = 50.0) -> Psyche:
    return Psyche(
        stress=clamp(0.2 + rng.gauss(0, 0.05), 0.05, 0.5),
        confidence=clamp(0.45 + 0.2 * traits.aggressive - 0.1 * traits.cautious + rng.gauss(0, 0.06), 0.2, 0.8),
        risk_tolerance=clamp(0.2 + 0.4 * traits.risk_seeking + 0.2 * traits.aggressive - 0.2 * traits.cautious, 0.05, 0.9),
        reputation=reputation,
    )


def _taken_names(world: World) -> set[str]:
    return {e.name for e in world.employees.values() if e.active} | {c.name for c in world.candidates}


def make_tipster(world: World, rng: random.Random, specialty: str, department_id: str | None,
                 level: int = 1, name: str | None = None, traits: Traits | None = None,
                 strategy_id: str | None = None, salary: float | None = None) -> Employee:
    name = name or unique_name(rng, _taken_names(world))
    traits = traits or random_traits(rng)
    if strategy_id is None:
        strategy_id = personal_strategy(world, rng, specialty, name).id
    emp = Employee(
        id=world.next_id("e"),
        name=name,
        role="tipster",
        title=TIPSTER_TITLES[level],
        level=level,
        specialty=specialty,
        department_id=department_id,
        traits=traits,
        psyche=_initial_psyche(rng, traits),
        appearance=random_appearance(rng),
        salary=salary if salary is not None else LEVEL_SALARY[level],
        hired=world.today,
        strategy_id=strategy_id,
        bankroll_weight=LEVEL_BANKROLL_WEIGHT[level],
    )
    emp.add_career(world.today, "hired", f"Joined as {emp.title} ({SPECIALTIES[specialty].label}).")
    return emp


def make_researcher(world: World, rng: random.Random, specialty: str, department_id: str | None,
                    name: str | None = None, traits: Traits | None = None, salary: float | None = None) -> Employee:
    name = name or unique_name(rng, _taken_names(world))
    traits = traits or random_traits(rng, {"analytical": 0.15})
    emp = Employee(
        id=world.next_id("e"),
        name=name,
        role="researcher",
        title="Researcher",
        level=1,
        specialty=specialty,
        department_id=department_id,
        traits=traits,
        psyche=_initial_psyche(rng, traits),
        appearance=random_appearance(rng),
        salary=salary if salary is not None else RESEARCHER_SALARY,
        hired=world.today,
    )
    emp.add_career(world.today, "hired", f"Joined the LAB as {SPECIALTIES[specialty].label}.")
    return emp


def make_ceo(world: World, rng: random.Random, style: str) -> Employee:
    bias = {
        "conservative_operator": {"cautious": 0.3, "risk_seeking": -0.3, "analytical": 0.1},
        "aggressive_expansionist": {"aggressive": 0.3, "ambitious": 0.3, "risk_seeking": 0.25, "cautious": -0.25},
        "data_driven": {"analytical": 0.35, "skeptical": 0.2, "stubborn": -0.15},
        "chaotic_founder": {"stubborn": 0.2, "aggressive": 0.2, "analytical": -0.25, "ambitious": 0.25},
    }[style]
    traits = random_traits(rng, bias)
    emp = Employee(
        id=world.next_id("e"),
        name=unique_name(rng, _taken_names(world), CEO_NAMES),
        role="ceo",
        title="CEO",
        level=4,
        specialty="management",
        traits=traits,
        psyche=_initial_psyche(rng, traits, reputation=60.0),
        appearance=random_appearance(rng),
        salary=CEO_SALARY,
        hired=world.today,
        ceo_style=style,
    )
    emp.add_career(world.today, "hired", "Founded the company.")
    return emp


def seed_relationships(world: World, rng: random.Random, emp: Employee) -> None:
    """Initial impressions both ways with every active colleague."""
    for other in world.active_employees():
        if other.id == emp.id:
            continue
        same = other.department_id is not None and other.department_id == emp.department_id
        for a, b in ((emp, other), (other, emp)):
            if b.id in a.relationships:
                continue
            base_trust = 50 + (8 if same else 0) + 10 * (a.traits.collaborative - 0.5) + rng.gauss(0, 8)
            a.relationships[b.id] = Relationship(
                trust=clamp(base_trust, 10, 90),
                respect=clamp(50 + rng.gauss(0, 6), 20, 80),
                rivalry=clamp((12 if same else 2) + 15 * (a.traits.ambitious - 0.5) + rng.gauss(0, 5), 0, 60),
            )


def generate_candidates(world: World, rng: random.Random, count: int, kinds: list[str] | None = None) -> list[Candidate]:
    """Applicants. CV ratings correlate only weakly with how good their methods really are."""
    pool_specialties: list[str] = []
    for kind in kinds or [d.kind for d in world.active_departments()]:
        dk = DEPARTMENT_KINDS.get(kind)
        if dk:
            pool_specialties.extend(dk.specialties)
    if not pool_specialties:
        pool_specialties = [k for k, s in SPECIALTIES.items() if s.role == "tipster"]
    out: list[Candidate] = []
    taken = _taken_names(world)
    for _ in range(count):
        specialty = rng.choice(pool_specialties)
        role = SPECIALTIES[specialty].role
        name = unique_name(rng, taken)
        taken.add(name)
        traits = random_traits(rng)
        strategy_id = None
        quality_hint = 0.5
        if role == "tipster":
            strat = personal_strategy(world, rng, specialty, name, origin="hire")
            strategy_id = strat.id
            quality_hint = strat.xg_weight
        experience = rng.randint(0, 12)
        cv = int(clamp(45 + rng.gauss(0, 15) + 18 * (quality_hint - 0.5) + experience * 1.2, 5, 98))
        base = RESEARCHER_SALARY if role == "researcher" else LEVEL_SALARY[1]
        salary_ask = round(base * (0.75 + cv / 160 + rng.uniform(-0.05, 0.1)), 0)
        pitch = rng.choice([
            "Has a spreadsheet for everything.",
            "Claims to have beaten the closing line for three seasons.",
            "Ex-scout with strong opinions about pressing intensity.",
            "Self-taught modeller, very online.",
            "Former trader, talks about variance a lot.",
            "Quiet, meticulous, hates long shots.",
            "Built their own expected-goals model in a weekend.",
            "Watches every match, trusts their eyes over numbers.",
        ])
        out.append(Candidate(
            id=world.next_id("c"), name=name, role=role, specialty=specialty, traits=traits,
            appearance=random_appearance(rng), cv_rating=cv, experience_years=experience,
            salary_ask=salary_ask, strategy_id=strategy_id, pitch=pitch,
            expires=world.today + timedelta(days=35),
        ))
    return out


def hire_candidate(world: World, rng: random.Random, cand: Candidate, department_id: str) -> Employee:
    if cand.role == "researcher":
        emp = make_researcher(world, rng, cand.specialty, department_id, name=cand.name,
                              traits=cand.traits, salary=cand.salary_ask)
    else:
        level = 0 if cand.experience_years < 2 else 1
        emp = make_tipster(world, rng, cand.specialty, department_id, level=level, name=cand.name,
                           traits=cand.traits, strategy_id=cand.strategy_id, salary=cand.salary_ask)
    emp.appearance = cand.appearance
    if cand.strategy_id and cand.strategy_id in world.strategies:
        world.strategies[cand.strategy_id].author_id = emp.id
        world.strategies[cand.strategy_id].name = f"{emp.name}'s {SPECIALTIES[cand.specialty].label.split(' (')[0].lower()} model"
    return emp


def cleanup_candidate_strategies(world: World, keep: set[str]) -> None:
    """Drop strategies created for applicants who were never hired."""
    used = {e.strategy_id for e in world.employees.values() if e.strategy_id}
    for c in world.candidates:
        if c.strategy_id:
            used.add(c.strategy_id)
    used |= keep
    for sid in [sid for sid, s in world.strategies.items() if s.origin == "hire" and sid not in used]:
        del world.strategies[sid]
