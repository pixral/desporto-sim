"""Claude provider. Only used when DESPORTO_AI_PROVIDER=anthropic.

Structured outputs come from `messages.parse(output_format=<pydantic model>)`, which constrains
the response to the schema; the gateway still re-validates. Model and effort are configurable
per purpose through environment variables (see app/config.py).
"""

from __future__ import annotations

import time

from .provider import ModelRequest, ModelResponse

try:  # optional dependency
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

# Models that accept the server-side refusal fallback ("default" routing by refusal category).
_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, models: dict[str, str], efforts: dict[str, str], default_model: str = "claude-opus-5-5",
                 default_effort: str = "medium") -> None:
        if anthropic is None:
            raise RuntimeError("The 'anthropic' package is not installed. pip install anthropic")
        # Credentials resolve from ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login` profile.
        self.client = anthropic.AsyncAnthropic(max_retries=2)
        self.models = models
        self.efforts = efforts
        self.default_model = default_model
        self.default_effort = default_effort

    def model_for(self, purpose: str) -> str:
        return self.models.get(purpose, self.default_model)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        model = self.model_for(request.purpose)
        kwargs: dict = dict(
            model=model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
            output_format=request.output_model,
        )
        effort = self.efforts.get(request.purpose, self.default_effort)
        if effort and model != "claude-haiku-4-5":
            kwargs["output_config"] = {"effort": effort}
        if model in _FALLBACK_MODELS:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        t0 = time.perf_counter()
        response = await self.client.beta.messages.parse(**kwargs)
        latency = (time.perf_counter() - t0) * 1000
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model refused ({getattr(response.stop_details, 'category', None)})")
        parsed = response.parsed_output
        if parsed is not None:
            text = parsed.model_dump_json()
        else:
            text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        return ModelResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model or model,
            latency_ms=latency,
            stop_reason=response.stop_reason,
        )
