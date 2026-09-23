"""Budgeted async BIRD-SQL Mini-Dev runner.

Same agent/safety/repair pipeline as the Chinook bake-off (``benchmark/run_bench.py``), pointed
at BIRD's 11 databases instead of one. Requires ``./scripts/setup_bird_minidev.sh`` to have been
run first. This is a local run against Mini-Dev's public dev-labels for comparison, not a
submission to the official BIRD-SQL leaderboard (which scores a held-out test set through its
own submission process).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from benchmark.bird import (
    DEFAULT_BIRD_DIR,
    BirdQuestion,
    db_path_for,
    load_questions,
    with_evidence,
)
from benchmark.evaluate import evaluate_sql
from src.agent import Agent
from src.conversation import ConversationContext
from src.costs import MODEL_DEEPSEEK, get_shared_budget
from src.db import connect_readonly
from src.schema import get_schema

DIFFICULTIES = ("simple", "moderate", "challenging")


def select_questions(args: argparse.Namespace) -> list[BirdQuestion]:
    questions = load_questions(Path(args.bird_dir) / "mini_dev_sqlite.json")
    if args.difficulty:
        questions = [q for q in questions if q.difficulty in args.difficulty]
    if args.db:
        questions = [q for q in questions if q.db_id in args.db]
    if args.limit is not None and args.limit < len(questions):
        questions = list(questions)
        random.Random(args.seed).shuffle(questions)
        questions = questions[: args.limit]
    return questions


async def benchmark(args: argparse.Namespace) -> Path:
    if not os.getenv("FIREWORKS_API_KEY"):
        raise SystemExit(
            "BLOCKED: FIREWORKS_API_KEY is absent. Run:\nexport FIREWORKS_API_KEY=<your-key>"
        )
    questions = select_questions(args)
    if not questions:
        raise SystemExit("No BIRD questions matched --difficulty/--db/--limit filters")
    guard = get_shared_budget(args.budget)
    semaphore = asyncio.Semaphore(args.concurrency)
    stop = asyncio.Event()
    records: list[dict[str, Any]] = []

    async def one(model: str, question: BirdQuestion, repeat: int) -> None:
        if stop.is_set():
            return
        async with semaphore:
            if stop.is_set():
                return
            db_path = db_path_for(question.db_id, bird_dir=args.bird_dir)
            conn = connect_readonly(db_path)
            try:
                result = await Agent(model, conn, guard, db_path=db_path).ask(
                    with_evidence(question.question, question.evidence),
                    ConversationContext(get_schema(db_path)),
                )
            finally:
                conn.close()
            if result.error_category == "budget-exceeded":
                stop.set()
            record = asdict(result)
            record.update(
                question_id=question.question_id,
                db_id=question.db_id,
                difficulty=question.difficulty,
                model=model,
                repeat=repeat,
                concurrency=args.concurrency,
            )
            eval_conn = connect_readonly(db_path)
            try:
                evaluation = evaluate_sql(
                    str(question.question_id), question.gold_sql, result.sql, eval_conn
                )
                record["evaluation"] = asdict(evaluation)
            finally:
                eval_conn.close()
            records.append(record)

    jobs = [
        (model, question, repeat)
        for model in args.models
        for repeat in range(args.repeats)
        for question in questions
    ]
    queue: asyncio.Queue[tuple[str, BirdQuestion, int]] = asyncio.Queue()
    for job in jobs:
        queue.put_nowait(job)

    async def worker() -> None:
        while not queue.empty() and not stop.is_set():
            job = await queue.get()
            try:
                await one(*job)
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
    await asyncio.gather(*workers)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = Path(f"benchmark/results/bird_raw_{timestamp}.jsonl")
    output.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    Path(args.report).write_text(build_bird_report(records, len(questions)))
    return output


def build_bird_report(records: list[dict[str, Any]], question_count: int) -> str:
    lines = [
        "# BIRD-SQL Mini-Dev Report",
        "",
        (
            f"Local execution-accuracy (EX) run against {question_count} Mini-Dev questions "
            "(public dev-labels), using the same schema-grounded agent as the Chinook bake-off. "
            "**Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a "
            "held-out test set through its own process; this is a comparable local proxy. "
            "Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here."
        ),
        "",
        "| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["model"], record["difficulty"])].append(record)
    for model in sorted({record["model"] for record in records}):
        rows_by_difficulty = [(d, groups.get((model, d), [])) for d in DIFFICULTIES]
        overall = [row for _, rows in rows_by_difficulty for row in rows]
        for label, rows in [*rows_by_difficulty, ("overall", overall)]:
            if not rows:
                continue
            correct = sum(bool(row.get("evaluation", {}).get("sql_equivalent")) for row in rows)
            latencies = sorted(float(row["t_total_ms"]) / 1_000 for row in rows)
            costs = [sum(call["cost_usd"] for call in row.get("llm_calls", [])) for row in rows]
            repairs = sum(bool(row.get("repaired")) for row in rows)
            p50 = latencies[len(latencies) // 2]
            p90 = latencies[min(len(latencies) - 1, round(0.9 * (len(latencies) - 1)))]
            lines.append(
                f"| `{model}` | {label} | {len(rows)} | {correct / len(rows):.1%} | "
                f"{p50:.2f} | {p90:.2f} | {repairs / len(rows):.1%} | "
                f"${statistics.mean(costs) if costs else 0.0:.6f} |"
            )
    lines.extend(["", "## Failure analysis"])
    failures = [r for r in records if not r.get("evaluation", {}).get("sql_equivalent")]
    if not failures:
        lines.append("No execution-accuracy failures in this run.")
    else:
        for row in sorted(failures, key=lambda r: (r["db_id"], r["question_id"])):
            reason = row.get("evaluation", {}).get("reason") or row.get("error") or "Unknown"
            category = row.get("error_category") or "wrong-result"
            lines.append(
                f"- `{row['db_id']}` #{row['question_id']} ({row['difficulty']}): "
                f"{reason} (category: {category})"
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[MODEL_DEEPSEEK])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--budget", type=float, default=2.0)
    parser.add_argument(
        "--difficulty", nargs="+", choices=DIFFICULTIES, help="Filter to these difficulties."
    )
    parser.add_argument("--db", nargs="+", help="Filter to these db_ids.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Randomly sample at most this many questions."
    )
    parser.add_argument("--seed", type=int, default=0, help="Sampling seed for --limit.")
    parser.add_argument("--bird-dir", default=str(DEFAULT_BIRD_DIR))
    parser.add_argument("--report", default="benchmark/results/bird_report.md")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    output = asyncio.run(benchmark(parse_args()))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
