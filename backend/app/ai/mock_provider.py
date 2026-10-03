"""Free, deterministic stand-in for an LLM.

Receives the same request a real model would (system + user prompt + the structured context
the prompt was rendered from) and answers with JSON from the personality-driven policies.
Token usage is estimated from prompt length so the economy still pays for "AI" at the
reference model's price.
"""

from __future__ import annotations

import json
import random
import time

from app.agents.policies import ceo_policy, lab_policy, tipster_policy

from .provider import ModelRequest, ModelResponse

_POLICIES = {
    "tipster_day": tipster_policy.decide_day,
    "ceo_review": ceo_policy.review,
    "lab_hypothesis": lab_policy.hypothesize,
}


class MockAgentModelProvider:
    name = "mock"

    def __init__(self, reference_model: str = "claude-opus-5-5", failure_rate: float = 0.0) -> None:
        self.reference_model = reference_model
        self.failure_rate = failure_rate

    def model_for(self, purpose: str) -> str:
        return self.reference_model

    async def complete(self, request: ModelRequest) -> ModelResponse:
        t0 = time.perf_counter()
        rng = random.Random(request.seed)
        policy = _POLICIES.get(request.purpose)
        if policy is None:
            raise ValueError(f"mock provider has no policy for purpose '{request.purpose}'")
        if self.failure_rate and rng.random() < self.failure_rate:
            text = "{\"oops\": I am not valid JSON"  # exercise the gateway's retry path
        else:
            text = json.dumps(policy(request.context, rng), ensure_ascii=False)
        return ModelResponse(
            text=text,
            input_tokens=(len(request.system) + len(request.user)) // 4,
            output_tokens=len(text) // 4 + 150,  # + a little simulated reasoning
            model=self.reference_model,
            latency_ms=(time.perf_counter() - t0) * 1000,
            estimated_usage=True,
        )
