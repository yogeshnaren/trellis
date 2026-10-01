"""Bounded text-to-SQL generation, validation, execution, and repair."""

from __future__ import annotations

import asyncio
import copy
import sqlite3
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from src.conversation import ConversationContext, Turn
from src.costs import BudgetExceeded, BudgetGuard
from src.db import (
    execute,
    identifier_hint,
    is_recoverable_rejection,
    is_safe,
    result_signature,
    validate,
)
from src.llm import ErrorCategory, LLMResult, complete
from src.prompts import (
    EMPTY_RESULT_PROMPT,
    REFUSAL_RETRY_PROMPT,
    REPAIR_PROMPT,
    SQL_SCHEMA,
    ResponseType,
    SQLResponse,
)
from src.schema import DEFAULT_DB_PATH
from src.value_hints import value_hints as stored_value_hints

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
    refusal_retried: bool = False
    empty_retried: bool = False
    truncation_retried: bool = False
    truncated: bool = False
    # Model whose answer was delivered instead of the primary's, by error escalation or the
    # agreement cascade (None: the primary answer stands).
    escalation_model: str | None = None
    # Agreement cascade: 1 when the first two models agreed, 2 when the rest were asked.
    cascade_stage: int | None = None
    # Candidate ledger (P32): every answer produced for this question, in order, with its
    # model, SQL, row count, error and whether it was delivered. Empty when both are off.
    candidates: list[dict[str, Any]] = field(default_factory=list)
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
        max_tokens: int = 400,
        temperature: float = 0.0,
        request_options: dict[str, Any] | None = None,
        pipeline_repairs: bool = False,
        llm_timeout_s: float = 20.0,
        truncation_retry_tokens: int = 0,
        escalation_models: tuple[str, ...] = (),
        shadow_empty_escalation: bool = False,
        cascade_models: tuple[str, ...] = (),
        value_hints: bool = False,
    ):
        self.model = model
        self.conn = conn
        self.budget = budget
        self.db_path = db_path
        self.max_repairs = max_repairs
        self.complete_fn = complete_fn
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_options = request_options
        # Benchmark-mode repairs (off for the interactive CLI): recoverable safety rejects
        # get a "did you mean" repair, one refusal is retried as answerable, an empty result
        # gets one guarded re-check. Forbidden SQL still never retries.
        self.pipeline_repairs = pipeline_repairs
        # Reasoning-mode calls can legitimately exceed the interactive 20s client timeout.
        self.llm_timeout_s = llm_timeout_s
        # When > 0: an answer cut off by max_tokens (finish_reason "length") is re-asked once
        # with this larger cap, instead of raising every call's cap. Off by default.
        self.truncation_retry_tokens = truncation_retry_tokens
        # Benchmark-mode escalation (docs/DECISIONS.md 2026-09-30), split per review P08/P31/P32:
        # - an ERROR answer is always wrong, so the escalation models are asked in order and the
        #   first answer that runs is delivered;
        # - an EMPTY or all-NULL answer may be legitimately correct, so with
        #   ``shadow_empty_escalation`` the models are asked but their answers are only logged in
        #   the candidate ledger, never delivered.
        # Both are off by default (the CLI never uses them). This is a quality escalation, not an
        # availability fallback for an unavailable model.
        self.escalation_models = escalation_models
        self.shadow_empty_escalation = shadow_empty_escalation
        # Benchmark-mode agreement cascade (docs/DECISIONS.md 2026-09-30): the primary model and
        # cascade_models[0] answer at the same time; if their results match (non-empty), that
        # answer is delivered. Otherwise the remaining cascade models answer (also at the same
        # time) and the result most models share is delivered, ties going to the primary. An
        # error is never delivered while another model has an answer that runs. Off by default.
        self.cascade_models = cascade_models
        # Benchmark-mode stored-value hints (docs/DECISIONS.md 2026-09-30): the empty-result
        # retry also covers all-NULL answers and is told which compared literals the database
        # does not store, with similar stored values and slash-date formats. Off by default.
        self.value_hints = value_hints

    async def ask(self, question: str, ctx: ConversationContext) -> AgentResult:
        if self.cascade_models:
            return await self._cascade(question, ctx)
        started = time.perf_counter()
        before = copy.deepcopy(ctx) if self.escalation_models else None
        result = await self._ask(question, ctx)
        if before is None:
            return result
        trigger = escalation_trigger(result)
        if trigger is None or (trigger == "empty" and not self.shadow_empty_escalation):
            return result
        result.candidates.append(_candidate(self.model, result, delivered=True))
        for model in self.escalation_models:
            # Each model uses its own request defaults (e.g. gpt-oss rejects reasoning_effort
            # "none") and a fresh copy of the pre-question context: same prompt, schema, facts.
            alt = await self._ask(question, copy.deepcopy(before), model=model, options=None)
            _absorb(result, alt)
            deliver = trigger == "error" and alt.ok and alt.response_type == "query"
            result.candidates.append(_candidate(model, alt, delivered=deliver))
            if deliver:
                result.candidates[0]["delivered"] = False
                _deliver(result, alt, model)
                break
            if alt.error_category == "budget-exceeded":
                break
        result.t_total_ms = (time.perf_counter() - started) * 1_000
        return result

    async def _cascade(self, question: str, ctx: ConversationContext) -> AgentResult:
        started = time.perf_counter()
        before = copy.deepcopy(ctx)
        first, *rest = self.cascade_models

        def other(model: str) -> Awaitable[AgentResult]:
            return self._ask(question, copy.deepcopy(before), model=model, options=None)

        primary, partner = await asyncio.gather(self._ask(question, ctx), other(first))
        answers = [(self.model, primary), (first, partner)]
        sigs = [self._signature(a) for _, a in answers]
        agreed = sigs[0] is not None and sigs[0] == sigs[1]
        if not agreed and rest:
            extra = await asyncio.gather(*(other(model) for model in rest))
            answers += list(zip(rest, extra, strict=True))
            sigs += [self._signature(a) for a in extra]
        pick = 0 if agreed else _vote([a for _, a in answers], sigs)
        result = primary
        for i, (model, answer) in enumerate(answers):
            if i:
                _absorb(result, answer)
            result.candidates.append(_candidate(model, answer, delivered=i == pick)
                                     | {"signature": sigs[i]})
        if pick:
            model, chosen = answers[pick]
            _deliver(result, chosen, model)
            if ctx.turns and ctx.turns[-1].question == question:
                ctx.turns.pop()  # the primary recorded its own (not delivered) answer
            if chosen.sql is not None and chosen.rows is not None:
                ctx.record(Turn(question, chosen.sql, len(chosen.rows), chosen.truncated))
        result.cascade_stage = 1 if agreed else 2
        result.t_total_ms = (time.perf_counter() - started) * 1_000
        return result

    def _signature(self, answer: AgentResult) -> str | None:
        """Result signature of a non-empty query answer (None for errors, refusals, no rows)."""
        if not answer.ok or answer.response_type != "query" or not answer.rows or not answer.sql:
            return None
        rows = answer.rows
        if answer.truncated:
            try:
                rows = execute(self.conn, answer.sql, limit=None)[1]
            except sqlite3.Error:
                return None
        return result_signature(rows)

    async def _ask(
        self,
        question: str,
        ctx: ConversationContext,
        *,
        model: str | None = None,
        options: dict[str, Any] | None | bool = False,
    ) -> AgentResult:
        """One model's full answer. ``model``/``options`` default to the agent's own; they are
        parameters (not swapped attributes) so several models can answer concurrently."""
        model = model or self.model
        request_options = self.request_options if options is False else options
        assert request_options is None or isinstance(request_options, dict)
        started = time.perf_counter()
        result = AgentResult(question=question)
        messages = ctx.build_messages(question)
        repairs_left = self.max_repairs
        refusal_retry_left = 1 if self.pipeline_repairs else 0
        max_tokens = self.max_tokens

        while True:
            try:
                llm_result = await self.complete_fn(
                    messages,
                    model,
                    response_format=SQL_SCHEMA,
                    max_tokens=max_tokens,
                    budget=self.budget,
                    request_options=request_options,
                    temperature=self.temperature,
                    timeout_s=self.llm_timeout_s,
                )
                result.llm_calls.append(llm_result)
                result.t_llm_ms += llm_result.latency_ms
            except BudgetExceeded as exc:
                return self._finish(result, str(exc), "budget-exceeded", started)
            except AuthenticationError as exc:
                return self._finish(result, str(exc), "authentication-failed", started)
            except (NotFoundError, PermissionDeniedError) as exc:
                # The key cannot call this model (retired, not deployed, or not granted).
                return self._finish(
                    result, f"Model {model} is not available to this API key: {exc}",
                    "model-unavailable", started,
                )
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
                if (
                    llm_result.finish_reason == "length"
                    and self.truncation_retry_tokens > max_tokens
                    and not result.truncation_retried
                ):
                    # Same messages, larger cap, once: only truncated answers pay for it.
                    result.truncation_retried = True
                    max_tokens = self.truncation_retry_tokens
                    continue
                return self._finish(
                    result, f"Structured output failed: {exc}", "structured-output-failed", started
                )

            result.response_type = payload.response_type
            result.message = payload.message
            if payload.response_type != "query":
                if refusal_retry_left:
                    refusal_retry_left -= 1
                    result.refusal_retried = True
                    messages.append({"role": "assistant", "content": llm_result.text})
                    messages.append({"role": "user", "content": REFUSAL_RETRY_PROMPT})
                    continue
                result.t_total_ms = (time.perf_counter() - started) * 1_000
                return result

            sql = payload.sql
            assert sql is not None
            result.sql = sql
            safe, reason = is_safe(sql, db_path=self.db_path)
            if not safe:
                if self.pipeline_repairs and repairs_left and is_recoverable_rejection(reason):
                    repairs_left -= 1
                    result.repaired = True
                    hinted = reason + identifier_hint(reason, self.db_path)
                    messages.append({"role": "assistant", "content": llm_result.text})
                    messages.append(
                        {"role": "user", "content": REPAIR_PROMPT.format(sql=sql, error=hinted)}
                    )
                    continue
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
            if self.pipeline_repairs and (not rows or (self.value_hints and _all_null(rows))):
                retried = await self._retry_empty(
                    messages, llm_result.text, sql, result, model, request_options
                )
                if retried is not None:
                    sql, (columns, rows, truncated) = retried
                    result.sql = sql
            result.columns, result.rows, result.truncated = columns, rows, truncated
            ctx.record(Turn(question, sql, len(rows), truncated))
            result.t_total_ms = (time.perf_counter() - started) * 1_000
            return result

    async def _retry_empty(
        self,
        messages: list[dict[str, str]],
        answer: str,
        sql: str,
        result: AgentResult,
        model: str,
        request_options: dict[str, Any] | None,
    ) -> tuple[str, tuple[list[str], list[tuple[Any, ...]], bool]] | None:
        """One guarded re-check of an empty result.

        The new query replaces the original only if it passes the same safety, validation,
        and execution path *and* returns rows; any failure keeps the original (empty) answer,
        so this can add a call but never turn a delivered answer into an error.
        """
        result.empty_retried = True
        prompt = EMPTY_RESULT_PROMPT.format(sql=sql)
        if self.value_hints:
            hints = stored_value_hints(sql, self.db_path)
            if hints:
                prompt += "\nStored-value checks:\n" + "\n".join(f"- {hint}" for hint in hints)
        retry_messages = [
            *messages,
            {"role": "assistant", "content": answer},
            {"role": "user", "content": prompt},
        ]
        try:
            llm_result = await self.complete_fn(
                retry_messages,
                model,
                response_format=SQL_SCHEMA,
                max_tokens=self.max_tokens,
                budget=self.budget,
                request_options=request_options,
                temperature=self.temperature,
                timeout_s=self.llm_timeout_s,
            )
        except (BudgetExceeded, AuthenticationError, NotFoundError, PermissionDeniedError,
                RateLimitError, APITimeoutError, APIConnectionError):
            return None
        result.llm_calls.append(llm_result)
        result.t_llm_ms += llm_result.latency_ms
        try:
            payload = SQLResponse.model_validate_json(llm_result.text)
        except ValidationError:
            return None
        candidate = (payload.sql or "").strip()
        if payload.response_type != "query" or not candidate or candidate == sql.strip():
            return None
        if not is_safe(candidate, db_path=self.db_path)[0] or not validate(self.conn, candidate)[0]:
            return None
        exec_started = time.perf_counter()
        try:
            outcome = execute(self.conn, candidate)
        except sqlite3.Error:
            return None
        finally:
            result.t_exec_ms += (time.perf_counter() - exec_started) * 1_000
        rows = outcome[1]
        return (candidate, outcome) if rows and not (self.value_hints and _all_null(rows)) else None

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


def escalation_trigger(result: AgentResult) -> str | None:
    """'error' for a failed answer (not budget/credentials), 'empty' for a query answer with no
    rows or only NULLs (e.g. ``[(None,)]`` from an aggregate over nothing), else None."""
    if result.error_category in ("budget-exceeded", "authentication-failed"):
        return None
    if result.error is not None:
        return "error"
    if result.response_type == "query" and (
        not result.rows or all(value is None for row in result.rows for value in row)
    ):
        return "empty"
    return None


def _candidate(model: str, result: AgentResult, *, delivered: bool) -> dict[str, Any]:
    return {"model": model, "sql": result.sql, "row_count": len(result.rows or []),
            "error_category": result.error_category, "delivered": delivered}


def _vote(answers: list[AgentResult], signatures: list[str | None]) -> int:
    """Index of the answer whose result most models share; ties go to the earliest (the
    primary first). With no non-empty result, the first answer that ran without error."""
    votes = Counter(sig for sig in signatures if sig is not None)
    if votes:
        best = max(votes.values())
        return next(i for i, sig in enumerate(signatures) if sig is not None and votes[sig] == best)
    return next((i for i, a in enumerate(answers) if a.ok and a.response_type == "query"), 0)


def _absorb(result: AgentResult, other: AgentResult) -> None:
    """Charge another model's calls and time to this question's result."""
    result.llm_calls.extend(other.llm_calls)
    result.t_llm_ms += other.t_llm_ms
    result.t_exec_ms += other.t_exec_ms


def _deliver(result: AgentResult, chosen: AgentResult, model: str) -> None:
    for name in ("response_type", "message", "sql", "rows", "columns", "error", "error_category",
                 "truncated"):
        setattr(result, name, getattr(chosen, name))
    result.escalation_model = model


def _all_null(rows: list[tuple[Any, ...]]) -> bool:
    return bool(rows) and all(value is None for row in rows for value in row)
