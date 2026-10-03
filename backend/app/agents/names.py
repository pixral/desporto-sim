"""Names, appearances and personalities for new agents."""

from __future__ import annotations

import random

from app.domain.base import clamp
from app.domain.people import Appearance, Traits

FIRST_NAMES = (
    "Marta", "Lucas", "Sofia", "Tiago", "Inês", "Jonas", "Amara", "Kenji", "Lena", "Mateo", "Noor", "Ravi",
    "Freya", "Diego", "Yara", "Oskar", "Elif", "Bruno", "Chiara", "Kofi", "Hana", "Pablo", "Ingrid", "Samir",
    "Leila", "Viktor", "Ana", "Malik", "Greta", "Rui", "Zara", "Emil", "Bea", "Tomás", "Mei", "Felix",
    "Aisha", "Hugo", "Nadia", "Joaquín", "Saoirse", "Ibrahim", "Clara", "Mikkel", "Lucía", "Arjun", "Wanda",
    "Nico", "Esra", "Dario", "Maja", "Tobias", "Rosa", "Kai", "Ayumi", "Lars", "Paula", "Idris", "Vera",
    "Gustavo", "Milena", "Otto", "Selin", "Andrés", "Thea", "Yusuf", "Carla", "Henrik", "Luz", "Matteo",
    "Anouk", "Rafael", "Sigrid", "Omar", "Elena", "Bastian", "Imani", "Jakub", "Pilar", "Dmitri", "Ines",
    "Sven", "Lola", "Kwame", "Astrid", "Marco", "Valentina", "Ezra", "Nina", "Joel", "Farah", "Iker",
    "Linnea", "Cosmo", "Dalia", "Ruben", "Mira", "August", "Soraya", "Leon", "Beatriz", "Anton", "Kira",
)

CEO_NAMES = ("Augusto", "Helena", "Bernardo", "Victoria", "Cassius", "Regina", "Maximilian", "Odette")


def unique_name(rng: random.Random, taken: set[str], pool: tuple[str, ...] = FIRST_NAMES) -> str:
    free = [n for n in pool if n not in taken]
    if free:
        return rng.choice(free)
    base = rng.choice(pool)
    i = 2
    while f"{base} {i}" in taken:
        i += 1
    return f"{base} {i}"


def random_appearance(rng: random.Random) -> Appearance:
    return Appearance(
        skin=rng.randrange(6),
        hair_style=rng.randrange(7),
        hair_color=rng.randrange(7),
        shirt=rng.randrange(8),
        pants=rng.randrange(5),
        accessory=rng.choices(range(5), weights=(5, 2, 2, 1, 1))[0],
    )


def random_traits(rng: random.Random, bias: dict[str, float] | None = None) -> Traits:
    def b() -> float:
        return rng.betavariate(2.0, 2.0)

    cautious = b()
    collaborative = b()
    t = Traits(
        cautious=cautious,
        analytical=b(),
        aggressive=clamp(b() * 0.7 + (1 - cautious) * 0.3, 0, 1),
        ambitious=b(),
        stubborn=b(),
        collaborative=collaborative,
        independent=clamp(1 - collaborative + rng.gauss(0, 0.18), 0, 1),
        risk_seeking=clamp(1 - cautious + rng.gauss(0, 0.2), 0, 1),
        skeptical=b(),
    )
    for name, delta in (bias or {}).items():
        setattr(t, name, clamp(getattr(t, name) + delta, 0.0, 1.0))
    return t
