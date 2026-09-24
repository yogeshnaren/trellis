"""Token pricing and concurrency-safe project-wide budget accounting."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
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
    # Remaining Standard-tier serverless models, verified against the same page on 2026-09-23
    # for the SOTA-plan bake-offs (docs/SOTA_PLAN.md). Batch inference bills 50% of these.
    "accounts/fireworks/models/deepseek-v4p1-flash": {"input": 0.30, "cached": 0.006, "output": 1.20},
    "accounts/fireworks/models/deepseek-v4-pro-0813": {"input": 1.32, "cached": 0.044, "output": 3.96},
    "accounts/fireworks/models/glm-5p3": {"input": 1.40, "cached": 0.26, "output": 4.40},
    "accounts/fireworks/models/glm-5p3-flash": {"input": 0.15, "cached": 0.03, "output": 0.50},
    "accounts/fireworks/models/kimi-k2p7-code": {"input": 0.95, "cached": 0.19, "output": 4.00},
    "accounts/fireworks/models/kimi-k3": {"input": 3.00, "cached": 0.30, "output": 15.00},
    "accounts/fireworks/models/qwen3p8-max": {"input": 2.00, "cached": 0.25, "output": 6.00},
    "accounts/fireworks/models/nemotron-3-ultra-nvfp4": {"input": 0.60, "cached": 0.12, "output": 2.40},
}
# SQLite spend ledger; a legacy JSON ledger at the same stem is imported once on first use.
DEFAULT_LEDGER = Path("benchmark/results/.spend.sqlite")
# Fireworks bills batch inference at 50% of serverless pricing on input and output.
BATCH_DISCOUNT = 0.5
# A reservation this old is treated as abandoned (charged as spent, since its call may have
# been billed) even if its process is still alive.
STALE_RESERVATION_S = 3_600.0


class BudgetExceeded(RuntimeError):
    """Raised before dispatch when the reservation would exceed the ceiling."""


def cost_usd(
    model: str,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    *,
    batch: bool = False,
) -> float:
    """Price uncached input, cached input, and output independently (batch: 50% off)."""
    rates = PRICING[model]
    cached = min(max(cached_tokens, 0), max(input_tokens, 0))
    uncached = max(input_tokens - cached, 0)
    serverless = (
        uncached * rates["input"]
        + cached * rates["cached"]
        + max(output_tokens, 0) * rates["output"]
    ) / 1_000_000
    return serverless * BATCH_DISCOUNT if batch else serverless


@dataclass(frozen=True)
class Reservation:
    token: str
    amount_usd: float


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS reservation (
    token TEXT PRIMARY KEY, usd REAL NOT NULL, pid INTEGER NOT NULL, at REAL NOT NULL,
    ttl_s REAL NOT NULL, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS charge (
    id INTEGER PRIMARY KEY, token TEXT, usd REAL NOT NULL, source TEXT NOT NULL,
    kind TEXT NOT NULL, at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS charge_token ON charge(token);
CREATE TABLE IF NOT EXISTS settlement (
    token TEXT PRIMARY KEY, state TEXT NOT NULL, at REAL NOT NULL
);
"""


class BudgetGuard:
    """Reserve before dispatch, settle actual cost, on one ledger shared across processes.

    The ledger is a SQLite database: an append-only ``charge`` journal (spend is its sum),
    open ``reservation`` rows, and a durable, indexed ``settlement`` key per reservation.
    Every operation runs in a ``BEGIN IMMEDIATE`` transaction, so concurrent processes (a CLI
    session, benchmark runs, batch jobs) serialize on SQLite's lock and always see each
    other's reserves and spend.

    Settlement is reconciling and idempotent, and never forgets a key:

    - ``settle(r, actual)`` charges the actual cost and marks the key *final*; settling a
      final key again is a no-op.
    - ``settle(r, None)`` (outcome unknown) charges the reserved amount *provisionally*
      under the ``unsettled`` source; a later ``settle(r, actual)`` reverses that charge and
      books the actual cost under its real source.
    - A reservation whose process has died, or that outlives its ``ttl_s``, is charged
      provisionally the same way (its call may have been billed).
    - ``reserve_usd(..., key=...)`` takes a caller-supplied durable key (e.g. a batch job
      id), so a different process can settle it after a restart via ``reservation(key)``.

    Non-token-priced spend (OpenRouter/Jev, Fireworks batch jobs) uses ``reserve_usd`` and a
    ``source`` label; ``record_charge`` books after-the-fact reconciliations. A legacy JSON
    ledger (``spent_usd``) next to the database is imported once as an opening balance.
    """

    def __init__(self, ceiling_usd: float = 6.0, ledger_path: Path = DEFAULT_LEDGER):
        self.ceiling_usd = ceiling_usd
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            self._import_legacy(db)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """One write-locked transaction; charges stale reservations first."""
        db = sqlite3.connect(self.ledger_path, timeout=60, isolation_level=None)
        try:
            db.executescript(_LEDGER_SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            try:
                self._charge_stale(db)
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()

    def _import_legacy(self, db: sqlite3.Connection) -> None:
        legacy = self.ledger_path.with_suffix(".json")
        if legacy == self.ledger_path or not legacy.exists():
            return
        if db.execute("SELECT 1 FROM charge WHERE kind = 'opening'").fetchone():
            return
        try:
            raw = json.loads(legacy.read_text())
        except json.JSONDecodeError:
            return
        spent = float(raw.get("spent_usd", 0.0) or 0.0)
        by_source = raw.get("by_source") or ({"fireworks": spent} if spent else {})
        for source, usd in by_source.items():
            self._charge(db, None, float(usd), str(source), "opening")
        legacy.replace(legacy.with_suffix(".json.migrated"))

    @staticmethod
    def _charge(
        db: sqlite3.Connection, token: str | None, usd: float, source: str, kind: str
    ) -> None:
        db.execute(
            "INSERT INTO charge (token, usd, source, kind, at) VALUES (?, ?, ?, ?, ?)",
            (token, usd, source, kind, time.time()),
        )

    @staticmethod
    def _mark(db: sqlite3.Connection, token: str, state: str) -> None:
        db.execute(
            "INSERT OR REPLACE INTO settlement (token, state, at) VALUES (?, ?, ?)",
            (token, state, time.time()),
        )

    def _charge_stale(self, db: sqlite3.Connection) -> None:
        now = time.time()
        rows = db.execute("SELECT token, usd, pid, at, ttl_s FROM reservation").fetchall()
        for token, usd, pid, at, ttl_s in rows:
            if not _pid_alive(int(pid)) or now - float(at) > float(ttl_s):
                db.execute("DELETE FROM reservation WHERE token = ?", (token,))
                self._charge(db, token, float(usd), "unsettled", "provisional")
                self._mark(db, token, "provisional")

    @staticmethod
    def _spent(db: sqlite3.Connection) -> float:
        return float(db.execute("SELECT COALESCE(SUM(usd), 0) FROM charge").fetchone()[0])

    @staticmethod
    def _reserved(db: sqlite3.Connection) -> float:
        row = db.execute("SELECT COALESCE(SUM(usd), 0) FROM reservation").fetchone()
        return float(row[0])

    @property
    def spent(self) -> float:
        with self._transaction() as db:
            return self._spent(db)

    @property
    def reserved(self) -> float:
        with self._transaction() as db:
            return self._reserved(db)

    @property
    def remaining(self) -> float:
        with self._transaction() as db:
            return max(self.ceiling_usd - self._spent(db) - self._reserved(db), 0.0)

    def spend_by_source(self) -> dict[str, float]:
        with self._transaction() as db:
            rows = db.execute("SELECT source, SUM(usd) FROM charge GROUP BY source").fetchall()
            return {str(source): float(usd) for source, usd in rows if abs(usd) > 1e-12}

    def reservation(self, key: str) -> Reservation:
        """Rebuild a handle for a caller-keyed reservation (e.g. after a restart)."""
        with self._transaction() as db:
            row = db.execute("SELECT usd FROM reservation WHERE token = ?", (key,)).fetchone()
            return Reservation(key, float(row[0]) if row else 0.0)

    async def reserve(
        self,
        model: str,
        estimated_input_tokens: int,
        max_output_tokens: int,
        *,
        batch: bool = False,
    ) -> Reservation:
        """Atomically reserve conservative uncached-input plus max-output cost."""
        amount = cost_usd(model, estimated_input_tokens, 0, max_output_tokens, batch=batch)
        return await self.reserve_usd(amount, label=model)

    async def reserve_usd(
        self,
        amount_usd: float,
        *,
        label: str = "",
        ttl_s: float = STALE_RESERVATION_S,
        key: str | None = None,
    ) -> Reservation:
        """Reserve a dollar amount directly (OpenRouter/Jev calls, batch-job estimates).

        ``ttl_s`` is how long the reservation may stay open before it is treated as
        abandoned. ``key`` makes the reservation durable and idempotent: reserving an
        existing or already-settled key returns it instead of reserving twice.
        """
        with self._transaction() as db:
            if key is not None:
                existing = db.execute(
                    "SELECT usd FROM reservation WHERE token = ?", (key,)
                ).fetchone()
                if existing:
                    return Reservation(key, float(existing[0]))
                if db.execute("SELECT 1 FROM settlement WHERE token = ?", (key,)).fetchone():
                    return Reservation(key, 0.0)
            committed = self._spent(db) + self._reserved(db)
            if committed + amount_usd > self.ceiling_usd:
                remaining = max(self.ceiling_usd - committed, 0.0)
                raise BudgetExceeded(
                    f"Shared ${self.ceiling_usd:.2f} ceiling would be exceeded; "
                    f"${remaining:.4f} remains"
                )
            token = key if key is not None else uuid4().hex
            db.execute(
                "INSERT INTO reservation (token, usd, pid, at, ttl_s, label) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (token, amount_usd, os.getpid(), time.time(), ttl_s, label),
            )
            return Reservation(token, amount_usd)

    async def settle(
        self, reservation: Reservation, actual_usd: float | None, *, source: str = "fireworks"
    ) -> float:
        """Settle a reservation; returns the change in recorded spend (see class docs)."""
        token = reservation.token
        with self._transaction() as db:
            state_row = db.execute(
                "SELECT state FROM settlement WHERE token = ?", (token,)
            ).fetchone()
            if state_row and state_row[0] == "final":
                return 0.0
            held = db.execute("SELECT usd FROM reservation WHERE token = ?", (token,)).fetchone()
            if held is not None:
                db.execute("DELETE FROM reservation WHERE token = ?", (token,))
                if actual_usd is None:
                    self._charge(db, token, float(held[0]), "unsettled", "provisional")
                    self._mark(db, token, "provisional")
                    return float(held[0])
                self._charge(db, token, max(actual_usd, 0.0), source, "final")
                self._mark(db, token, "final")
                return max(actual_usd, 0.0)
            if state_row and state_row[0] == "provisional":
                if actual_usd is None:
                    return 0.0  # still unknown: the conservative provisional charge stands
                prior = float(
                    db.execute(
                        "SELECT COALESCE(SUM(usd), 0) FROM charge "
                        "WHERE token = ? AND kind IN ('provisional', 'reversal')",
                        (token,),
                    ).fetchone()[0]
                )
                self._charge(db, token, -prior, "unsettled", "reversal")
                self._charge(db, token, max(actual_usd, 0.0), source, "final")
                self._mark(db, token, "final")
                return max(actual_usd, 0.0) - prior
            # A key this ledger never reserved: book what is known, once.
            charged = max(actual_usd or 0.0, 0.0)
            self._charge(db, token, charged, source, "final")
            self._mark(db, token, "final")
            return charged

    def record_charge(self, amount_usd: float, *, source: str) -> None:
        """Record spend that happened outside a reservation (e.g. a batch-invoice delta)."""
        with self._transaction() as db:
            self._charge(db, None, amount_usd, source, "external")


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
