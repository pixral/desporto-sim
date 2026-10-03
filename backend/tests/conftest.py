from __future__ import annotations

import pytest

from app.ai.mock_provider import MockAgentModelProvider
from app.domain.world import RunConfig
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_world
from app.sports.mock_provider import MockSportsDataProvider


def build(style: str = "data_driven", seed: int = 3, capital: float = 20000.0, **kw):
    sports = MockSportsDataProvider(seed=seed)
    world = create_world(RunConfig(ceo_style=style, seed=seed, starting_capital=capital, **kw), sports)
    engine = SimulationEngine(world, sports, MockAgentModelProvider())
    return world, sports, engine


@pytest.fixture
def fresh():
    return build


@pytest.fixture(scope="session")
def bootstrapped():
    """A provider that has simulated one prior season, plus its finished matches (read-only use)."""
    from datetime import date

    sports = MockSportsDataProvider(seed=5)
    history = sports.bootstrap_history(date(2026, 8, 10))
    return sports, history
