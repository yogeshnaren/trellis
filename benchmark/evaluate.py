"""Execution-accuracy evaluation against gold SQL result sets."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from sqlglot import exp, parse_one

from src.db import connect_readonly, execute, result_signature

OrderPolicy = Literal["strict", "bag"]
TiePolicy = Literal["ordered", "bag_within_ties"]
DateGrain = Literal["month", "year_month"]


@dataclass
class EvaluationContract:
    order_policy: OrderPolicy | None = None
    tie_policy: TiePolicy | None = None
    date_grain: DateGrain | None = None
    required_columns: list[str] | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> EvaluationContract | None:
        if not raw:
            return None
        return cls(
            order_policy=raw.get("order_policy"),
            tie_policy=raw.get("tie_policy"),
            date_grain=raw.get("date_grain"),
            required_columns=list(raw["required_columns"])
            if raw.get("required_columns") is not None
            else None,
        )


@dataclass
class Evaluation:
    question_id: str
    correct: bool
    reason: str
    warning: str | None = None
    sql_equivalent: bool = False
    e2e_success: bool | None = None

    def __post_init__(self) -> None:
        # Keep ``correct`` and ``sql_equivalent`` aligned for back-compat.
        if self.correct and not self.sql_equivalent:
            self.sql_equivalent = True
        elif self.sql_equivalent and not self.correct:
            self.correct = True


def evaluate_task_success(
    *,
    error: str | None,
    response_type: str | None,
    rows: list[Any] | None,
    sql_equivalent: bool,
) -> bool:
    """End-to-end success: agent delivered results and SQL matched gold."""
    return (
        error is None
        and response_type == "query"
        and rows is not None
        and sql_equivalent
    )


def _normal(value: Any) -> Any:
    if value is None:
        return ("NULL",)
    if isinstance(value, float):
        return round(value, 2)
    return value


def _month_key(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if re.fullmatch(r"\d{2}", value):
        return value
    match = re.fullmatch(r"\d{4}-(\d{2})", value)
    if match:
        return match.group(1)
    return value


def _apply_date_grain(
    columns: list[str],
    rows: list[tuple[Any, ...]],
    grain: DateGrain | None,
) -> list[tuple[Any, ...]]:
    if grain != "month":
        return rows
    indexes = [
        index
        for index, name in enumerate(columns)
        if "month" in name.casefold() or name.casefold() in {"ym", "period"}
    ]
    if not indexes:
        indexes = [0] if columns else []
    normalized: list[tuple[Any, ...]] = []
    for row in rows:
        values = list(row)
        for index in indexes:
            if index < len(values):
                values[index] = _month_key(values[index])
        normalized.append(tuple(values))
    return normalized


def _aligned_rows(
    gold_columns: list[str],
    gold_rows: list[tuple[Any, ...]],
    actual_columns: list[str],
    actual_rows: list[tuple[Any, ...]],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[str], str | None]:
    gold_names = [name.casefold() for name in gold_columns]
    actual_names = [name.casefold() for name in actual_columns]
    warning = None
    aligned_columns = gold_columns
    if len(set(gold_names)) == len(gold_names) and set(gold_names) == set(actual_names):
        indexes = [actual_names.index(name) for name in gold_names]
        actual_rows = [tuple(row[index] for index in indexes) for row in actual_rows]
    else:
        warning = "Columns could not be aligned by name; positional comparison used"
        if len(gold_columns) != len(actual_columns):
            return gold_rows, actual_rows, aligned_columns, warning
    return (
        [tuple(_normal(value) for value in row) for row in gold_rows],
        [tuple(_normal(value) for value in row) for row in actual_rows],
        aligned_columns,
        warning,
    )


def _bag_within_ties(
    gold_rows: list[tuple[Any, ...]],
    actual_rows: list[tuple[Any, ...]],
) -> bool:
    """Allow free permutation among rows that share the same ranking score."""
    if Counter(gold_rows) != Counter(actual_rows):
        return False

    def score(row: tuple[Any, ...]) -> Any:
        for value in reversed(row):
            if isinstance(value, (int, float)) or (
                isinstance(value, tuple) and value == ("NULL",)
            ):
                return value
        return row

    def groups(rows: list[tuple[Any, ...]]) -> list[tuple[Any, Counter[tuple[Any, ...]]]]:
        ordered: list[tuple[Any, Counter[tuple[Any, ...]]]] = []
        current_score: Any = object()
        current: Counter[tuple[Any, ...]] = Counter()
        for row in rows:
            row_score = score(row)
            if row_score != current_score:
                if current:
                    ordered.append((current_score, current))
                current_score = row_score
                current = Counter()
            current[row] += 1
        if current:
            ordered.append((current_score, current))
        return ordered

    return groups(gold_rows) == groups(actual_rows)


def evaluate_sql(
    question_id: str,
    gold_sql: str,
    actual_sql: str | None,
    conn: sqlite3.Connection,
    contract: EvaluationContract | Mapping[str, Any] | None = None,
) -> Evaluation:
    """Compare complete result sets; product rendering limits do not apply."""
    resolved = (
        contract
        if isinstance(contract, EvaluationContract)
        else EvaluationContract.from_mapping(contract)
    )
    if not actual_sql:
        return Evaluation(question_id, False, "No generated SQL", sql_equivalent=False)
    try:
        gold_columns, gold_rows, _ = execute(conn, gold_sql, limit=None)
        actual_columns, actual_rows, _ = execute(conn, actual_sql, limit=None)
    except sqlite3.Error as exc:
        return Evaluation(
            question_id, False, f"Execution failed: {exc}", sql_equivalent=False
        )
    return compare_result_sets(
        question_id, gold_sql, gold_columns, gold_rows, actual_columns, actual_rows, resolved
    )


def compare_result_sets(
    question_id: str,
    gold_sql: str,
    gold_columns: list[str],
    gold_rows: list[tuple[Any, ...]],
    actual_columns: list[str],
    actual_rows: list[tuple[Any, ...]],
    resolved: EvaluationContract | None = None,
) -> Evaluation:
    """The local contract-aware comparison, on already-executed result sets."""
    if resolved and resolved.required_columns:
        required = {name.casefold() for name in resolved.required_columns}
        actual_names = {name.casefold() for name in actual_columns}
        missing = sorted(required - actual_names)
        if missing:
            return Evaluation(
                question_id,
                False,
                f"Missing required columns: {', '.join(missing)}",
                sql_equivalent=False,
            )

    gold_rows, actual_rows, aligned_columns, warning = _aligned_rows(
        gold_columns, gold_rows, actual_columns, actual_rows
    )
    if resolved and resolved.date_grain:
        gold_rows = _apply_date_grain(aligned_columns, gold_rows, resolved.date_grain)
        actual_rows = _apply_date_grain(aligned_columns, actual_rows, resolved.date_grain)

    gold_has_order = parse_one(gold_sql, read="sqlite").find(exp.Order) is not None
    order_policy = (resolved.order_policy if resolved else None) or (
        "strict" if gold_has_order else "bag"
    )
    tie_policy = resolved.tie_policy if resolved else None

    if order_policy == "bag":
        matches = Counter(gold_rows) == Counter(actual_rows)
    elif tie_policy == "bag_within_ties":
        matches = _bag_within_ties(gold_rows, actual_rows)
    else:
        matches = gold_rows == actual_rows

    return Evaluation(
        question_id,
        matches,
        "Result sets match" if matches else "Result sets differ",
        warning,
        sql_equivalent=matches,
    )


BIRD_OFFICIAL_TIMEOUT_S = 30.0


@dataclass
class BirdScore:
    evaluation: Evaluation
    official_ex: bool
    signature: str | None
    row_count: int | None


def score_bird(
    conn: sqlite3.Connection,
    question_id: str,
    gold_sql: str,
    generated_sql: str | None,
    *,
    delivered: bool,
) -> BirdScore:
    """Execute generated and gold SQL once each and derive every metric from those rows.

    The generated SQL runs *first*, so its full-result signature exists even when the gold
    query fails or times out. ``official_ex`` counts only SQL the agent delivered (a
    rejected or failed query is no answer); the local ``evaluation`` keeps its historical
    definition (any generated SQL).
    """
    if not generated_sql:
        missing = Evaluation(question_id, False, "No generated SQL", sql_equivalent=False)
        return BirdScore(missing, False, None, None)
    try:
        actual_columns, actual_rows, _ = execute(conn, generated_sql, limit=None)
    except sqlite3.Error as exc:
        failed = Evaluation(question_id, False, f"Execution failed: {exc}")
        return BirdScore(failed, False, None, None)
    signature, row_count = result_signature(actual_rows), len(actual_rows)
    try:
        gold_columns, gold_rows, _ = execute(conn, gold_sql, limit=None)
    except sqlite3.Error as exc:
        failed = Evaluation(question_id, False, f"Gold execution failed: {exc}")
        return BirdScore(failed, False, signature, row_count)
    evaluation = compare_result_sets(
        question_id, gold_sql, gold_columns, gold_rows, actual_columns, actual_rows
    )
    official = delivered and set(actual_rows) == set(gold_rows)
    return BirdScore(evaluation, official, signature, row_count)


def official_ex(conn: sqlite3.Connection, gold_sql: str, actual_sql: str | None) -> bool:
    """BIRD's official execution-accuracy rule: ``set(predicted) == set(gold)``.

    Mirrors ``evaluation_ex.py`` from bird-bench/mini_dev: row order, duplicate rows, and
    column names are ignored, but column *positions* and exact values (no float rounding)
    matter, and any execution error scores 0. Deliberately independent of
    ``evaluate_sql``'s contract-aware comparison, which stays the Chinook-suite metric.
    """
    if not actual_sql:
        return False
    try:
        _, gold_rows, _ = execute(conn, gold_sql, limit=None)
        _, actual_rows, _ = execute(conn, actual_sql, limit=None)
    except sqlite3.Error:
        return False
    return set(actual_rows) == set(gold_rows)


def evaluate_file(
    raw_path: Path,
    gold_path: Path = Path("data/dev_questions_with_answers.json"),
) -> Path:
    gold = {item["id"]: item for item in json.loads(gold_path.read_text())}
    conn = connect_readonly()
    try:
        evaluations = []
        for line in raw_path.read_text().splitlines():
            record = json.loads(line)
            question = gold[record["question_id"]]
            evaluation = evaluate_sql(
                record["question_id"],
                question["gold_sql"],
                record.get("sql"),
                conn,
                contract=question.get("evaluation_contract"),
            )
            evaluation.e2e_success = evaluate_task_success(
                error=record.get("error"),
                response_type=record.get("response_type"),
                rows=record.get("rows"),
                sql_equivalent=evaluation.sql_equivalent,
            )
            evaluations.append({**record, "evaluation": asdict(evaluation)})
    finally:
        conn.close()
    output = raw_path.with_name(raw_path.stem + "_evaluated.jsonl")
    output.write_text("\n".join(json.dumps(row) for row in evaluations) + "\n")
    return output
