"""Bounded text-to-SQL generation, validation, execution, and repair."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from pydantic import ValidationError

from src.conversation import ConversationContext, Turn
from src.costs import BudgetExceeded, BudgetGuard
from src.db import execute, is_safe, validate
from src.llm import ErrorCategory, LLMResult, complete
from src.prompts import REPAIR_PROMPT, SQL_SCHEMA, ResponseType, SQLResponse
from src.schema import DEFAULT_DB_PATH

CompleteFn = Callable[..., Awaitable[LLMResult]]


@dataclass
class AgentResult:
    question: str
    response_type: ResponseType | None = None
    message: str | None = None
    sql: str | None = None
    rows: list[tuple[Any, ...]] | None = None
    columns: list[str] | None = None
    error: str | None = None
    error_category: ErrorCategory | None = None
    repaired: bool = False
    truncated: bool = False
    llm_calls: list[LLMResult] = field(default_factory=list)
    t_schema_ms: float = 0.0
    t_llm_ms: float = 0.0
    t_exec_ms: float = 0.0
    t_total_ms: float = 0.0

    @property
    def input_tokens(self) -> int:
        return sum(call.input_tokens for call in self.llm_calls)

    @property
    def cached_tokens(self) -> int:
        return sum(call.cached_tokens for call in self.llm_calls)

    @property
    def output_tokens(self) -> int:
        return sum(call.output_tokens for call in self.llm_calls)

    @property
    def cost_usd(self) -> float:
        return sum(call.cost_usd for call in self.llm_calls)

    @property
    def ok(self) -> bool:
        return self.error is None


class Agent:
    def __init__(
        self,
        model: str,
        conn: sqlite3.Connection,
        budget: BudgetGuard,
        *,
        db_path: str | Path = DEFAULT_DB_PATH,
        max_repairs: int = 1,
        complete_fn: CompleteFn = complete,
    ):
        self.model = model
        self.conn = conn
        self.budget = budget
        self.db_path = db_path
        self.max_repairs = max_repairs
        self.complete_fn = complete_fn

    async def ask(self, question: str, ctx: ConversationContext) -> AgentResult:
        started = time.perf_counter()
        result = AgentResult(question=question)
        messages = ctx.build_messages(question)
        repairs_left = self.max_repairs

        while True:
            try:
                llm_result = await self.complete_fn(
                    messages,
                    self.model,
                    response_format=SQL_SCHEMA,
                    max_tokens=400,
                    budget=self.budget,
                )
                result.llm_calls.append(llm_result)
                result.t_llm_ms += llm_result.latency_ms
            except BudgetExceeded as exc:
                return self._finish(result, str(exc), "budget-exceeded", started)
            except AuthenticationError as exc:
                return self._finish(result, str(exc), "authentication-failed", started)
            except RateLimitError as exc:
                return self._finish(result, str(exc), "rate-limited", started)
            except APITimeoutError as exc:
                return self._finish(result, str(exc), "timed-out", started)
            except APIConnectionError as exc:
                return self._finish(result, str(exc), "network-failed", started)

            try:
                payload = SQLResponse.model_validate_json(llm_result.text)
                if payload.response_type == "query":
                    if not payload.sql or not payload.sql.strip():
                        raise ValueError("query responses require non-empty sql")
                    if payload.message is not None:
                        raise ValueError("query responses must set message to null")
                else:
                    if payload.sql is not None:
                        raise ValueError(
                            f"{payload.response_type} responses must set sql to null"
                        )
                    if not payload.message or not payload.message.strip():
                        raise ValueError(
                            f"{payload.response_type} responses require a non-empty message"
                        )
            except (ValidationError, ValueError) as exc:
                return self._finish(
                    result, f"Structured output failed: {exc}", "structured-output-failed", started
                )

            result.response_type = payload.response_type
            result.message = payload.message
            if payload.response_type != "query":
                result.t_total_ms = (time.perf_counter() - started) * 1_000
                return result

            sql = payload.sql
            assert sql is not None
            result.sql = sql
            safe, reason = is_safe(sql, db_path=self.db_path)
            if not safe:
                return self._finish(result, reason, "safety-rejected", started)

            valid, error = validate(self.conn, sql)
            if not valid:
                if repairs_left:
                    repairs_left -= 1
                    result.repaired = True
                    messages.append({"role": "assistant", "content": llm_result.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": REPAIR_PROMPT.format(sql=sql, error=error),
                        }
                    )
                    continue
                category: ErrorCategory = (
                    "repair-exhausted" if result.repaired else "validate-failed"
                )
                return self._finish(result, error, category, started)

            exec_started = time.perf_counter()
            try:
                columns, rows, truncated = execute(self.conn, sql)
            except sqlite3.Error as exc:
                result.t_exec_ms += (time.perf_counter() - exec_started) * 1_000
                if repairs_left:
                    repairs_left -= 1
                    result.repaired = True
                    messages.extend(
                        [
                            {"role": "assistant", "content": llm_result.text},
                            {
                                "role": "user",
                                "content": REPAIR_PROMPT.format(sql=sql, error=str(exc)),
                            },
                        ]
                    )
                    continue
                category = "repair-exhausted" if result.repaired else "execute-failed"
                return self._finish(result, str(exc), category, started)
            result.t_exec_ms += (time.perf_counter() - exec_started) * 1_000
            result.columns, result.rows, result.truncated = columns, rows, truncated
            ctx.record(Turn(question, sql, len(rows), truncated))
            result.t_total_ms = (time.perf_counter() - started) * 1_000
            return result

    @staticmethod
    def _finish(
        result: AgentResult,
        error: str,
        category: ErrorCategory,
        started: float,
    ) -> AgentResult:
        result.error = error
        result.error_category = category
        result.t_total_ms = (time.perf_counter() - started) * 1_000
        return result
