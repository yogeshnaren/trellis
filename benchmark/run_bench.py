"""Budgeted asynchronous model bake-off."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlglot import parse
from sqlglot.errors import ParseError, TokenError

from benchmark.evaluate import evaluate_sql, evaluate_task_success
from src.agent import Agent, AgentResult
from src.conversation import ConversationContext
from src.costs import (
    MODEL_DEEPSEEK,
    MODELS,
    BudgetExceeded,
    BudgetGuard,
    get_shared_budget,
)
from src.db import connect_readonly, execute, is_safe, validate
from src.llm import complete
from src.prompts import baseline_prompt
from src.schema import DEFAULT_DB_PATH, get_schema

CONTROL_MODEL = MODEL_DEEPSEEK


def arm_matrix(models: list[str], arms: list[str]) -> list[tuple[str, str]]:
    matrix = [(model, "agent") for model in models if "agent" in arms]
    if "baseline" in arms:
        matrix.append((CONTROL_MODEL, "baseline"))
    return matrix


def extract_baseline_sql(text: str) -> str:
    """Extract but never repair/rewrite the first parser-valid SQL statement."""
    stripped = text.strip()
    fence = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    match = re.search(r"\b(?:SELECT|WITH)\b", stripped, flags=re.IGNORECASE)
    if not match:
        raise ValueError("No SELECT/WITH statement found")
    try:
        statements = [statement for statement in parse(stripped[match.start() :], read="sqlite") if statement]
    except (ParseError, TokenError) as exc:
        raise ValueError(f"sqlglot could not parse baseline output: {exc}") from exc
    if not statements:
        raise ValueError("No valid SQL statement found")
    return statements[0].sql(dialect="sqlite")


async def run_baseline(
    question: str,
    model: str,
    budget: BudgetGuard,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> AgentResult:
    started = asyncio.get_running_loop().time()
    result = AgentResult(question=question)
    try:
        call = await complete(
            [{"role": "user", "content": baseline_prompt(question)}],
            model,
            max_tokens=300,
            budget=budget,
        )
        result.llm_calls.append(call)
        result.t_llm_ms = call.latency_ms
        try:
            result.sql = extract_baseline_sql(call.text)
        except ValueError as exc:
            result.error, result.error_category = str(exc), "baseline-parse-failed"
            return result
        safe, reason = is_safe(result.sql, db_path=db_path)
        if not safe:
            result.error, result.error_category = reason, "safety-rejected"
            return result
        conn = connect_readonly(db_path)
        try:
            valid, error = validate(conn, result.sql)
            if not valid:
                result.error, result.error_category = error, "validate-failed"
                return result
            result.columns, result.rows, result.truncated = execute(conn, result.sql)
        finally:
            conn.close()
        return result
    except BudgetExceeded as exc:
        result.error, result.error_category = str(exc), "budget-exceeded"
        return result
    finally:
        result.t_total_ms = (asyncio.get_running_loop().time() - started) * 1_000


def serialize_result(
    result: AgentResult,
    *,
    question_id: str,
    model: str,
    arm: str,
    repeat: int,
    concurrency: int,
) -> dict[str, Any]:
    data = asdict(result)
    data.update(
        question_id=question_id,
        model=model,
        arm=arm,
        repeat=repeat,
        concurrency=concurrency,
    )
    return data


def human_answer(columns: list[str] | None, rows: list[list[Any]] | None) -> str:
    if not rows:
        return "No rows returned."
    rendered = []
    for row in rows[:5]:
        rendered.append(", ".join(f"{name}: {value}" for name, value in zip(columns or [], row)))
    suffix = " …" if len(rows) > 5 else ""
    return "; ".join(rendered) + suffix


async def benchmark(args: argparse.Namespace) -> Path:
    if not os.getenv("FIREWORKS_API_KEY"):
        raise SystemExit(
            "BLOCKED: FIREWORKS_API_KEY is absent. Run:\n"
            "export FIREWORKS_API_KEY=<your-key>\n"
            "uv run python -m benchmark.run_bench --models "
            + " ".join(args.models)
            + f" --repeats {args.repeats} --concurrency {args.concurrency} "
            "--arms "
            + " ".join(args.arms)
            + f" --budget {args.budget:.2f}"
        )
    questions = json.loads(Path(args.questions).read_text())
    gold = {item["id"]: item for item in questions}
    guard = get_shared_budget(args.budget)
    semaphore = asyncio.Semaphore(args.concurrency)
    stop = asyncio.Event()
    records: list[dict[str, Any]] = []
    db_path = args.db_path

    async def one(model: str, arm: str, question: dict[str, Any], repeat: int) -> None:
        if stop.is_set():
            return
        async with semaphore:
            if stop.is_set():
                return
            if arm == "agent":
                conn = connect_readonly(db_path)
                try:
                    # Independent question/repeat: no unrelated history contamination.
                    result = await Agent(model, conn, guard, db_path=db_path).ask(
                        question["question"], ConversationContext(get_schema(db_path))
                    )
                finally:
                    conn.close()
            else:
                result = await run_baseline(question["question"], model, guard, db_path=db_path)
            if result.error_category == "budget-exceeded":
                stop.set()
            record = serialize_result(
                result,
                question_id=question["id"],
                model=model,
                arm=arm,
                repeat=repeat,
                concurrency=args.concurrency,
            )
            evaluation_conn = connect_readonly(db_path)
            try:
                evaluation = evaluate_sql(
                    question["id"],
                    gold[question["id"]]["gold_sql"],
                    result.sql,
                    evaluation_conn,
                    contract=gold[question["id"]].get("evaluation_contract"),
                )
                evaluation.e2e_success = evaluate_task_success(
                    error=result.error,
                    response_type=result.response_type,
                    rows=result.rows,
                    sql_equivalent=evaluation.sql_equivalent,
                )
                record["evaluation"] = asdict(evaluation)
            finally:
                evaluation_conn.close()
            records.append(record)

    # One excluded warm-up per arm/model; never enters the reported distribution.
    for model, arm in arm_matrix(args.models, args.arms):
        if arm == "agent":
            conn = connect_readonly(db_path)
            try:
                await Agent(model, conn, guard, db_path=db_path).ask(
                    questions[0]["question"], ConversationContext(get_schema(db_path))
                )
            finally:
                conn.close()
        else:
            await run_baseline(questions[0]["question"], model, guard, db_path=db_path)

    jobs = [
        (model, arm, question, repeat)
        for model, arm in arm_matrix(args.models, args.arms)
        for repeat in range(args.repeats)
        for question in questions
    ]
    queue: asyncio.Queue[tuple[str, str, dict[str, Any], int]] = asyncio.Queue()
    for job in jobs:
        queue.put_nowait(job)

    async def worker() -> None:
        while not queue.empty() and not stop.is_set():
            job = await queue.get()
            try:
                await one(*job)
            finally:
                queue.task_done()

    # Only this bounded worker set is created. Queued jobs have not dispatched HTTP.
    workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
    await asyncio.gather(*workers)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = Path(f"benchmark/results/raw_bakeoff_{timestamp}.jsonl")
    output.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    for model, arm in arm_matrix(args.models, args.arms):
        model_slug = model.rsplit("/", 1)[-1]
        arm_records = [
            record for record in records if record["model"] == model and record["arm"] == arm
        ]
        arm_path = Path(f"benchmark/results/raw_{model_slug}_{arm}_{timestamp}.jsonl")
        arm_path.write_text("\n".join(json.dumps(record) for record in arm_records) + "\n")

    if args.emit_answers:
        answers: dict[str, dict[str, str]] = {}
        for record in records:
            if record["arm"] == "agent" and record["repeat"] == 0 and record.get("sql"):
                answers[record["question_id"]] = {
                    "sql": record["sql"],
                    "answer": human_answer(record.get("columns"), record.get("rows")),
                }
        Path("data/dev_answers.json").write_text(json.dumps(answers, indent=2) + "\n")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--arms", nargs="+", choices=["agent", "baseline"], default=["agent"])
    parser.add_argument("--budget", type=float, default=4.0)
    parser.add_argument(
        "--questions",
        default="data/dev_questions_with_answers.json",
        help="Gold-labeled questions JSON used for execution-accuracy eval.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database every question in --questions is run against.",
    )
    parser.add_argument("--emit-answers", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    output = asyncio.run(benchmark(parse_args()))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
