"""Budgeted async BIRD-SQL runner (Mini-Dev by default; any BIRD-format question file).

Same agent/safety/repair pipeline as the Chinook bake-off (``benchmark/run_bench.py``), pointed
at BIRD's 11 databases instead of one. Requires ``./scripts/setup_bird_minidev.sh`` to have been
run first. This is a local run against Mini-Dev's public dev-labels for comparison, not a
submission to the official BIRD-SQL leaderboard (which scores a held-out test set through its
own submission process).

Scoring unit is the dataset *row* (``row_index``), so all 500 Mini-Dev rows count, duplicates
included, exactly as BIRD's official evaluator does. Each run writes a raw JSONL plus a
``bird_meta_<ts>.json`` sidecar pinning the dataset fingerprint, prompt hash, git commit, and
generation parameters, so runs on different dataset versions are never silently mixed.

    uv run python -m benchmark.run_bird --questions data/bird/splits/train_dev.json \
        --db-dir data/bird/train/train_databases --limit 100 --seed 1
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import statistics
import subprocess
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from benchmark.bird import (
    DEFAULT_DB_DIR,
    DEFAULT_QUESTIONS,
    BirdQuestion,
    database_fingerprint,
    dataset_fingerprint,
    db_path_for,
    load_questions,
    with_evidence,
)
from benchmark.evaluate import BIRD_OFFICIAL_TIMEOUT_S, score_bird
from src.agent import Agent
from src.conversation import ConversationContext
from src.costs import MODEL_DEEPSEEK, get_shared_budget
from src.db import connect_readonly
from src.prompts import SYSTEM_PROMPT
from src.schema import get_schema

DIFFICULTIES = ("simple", "moderate", "challenging", "unknown")


def select_questions(args: argparse.Namespace) -> list[BirdQuestion]:
    questions = load_questions(args.questions)
    if args.difficulty:
        questions = [q for q in questions if q.difficulty in args.difficulty]
    if args.db:
        questions = [q for q in questions if q.db_id in args.db]
    rng = random.Random(args.seed)
    if args.per_db is not None:
        # Stratified pilot: the same number of rows from every database, so a small sample
        # still exercises each schema instead of mostly the largest database.
        by_db: dict[str, list[BirdQuestion]] = defaultdict(list)
        for question in questions:
            by_db[question.db_id].append(question)
        questions = [
            q for rows in by_db.values() for q in rng.sample(rows, min(args.per_db, len(rows)))
        ]
    if args.limit is not None and args.limit < len(questions):
        questions = list(questions)
        rng.shuffle(questions)
        questions = questions[: args.limit]
    if args.ids:
        # Targeted cases (e.g. rows that exercise the change under test) join the sample.
        chosen = {q.row_index for q in questions}
        wanted = set(args.ids)
        questions += [
            q for q in load_questions(args.questions)
            if q.question_id in wanted and q.row_index not in chosen
        ]
    # Order by database: consecutive requests share a schema prompt prefix, which is what
    # lets the provider's prompt cache (cached input is ~30x cheaper) actually hit.
    return sorted(questions, key=lambda q: (q.db_id, q.row_index))


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
            db_path = db_path_for(question.db_id, db_dir=args.db_dir)
            conn = connect_readonly(db_path)
            try:
                agent = Agent(
                    model,
                    conn,
                    guard,
                    db_path=db_path,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    request_options=(
                        {"reasoning_effort": args.reasoning_effort}
                        if args.reasoning_effort
                        else None
                    ),
                )
                result = await agent.ask(
                    with_evidence(question.question, question.evidence),
                    ConversationContext(get_schema(db_path)),
                )
            finally:
                conn.close()
            if result.error_category == "budget-exceeded":
                stop.set()
            record = asdict(result)
            record.update(
                row_index=question.row_index,
                question_id=question.question_id,
                db_id=question.db_id,
                difficulty=question.difficulty,
                model=model,
                repeat=repeat,
                concurrency=args.concurrency,
            )
            eval_conn = connect_readonly(db_path, timeout_seconds=BIRD_OFFICIAL_TIMEOUT_S)
            try:
                # One execution of gold and generated SQL feeds every metric. Only SQL the
                # agent actually delivered counts officially; a rejected query is no answer.
                score = score_bird(
                    eval_conn,
                    str(question.question_id),
                    question.gold_sql,
                    result.sql,
                    delivered=result.error is None,
                )
                record["evaluation"] = asdict(score.evaluation)
                record["official_ex"] = score.official_ex
                record["result_signature"] = score.signature
                record["result_row_count"] = score.row_count
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
    meta = run_metadata(args, questions)
    delivered = {
        (r["model"], r["row_index"], r["repeat"])
        for r in records
        if r.get("error_category") != "budget-exceeded"
    }
    meta.update(
        expected_rows=sorted(question.row_index for question in questions),
        expected_repeats=args.repeats,
        # False after a budget stop or any missing (model, row, repeat): such a file can
        # only be compared as a pilot, never as full acceptance evidence.
        complete=not stop.is_set() and len(delivered) == len(jobs),
    )
    output.with_name(f"bird_meta_{timestamp}.json").write_text(
        json.dumps(meta, indent=1) + "\n"
    )
    Path(args.report).write_text(build_bird_report(records, len(questions)))
    return output


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def run_metadata(
    args: argparse.Namespace, questions: list[BirdQuestion]
) -> dict[str, Any]:
    """Everything needed to decide whether two runs are comparable.

    Pins *contents*, not paths: the question file, every database scored against, the
    effective system prompt per database (template + rendered schema, so a ``schema.py``
    change shows up), the generation configuration, and the code state including
    uncommitted edits and untracked files under ``src/`` and ``benchmark/``.
    """

    def git(*command: str) -> str:
        try:
            return subprocess.run(
                ["git", *command], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return "unknown"

    db_ids = sorted({question.db_id for question in questions})
    db_paths = {db_id: db_path_for(db_id, db_dir=args.db_dir) for db_id in db_ids}
    prompts = {
        db_id: _sha16(SYSTEM_PROMPT.format(schema=get_schema(path)))
        for db_id, path in db_paths.items()
    }
    config = {
        "models": args.models,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "reasoning_effort": args.reasoning_effort,
        "max_repairs": 1,
    }
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "src", "benchmark")
    code_state = git("diff", "HEAD", "--", "src", "benchmark") + "".join(
        Path(name).read_text(errors="replace") for name in sorted(untracked.split()) if name
    )
    return {
        "questions": str(args.questions),
        "dataset_sha256_16": dataset_fingerprint(args.questions),
        "db_dir": str(args.db_dir),
        "database_sha256_16": {
            db_id: database_fingerprint(path) for db_id, path in db_paths.items()
        },
        "question_count": len(questions),
        "effective_prompt_sha256_16": _sha16(json.dumps(prompts, sort_keys=True)),
        "effective_prompt_by_db": prompts,
        "config": config,
        "config_sha256_16": _sha16(json.dumps(config, sort_keys=True)),
        "git_commit": git("rev-parse", "HEAD").strip(),
        "code_state_sha256_16": _sha16(code_state),
        "git_dirty": bool(code_state),
        "repeats": args.repeats,
        "difficulty": args.difficulty,
        "db": args.db,
        "limit": args.limit,
        "per_db": args.per_db,
        "ids": args.ids,
        "seed": args.seed,
    }


def is_correct(record: dict[str, Any]) -> bool:
    """Official BIRD EX when recorded; the local contract-aware metric for older runs."""
    if "official_ex" in record:
        return bool(record["official_ex"])
    return bool(record.get("evaluation", {}).get("sql_equivalent"))


def build_bird_report(records: list[dict[str, Any]], question_count: int) -> str:
    lines = [
        "# BIRD-SQL Mini-Dev Report",
        "",
        (
            f"Local execution-accuracy (EX) run against {question_count} Mini-Dev questions "
            "(public dev-labels), using the same schema-grounded agent as the Chinook bake-off. "
            "**Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a "
            "held-out test set through its own process; this is a comparable local proxy. "
            "Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, "
            "`benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back "
            "to the local contract-aware metric. "
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
        overall = [row for row in records if row["model"] == model]
        for label, rows in [*rows_by_difficulty, ("overall", overall)]:
            if not rows:
                continue
            correct = sum(is_correct(row) for row in rows)
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

    lines.extend(["", "## Per-database accuracy", "", "| db_id | N | Exec Acc |", "|---|---:|---:|"])
    by_db: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_db[record["db_id"]].append(record)
    for db_id, rows in sorted(
        by_db.items(),
        key=lambda kv: sum(is_correct(r) for r in kv[1])
        / len(kv[1]),
    ):
        correct = sum(is_correct(row) for row in rows)
        lines.append(f"| `{db_id}` | {len(rows)} | {correct / len(rows):.1%} |")
    if by_db:
        macro = statistics.mean(
            sum(is_correct(row) for row in rows) / len(rows) for rows in by_db.values()
        )
        lines.append(f"| **macro (mean over databases)** | {len(by_db)} DBs | {macro:.1%} |")

    lines.extend(["", "## Failure analysis"])
    failures = [r for r in records if not is_correct(r)]
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
    parser.add_argument(
        "--per-db", type=int, default=None, help="Stratified sample: at most N rows per database."
    )
    parser.add_argument(
        "--ids", type=int, nargs="+", help="Question ids to add as targeted cases."
    )
    parser.add_argument("--seed", type=int, default=0, help="Sampling seed for --limit/--per-db.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument(
        "--reasoning-effort",
        help="Override the per-model default (e.g. none/low/medium/high).",
    )
    parser.add_argument("--report", default="benchmark/results/bird_report.md")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    output = asyncio.run(benchmark(parse_args()))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
