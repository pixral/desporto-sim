"""Model-provider abstraction. The simulation never imports a concrete LLM SDK directly."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

# USD per million tokens (input, output). Used for cost accounting and mock estimates.
PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICING.get(model, (4.0, 20.0))
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


class ModelRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    purpose: str  # tipster_day | ceo_review | lab_hypothesis
    agent_id: str
    agent_name: str
    system: str
    user: str
    context: dict[str, Any]  # the structured data the prompt was rendered from
    output_model: type[BaseModel]
    seed: int
    max_tokens: int = 4000


class ModelResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float
    estimated_usage: bool = False  # True when tokens are estimated (mock provider)
    stop_reason: str | None = None


@runtime_checkable
class IAgentModelProvider(Protocol):
    name: str

    def model_for(self, purpose: str) -> str: ...

    async def complete(self, request: ModelRequest) -> ModelResponse: ...
