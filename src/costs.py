"""Token pricing and concurrency-safe project-wide budget accounting."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

MODEL_GPT_OSS = "accounts/fireworks/models/gpt-oss-120b"
MODEL_DEEPSEEK = "accounts/fireworks/models/deepseek-v4-flash-0731"
MODEL_MINIMAX = "accounts/fireworks/models/minimax-m3"
MODELS = (MODEL_GPT_OSS, MODEL_DEEPSEEK, MODEL_MINIMAX)

# USD per one million tokens: input, cached input, output. Verified against
# https://docs.fireworks.ai/serverless/pricing on 2026-09-22.
#
# gpt-oss-20b and the undated deepseek-v4-flash alias used in the original July 2026 bake-off
# have since been retired from the Fireworks catalog; gpt-oss-120b and the dated
# deepseek-v4-flash-0731 snapshot are their live replacements (see docs/DECISIONS.md).
PRICING: dict[str, dict[str, float]] = {
    MODEL_GPT_OSS: {"input": 0.15, "cached": 0.015, "output": 0.60},
    MODEL_DEEPSEEK: {"input": 0.22, "cached": 0.007, "output": 0.66},
    MODEL_MINIMAX: {"input": 0.30, "cached": 0.06, "output": 1.20},
}
DEFAULT_LEDGER = Path("benchmark/results/.spend.json")


class BudgetExceeded(RuntimeError):
    """Raised before dispatch when the reservation would exceed the ceiling."""


def cost_usd(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """Price uncached input, cached input, and output independently."""
    rates = PRICING[model]
    cached = min(max(cached_tokens, 0), max(input_tokens, 0))
    uncached = max(input_tokens - cached, 0)
    return (
        uncached * rates["input"]
        + cached * rates["cached"]
        + max(output_tokens, 0) * rates["output"]
    ) / 1_000_000


@dataclass(frozen=True)
class Reservation:
    token: str
    amount_usd: float


class BudgetGuard:
    """Reserve before HTTP dispatch, then settle actual cost on one ledger."""

    def __init__(self, ceiling_usd: float = 6.0, ledger_path: Path = DEFAULT_LEDGER):
        self.ceiling_usd = ceiling_usd
        self.ledger_path = ledger_path
        self._lock = asyncio.Lock()
        self._reserved: dict[str, float] = {}
        self._spent = self._read_spent()

    def _read_spent(self) -> float:
        try:
            return float(json.loads(self.ledger_path.read_text())["spent_usd"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return 0.0

    def _persist(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.ledger_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"spent_usd": self._spent}, indent=2) + "\n")
        temporary.replace(self.ledger_path)

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def reserved(self) -> float:
        return sum(self._reserved.values())

    @property
    def remaining(self) -> float:
        return max(self.ceiling_usd - self.spent - self.reserved, 0.0)

    async def reserve(
        self,
        model: str,
        estimated_input_tokens: int,
        max_output_tokens: int,
    ) -> Reservation:
        """Atomically reserve conservative uncached-input plus max-output cost."""
        amount = cost_usd(model, estimated_input_tokens, 0, max_output_tokens)
        async with self._lock:
            if self._spent + self.reserved + amount > self.ceiling_usd:
                raise BudgetExceeded(
                    f"Shared ${self.ceiling_usd:.2f} ceiling would be exceeded; "
                    f"${self.remaining:.4f} remains"
                )
            token = uuid4().hex
            self._reserved[token] = amount
            return Reservation(token, amount)

    async def settle(self, reservation: Reservation, actual_usd: float | None) -> float:
        """Replace a reservation with actual cost; unknown outcomes retain the reserve."""
        async with self._lock:
            reserved = self._reserved.pop(reservation.token, 0.0)
            charged = reserved if actual_usd is None else max(actual_usd, 0.0)
            self._spent += charged
            self._persist()
            return charged


_SHARED_GUARDS: dict[tuple[str, float], BudgetGuard] = {}


def get_shared_budget(
    ceiling_usd: float = 6.0,
    ledger_path: Path = DEFAULT_LEDGER,
) -> BudgetGuard:
    """Return the process-wide guard for the persisted project ledger."""
    key = (str(ledger_path.resolve()), ceiling_usd)
    if key not in _SHARED_GUARDS:
        _SHARED_GUARDS[key] = BudgetGuard(ceiling_usd, ledger_path)
    return _SHARED_GUARDS[key]
