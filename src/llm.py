"""Instrumented OpenAI-compatible client: Fireworks by default, plus OpenRouter and local servers.

A model name selects its provider: ``openrouter/<id>`` goes to OpenRouter (key
``OPENROUTER_API_KEY``, spend charged against its own cap in the shared ledger),
``local/<name>`` to an OpenAI-compatible server on this machine (``LOCAL_LLM_BASE_URL``,
default http://127.0.0.1:8080/v1; free), and anything else to Fireworks, unchanged.
"""

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
    LOCAL_PREFIX,
    MODEL_DEEPSEEK,
    MODEL_DEEPSEEK_V4P1,
    MODEL_GPT_OSS,
    OPENROUTER_PREFIX,
    BudgetGuard,
    Reservation,
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
    "model-unavailable",
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
    # Provider stop reason ("stop", "length", ...); "length" means max_tokens cut the output.
    finish_reason: str = ""


def model_request_options(model: str) -> dict[str, Any]:
    """Disable or minimize model reasoning for this latency-sensitive task.

    Fireworks' OpenAI-compatible ``reasoning_effort`` field, not a bespoke
    ``enable_thinking`` body field, is what controls this: passing an unrecognized
    top-level field (as ``extra_body`` does, since it merges into the request body
    rather than nesting under an "extra_body" key) is rejected with
    "Extra inputs are not permitted". GPT-OSS/Harmony models only accept
    low/medium/high (``"none"`` errors), so they get an explicit low effort instead.
    """
    if model.startswith(OPENROUTER_PREFIX):
        # Only route to hosts that honour every request parameter (e.g. strict JSON schema).
        return {"extra_body": {"provider": {"require_parameters": True}}}
    if model == MODEL_GPT_OSS:
        return {"reasoning_effort": "low"}
    if model in {MODEL_DEEPSEEK, MODEL_DEEPSEEK_V4P1}:
        return {"reasoning_effort": "none"}
    return {}


def _cached_tokens(usage: Any) -> int:
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        return int(getattr(details, "cached_tokens", 0) or 0)
    # Fireworks/OpenAI-compatible SDKs may retain unknown usage fields here.
    raw = getattr(usage, "model_extra", None) or {}
    return int((raw.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0)


FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LOCAL_BASE_URL = "http://127.0.0.1:8080/v1"
# One client (and so one pooled HTTPS connection set) per event loop and provider. A fresh
# client per call paid a new TCP + TLS handshake on every request; the per-request timeout is
# passed on each call instead. Keyed by loop because an httpx client can't cross event loops.
_CLIENTS: dict[tuple[int, str], tuple[asyncio.AbstractEventLoop, AsyncOpenAI]] = {}


def provider_of(model: str) -> str:
    if model.startswith(OPENROUTER_PREFIX):
        return "openrouter"
    if model.startswith(LOCAL_PREFIX):
        return "local"
    return "fireworks"


def api_model_name(model: str) -> str:
    """The provider's own model id (routing prefixes removed)."""
    for prefix in (OPENROUTER_PREFIX, LOCAL_PREFIX):
        if model.startswith(prefix):
            return model.removeprefix(prefix)
    return model


def _new_client(provider: str) -> AsyncOpenAI:
    if provider == "openrouter":
        return AsyncOpenAI(api_key=os.environ.get("OPENROUTER_API_KEY"), base_url=OPENROUTER_BASE_URL)
    if provider == "local":
        return AsyncOpenAI(api_key="local", base_url=os.environ.get("LOCAL_LLM_BASE_URL", LOCAL_BASE_URL))
    return AsyncOpenAI(api_key=os.environ.get("FIREWORKS_API_KEY"), base_url=FIREWORKS_BASE_URL)


def shared_client(provider: str = "fireworks") -> AsyncOpenAI:
    loop = asyncio.get_running_loop()
    entry = _CLIENTS.get((id(loop), provider))
    if entry is None or entry[0] is not loop:
        for key, (old_loop, _) in list(_CLIENTS.items()):
            if old_loop.is_closed():
                del _CLIENTS[key]  # drop clients of finished loops (e.g. asyncio.run in tests)
        entry = (loop, _new_client(provider))
        _CLIENTS[(id(loop), provider)] = entry
    return entry[1]


async def _reserve(guard: BudgetGuard, model: str, provider: str, estimated_input: int,
                   max_tokens: int) -> Reservation | None:
    if provider == "local":
        return None
    if provider == "openrouter":
        amount = max(cost_usd(model, estimated_input, 0, max_tokens), 1e-6)
        return await guard.reserve_openrouter_usd(
            amount,
            provider_ceiling_usd=float(os.getenv("OPENROUTER_BUDGET_USD", "5")),
            session_ceiling_usd=float(os.getenv("OPENROUTER_SESSION_BUDGET_USD", "5")),
            session_id=os.getenv("OPENROUTER_SESSION_ID", "bench"),
            label=model,
        )
    return await guard.reserve(model, estimated_input, max_tokens)


async def _settle(guard: BudgetGuard, reservation: Reservation | None, provider: str,
                  cost: float | None) -> None:
    if reservation is None:
        return
    if provider == "openrouter":
        await guard.settle(reservation, cost, source="openrouter")
    else:
        await guard.settle(reservation, cost)


async def complete(
    messages: list[dict[str, str]],
    model: str,
    *,
    response_format: dict[str, Any] | None = None,
    max_tokens: int = 400,
    budget: BudgetGuard | None = None,
    request_options: dict[str, Any] | None = None,
    temperature: float = 0.0,
    timeout_s: float = 20.0,
) -> LLMResult:
    """Complete once, retrying transient failures while preserving hard budget reserve."""
    guard = budget or get_shared_budget(float(os.getenv("FIREWORKS_BUDGET_USD", "6.00")))
    estimated_input = sum(len(message["content"]) for message in messages) // 3 + 256
    provider = provider_of(model)
    reservation = await _reserve(guard, model, provider, estimated_input, max_tokens)
    client = shared_client(provider)
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
                    model=api_model_name(model),
                    messages=messages,
                    response_format=response_format,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout_s,
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
        await _settle(guard, reservation, provider, actual_cost)
        choice = response.choices[0]
        message = choice.message
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
            finish_reason=str(getattr(choice, "finish_reason", None) or ""),
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError):
        await _settle(guard, reservation, provider, None)
        raise
    except Exception:
        await _settle(guard, reservation, provider, None)
        raise
