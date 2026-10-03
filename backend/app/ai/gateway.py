"""Every AI call goes through here: validation, retries, fallbacks, token + cost accounting, logging."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .provider import IAgentModelProvider, ModelRequest, cost_usd

T = TypeVar("T", bound=BaseModel)


class AICallRecord(BaseModel):
    """One logical AI call (possibly several attempts). Persisted to the ai_calls table."""

    run_id: str
    sim_time: datetime
    agent_id: str
    agent_name: str
    purpose: str
    provider: str
    model: str
    system: str
    prompt: str
    response: str
    ok: bool
    error: str | None = None
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    estimated: bool = False
    used_fallback: bool = False


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found in model output")
    return json.loads(text[start:end + 1])


class AIGateway:
    def __init__(self, provider: IAgentModelProvider, run_id: str,
                 sink: Callable[[AICallRecord], None] | None = None,
                 max_retries: int = 2, concurrency: int = 6) -> None:
        self.provider = provider
        self.run_id = run_id
        self.sink = sink
        self.max_retries = max_retries
        self._sem = asyncio.Semaphore(concurrency)

    async def run(self, *, purpose: str, agent_id: str, agent_name: str, sim_time: datetime,
                  system: str, user: str, context: dict[str, Any], output_model: type[T], seed: int,
                  fallback: Callable[[], T], max_tokens: int = 4000) -> tuple[T, AICallRecord]:
        """Ask the provider for a structured answer. Never raises: on failure returns `fallback()`."""
        prompt = user
        attempts = 0
        tokens_in = tokens_out = 0
        latency = 0.0
        last_error: str | None = None
        last_text = ""
        model = self.provider.model_for(purpose)
        estimated = False
        async with self._sem:
            while attempts <= self.max_retries:
                attempts += 1
                req = ModelRequest(purpose=purpose, agent_id=agent_id, agent_name=agent_name, system=system,
                                   user=prompt, context=context, output_model=output_model,
                                   seed=seed + attempts * 7919, max_tokens=max_tokens)
                t0 = time.perf_counter()
                try:
                    resp = await self.provider.complete(req)
                except Exception as exc:  # network errors, refusals, SDK errors
                    latency += (time.perf_counter() - t0) * 1000
                    last_error = f"{type(exc).__name__}: {exc}"
                    continue
                latency += resp.latency_ms
                tokens_in += resp.input_tokens
                tokens_out += resp.output_tokens
                model = resp.model
                estimated = resp.estimated_usage
                last_text = resp.text
                try:
                    parsed = output_model.model_validate(_extract_json(resp.text))
                except (ValueError, ValidationError) as exc:
                    last_error = f"invalid output: {str(exc)[:400]}"
                    prompt = (
                        f"{user}\n\nYour previous answer could not be used ({last_error}). "
                        "Reply again with a single JSON object that matches the schema exactly."
                    )
                    continue
                record = self._record(purpose, agent_id, agent_name, sim_time, model, system, user, last_text,
                                      True, None, attempts - 1, tokens_in, tokens_out, latency, estimated, False)
                return parsed, record
        result = fallback()
        record = self._record(purpose, agent_id, agent_name, sim_time, model, system, user, last_text,
                              False, last_error, attempts - 1, tokens_in, tokens_out, latency, estimated, True)
        return result, record

    def _record(self, purpose: str, agent_id: str, agent_name: str, sim_time: datetime, model: str,
                system: str, prompt: str, response: str, ok: bool, error: str | None, retries: int,
                tokens_in: int, tokens_out: int, latency: float, estimated: bool, used_fallback: bool) -> AICallRecord:
        rec = AICallRecord(
            run_id=self.run_id, sim_time=sim_time, agent_id=agent_id, agent_name=agent_name, purpose=purpose,
            provider=self.provider.name, model=model, system=system, prompt=prompt, response=response, ok=ok,
            error=error, retries=retries, input_tokens=tokens_in, output_tokens=tokens_out,
            cost_usd=cost_usd(model, tokens_in, tokens_out), latency_ms=round(latency, 1), estimated=estimated,
            used_fallback=used_fallback,
        )
        if self.sink:
            self.sink(rec)
        return rec
