"""Instrumented Fireworks OpenAI-compatible client."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Literal

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)

from src.costs import (
    MODEL_DEEPSEEK,
    MODEL_GPT_OSS,
    BudgetGuard,
    cost_usd,
    get_shared_budget,
)

ErrorCategory = Literal[
    "structured-output-failed",
    "baseline-parse-failed",
    "safety-rejected",
    "validate-failed",
    "execute-failed",
    "repair-exhausted",
    "budget-exceeded",
    "authentication-failed",
    "rate-limited",
    "network-failed",
    "timed-out",
]


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    latency_ms: float
    retry_ms: float
    model: str
    cost_usd: float
    reasoning_content: str = ""


def model_request_options(model: str) -> dict[str, Any]:
    """Disable or minimize model reasoning for this latency-sensitive task.

    Fireworks' OpenAI-compatible ``reasoning_effort`` field, not a bespoke
    ``enable_thinking`` body field, is what controls this: passing an unrecognized
    top-level field (as ``extra_body`` does, since it merges into the request body
    rather than nesting under an "extra_body" key) is rejected with
    "Extra inputs are not permitted". GPT-OSS/Harmony models only accept
    low/medium/high (``"none"`` errors), so they get an explicit low effort instead.
    """
    if model == MODEL_GPT_OSS:
        return {"reasoning_effort": "low"}
    if model == MODEL_DEEPSEEK:
        return {"reasoning_effort": "none"}
    return {}


def _cached_tokens(usage: Any) -> int:
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        return int(getattr(details, "cached_tokens", 0) or 0)
    # Fireworks/OpenAI-compatible SDKs may retain unknown usage fields here.
    raw = getattr(usage, "model_extra", None) or {}
    return int((raw.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0)


async def complete(
    messages: list[dict[str, str]],
    model: str,
    *,
    response_format: dict[str, Any] | None = None,
    max_tokens: int = 400,
    budget: BudgetGuard | None = None,
    request_options: dict[str, Any] | None = None,
) -> LLMResult:
    """Complete once, retrying transient failures while preserving hard budget reserve."""
    guard = budget or get_shared_budget(float(os.getenv("FIREWORKS_BUDGET_USD", "6.00")))
    estimated_input = sum(len(message["content"]) for message in messages) // 3 + 256
    reservation = await guard.reserve(model, estimated_input, max_tokens)
    client = AsyncOpenAI(
        api_key=os.environ.get("FIREWORKS_API_KEY"),
        base_url="https://api.fireworks.ai/inference/v1",
        timeout=20.0,
    )
    options = model_request_options(model)
    options.update(request_options or {})
    started = time.perf_counter()
    retry_ms = 0.0
    try:
        response = None
        create: Any = client.chat.completions.create
        for attempt in range(2):
            try:
                response = await create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                    max_tokens=max_tokens,
                    temperature=0,
                    **options,
                )
                break
            except (RateLimitError, InternalServerError):
                if attempt:
                    raise
                retry_started = time.perf_counter()
                await asyncio.sleep(0.5)
                retry_ms += (time.perf_counter() - retry_started) * 1_000
        assert response is not None
        usage = response.usage
        input_tokens = int(usage.prompt_tokens if usage else 0)
        output_tokens = int(usage.completion_tokens if usage else 0)
        cached_tokens = _cached_tokens(usage) if usage else 0
        actual_cost = cost_usd(model, input_tokens, cached_tokens, output_tokens)
        await guard.settle(reservation, actual_cost)
        message = response.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None) or ""
        return LLMResult(
            text=message.content or "",
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            latency_ms=(time.perf_counter() - started) * 1_000,
            retry_ms=retry_ms,
            model=model,
            cost_usd=actual_cost,
            reasoning_content=reasoning_content,
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError):
        await guard.settle(reservation, None)
        raise
    except Exception:
        await guard.settle(reservation, None)
        raise
    finally:
        await client.close()
