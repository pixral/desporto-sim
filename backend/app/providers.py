"""Factories that pick concrete sports-data and AI providers from configuration."""

from __future__ import annotations

from app.ai.mock_provider import MockAgentModelProvider
from app.ai.provider import IAgentModelProvider
from app.config import Settings
from app.domain.world import RunConfig
from app.economy.config import preset
from app.sports.mock_provider import MockSportsDataProvider
from app.sports.provider import ISportsDataProvider


def make_sports_provider(config: RunConfig) -> ISportsDataProvider:
    if config.sports_provider == "mock":
        return MockSportsDataProvider(seed=config.seed, xg_offset=preset(config.difficulty)["market_xg"])
    raise ValueError(f"unknown sports provider '{config.sports_provider}' (only 'mock' is implemented)")


def make_ai_provider(settings: Settings, config: RunConfig) -> IAgentModelProvider:
    if config.ai_provider == "mock":
        return MockAgentModelProvider(reference_model=settings.default_model, failure_rate=settings.mock_failure_rate)
    if config.ai_provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.model_overrides(), settings.effort_overrides(),
                                 default_model=settings.default_model, default_effort=settings.default_effort)
    raise ValueError(f"unknown AI provider '{config.ai_provider}'")
