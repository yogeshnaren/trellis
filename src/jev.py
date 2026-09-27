"""Typed OpenRouter/Jev decisions with bounded, reconciled spending.

Jev is a shadow-only decision service until a paired benchmark promotes a specific
policy. This module never generates SQL and never silently retries an uncertain call.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from src.costs import BudgetGuard

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
# The model's listed 32K context at $0.042/M input is about $0.00135. A $0.01
# reservation leaves substantial pricing/usage headroom, then settles actual usage.
JEV_RESERVATION_USD = 0.01
Transport = Callable[[bytes, str, float], dict[str, Any]]


class JevError(RuntimeError):
    """A decision failed; callers must use their deterministic baseline."""


@dataclass(frozen=True)
class JevConfig:
    api_key: str
    model: str
    total_cap_usd: float
    session_cap_usd: float

    @classmethod
    def from_env(cls) -> JevConfig:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        model = os.getenv("OPENROUTER_MODEL", "typesafe/jev-1.13").strip()
        if model != "typesafe/jev-1.13":
            raise ValueError("Jev benchmark calls require pinned typesafe/jev-1.13")
        total = float(os.getenv("OPENROUTER_BUDGET_USD", "0"))
        session = float(os.getenv("OPENROUTER_SESSION_BUDGET_USD", "0"))
        if total <= 0 or session <= 0:
            raise ValueError("OpenRouter total and session budgets must be positive")
        return cls(key, model, total, session)


@dataclass(frozen=True)
class JevDecision:
    answers: dict[str, dict[str, Any]]
    response_id: str
    model_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


def _post(payload: bytes, api_key: str, timeout_s: float) -> dict[str, Any]:
    request = Request(
        JEV_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        parsed: Any = json.load(response)
    if not isinstance(parsed, dict):
        raise JevError("Jev returned a non-object response")
    return parsed


def _validate_answers(
    raw: Any, questions: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or set(raw) != set(questions):
        raise JevError("Jev answer keys do not match request")
    validated: dict[str, dict[str, Any]] = {}
    for name, spec in questions.items():
        answer = raw[name]
        kind = spec.get("type")
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise JevError("Jev answer type is invalid")
        if kind == "noul":
            value = answer.get("noul")
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise JevError("Jev noul probability is invalid")
        elif kind == "choice":
            criteria = spec.get("criteria")
            choice = answer.get("choice")
            confidence = answer.get("confidence")
            if (
                not isinstance(criteria, dict)
                or choice not in criteria
                or not isinstance(confidence, (int, float))
                or not 0 <= float(confidence) <= 1
            ):
                raise JevError("Jev choice is invalid")
        elif kind == "score":
            if not isinstance(answer.get("score"), (int, float)):
                raise JevError("Jev score is invalid")
        else:
            raise ValueError(f"Unsupported Jev question type: {kind}")
        validated[name] = answer
    return validated


class JevClient:
    def __init__(
        self,
        config: JevConfig,
        guard: BudgetGuard,
        *,
        session_id: str | None = None,
        timeout_s: float = 30.0,
        transport: Transport = _post,
    ) -> None:
        self.config = config
        self.guard = guard
        self.session_id = session_id or uuid4().hex
        self.timeout_s = timeout_s
        self.transport = transport

    async def decide(
        self, state: Mapping[str, Any], questions: Mapping[str, Mapping[str, Any]]
    ) -> JevDecision:
        if not state or not questions:
            raise ValueError("Jev state and questions must be nonempty")
        # Validate specifications before reserving or dispatching.
        for spec in questions.values():
            if spec.get("type") not in {"noul", "choice", "score"}:
                raise ValueError("Jev question type must be noul, choice, or score")
        payload = json.dumps(
            {"model": self.config.model, "state": state, "questions": questions},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        reservation = await self.guard.reserve_openrouter_usd(
            JEV_RESERVATION_USD,
            provider_ceiling_usd=self.config.total_cap_usd,
            session_ceiling_usd=self.config.session_cap_usd,
            session_id=self.session_id,
            label=self.config.model,
        )
        started = time.perf_counter()
        try:
            raw = await asyncio.to_thread(
                self.transport, payload, self.config.api_key, self.timeout_s
            )
        except Exception:  # noqa: BLE001 - a failed transport may still have been billed
            # A network/endpoint failure may have been billed; hold the estimate.
            await self.guard.settle(reservation, None, source="openrouter")
            raise JevError("Jev request failed; deterministic fallback required") from None
        latency_ms = (time.perf_counter() - started) * 1000
        usage = raw.get("usage")
        if not isinstance(usage, dict) or not isinstance(usage.get("cost"), (int, float)):
            await self.guard.settle(reservation, None, source="openrouter")
            raise JevError("Jev returned no usable cost; deterministic fallback required")
        cost = float(usage["cost"])
        if cost < 0:
            await self.guard.settle(reservation, None, source="openrouter")
            raise JevError("Jev returned a negative cost")
        await self.guard.settle(reservation, cost, source="openrouter")
        answers = _validate_answers(raw.get("answers"), questions)
        version = raw.get("model")
        if not isinstance(version, str) or not version.startswith("typesafe/jev-1.13"):
            raise JevError("Unexpected Jev model version; deterministic fallback required")
        response_id = raw.get("id")
        return JevDecision(
            answers=answers,
            response_id=response_id if isinstance(response_id, str) else "",
            model_version=version,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cost_usd=cost,
            latency_ms=latency_ms,
        )
