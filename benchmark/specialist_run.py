"""Run a local SQL-specialist model (P16) in its native prompt format and score it.

The specialist (e.g. Arctic-Text2SQL-R1-7B served by a local llama.cpp OpenAI-compatible
server) is prompted the way it was trained: CREATE TABLE schema with example values, the
evidence before the question, free reasoning, and a final ```sql``` block. The extracted SQL
runs through the same safety gate and read-only executor as the agent, and is scored with
BIRD's official rule. Records and the metadata sidecar use the ``run_bird`` format, so
``benchmark.bank`` and ``benchmark.analyze`` read them unchanged. Local calls cost nothing.

    uv run python -m benchmark.specialist_run --questions data/bird/splits/train_dev2_bank.json \\
        --db-dir data/bird/train/train_databases --model local/arctic-text2sql-r1-7b-q4
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.bird import dataset_fingerprint, db_path_for, load_questions
from benchmark.evaluate import official_ex
from src.db import connect_readonly, execute_candidate, timeout_for_database
from src.llm import complete

RESULTS = Path("benchmark/results")
PROMPT = """Task Overview:
You are a data science expert. Below, you are provided with a database schema and a natural language question. Your task is to understand the schema and generate a valid SQL query to answer the question.

Database Engine:
SQLite

Database Schema:
{schema}
This schema describes the database's structure, including tables, columns, primary keys, foreign keys, and any relevant relationships or constraints.

Question:
{question}

Instructions:
- Make sure you only output the information that is asked in the question. If the question asks for a specific column, make sure to only include that column in the SELECT clause, nothing more.
- The generated query should return all of the information asked in the question without any missing or extra information.
- Before generating the final SQL query, please think through the steps of how to write the query.

Output Format:
In your answer, please enclose the generated SQL query in a code block:
```sql
-- Your SQL query
```

Take a deep breath and think step by step to find the correct SQL query."""
_SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def native_schema(db_path: Path, examples: int = 3) -> str:
    """CREATE TABLE statements with a few example values per column, OmniSQL style."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        parts = []
        for name, ddl in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ):
            notes = []
            for col in conn.execute(f'PRAGMA table_info("{name}")').fetchall():
                try:
                    vals = [str(r[0])[:40] for r in conn.execute(
                        f'SELECT DISTINCT "{col[1]}" FROM "{name}" WHERE "{col[1]}" IS NOT NULL LIMIT {examples}')]
                except sqlite3.Error:
                    vals = []
                if vals:
                    notes.append(f"-- {col[1]} examples: {vals}")
            parts.append(f"{ddl};\n" + "\n".join(notes))
        return "\n\n".join(parts)
    finally:
        conn.close()


def extract_sql(text: str) -> str | None:
    blocks = _SQL_BLOCK.findall(text or "")
    sql = blocks[-1].strip() if blocks else None
    return sql.rstrip(";").strip() if sql else None


async def run(args: argparse.Namespace) -> Path:
    all_questions = load_questions(args.questions)
    previous: list[dict[str, Any]] = []
    if args.resume:
        # Continue an interrupted run: keep its saved answers, skip their rows, append the rest.
        raw = Path(args.resume)
        stamp = raw.stem.removeprefix("bird_raw_")
        for line in raw.read_text().splitlines():
            try:
                previous.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a line cut off by the interruption: that question is redone
        raw.write_text("".join(json.dumps(r, default=str) + "\n" for r in previous))
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        raw = RESULTS / f"bird_raw_{stamp}.jsonl"
    done = {int(r["row_index"]) for r in previous}
    questions = [q for q in all_questions if q.row_index not in done]
    schemas: dict[str, str] = {}
    sem = asyncio.Semaphore(args.concurrency)

    async def one(q: Any) -> dict[str, Any]:
        db_path = db_path_for(q.db_id, db_dir=args.db_dir)
        if q.db_id not in schemas:
            schemas[q.db_id] = native_schema(db_path)
        question = f"{q.evidence}\n{q.question}" if q.evidence else q.question
        messages = [{"role": "user", "content": PROMPT.format(schema=schemas[q.db_id], question=question)}]
        started = time.perf_counter()
        async with sem:
            try:
                result = await complete(messages, args.model, max_tokens=args.max_tokens,
                                        temperature=0.0, timeout_s=args.timeout)
                text, error = result.text, None
                calls = [{"text": result.text, "input_tokens": result.input_tokens, "cached_tokens": 0,
                          "output_tokens": result.output_tokens, "latency_ms": result.latency_ms,
                          "model": args.model, "cost_usd": 0.0, "finish_reason": result.finish_reason}]
            except Exception as exc:  # noqa: BLE001 - record the failure and continue the run
                text, error, calls = "", f"model-failed: {type(exc).__name__}", []
        sql = extract_sql(text)
        record: dict[str, Any] = {
            "row_index": q.row_index, "question_id": q.question_id, "db_id": q.db_id,
            "difficulty": q.difficulty, "model": args.model, "repeat": 0, "sql": sql,
            "error": error or (None if sql else "no-sql-block"),
            "error_category": "structured-output-failed" if not sql else None,
            "llm_calls": calls, "official_ex": False, "result_signature": None, "result_row_count": 0,
        }
        if sql:
            conn = connect_readonly(db_path, timeout_seconds=timeout_for_database(db_path, default=30.0))
            try:
                cand = execute_candidate(conn, sql, db_path=db_path)
                record.update(result_signature=cand.signature, result_row_count=cand.row_count,
                              columns=cand.columns, rows=[list(r) for r in cand.rows[:20]])
                if cand.error:
                    record.update(error=cand.error, error_category="execute-failed")
                else:
                    record["official_ex"] = official_ex(conn, q.gold_sql, sql)
            finally:
                conn.close()
        record["t_total_ms"] = (time.perf_counter() - started) * 1_000
        return record

    records: list[dict[str, Any]] = list(previous)
    with raw.open("a" if args.resume else "w") as fh:
        for task in asyncio.as_completed([one(q) for q in questions]):
            rec = await task
            records.append(rec)
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            if len(records) % 25 == 0:
                ok = sum(r["official_ex"] for r in records)
                print(f"{len(records)}/{len(all_questions)} EX {ok / len(records):.1%}", flush=True)
    meta = {
        "questions": str(args.questions), "dataset_sha256_16": dataset_fingerprint(args.questions),
        "db_dir": str(args.db_dir), "question_count": len(all_questions), "repeats": 1,
        "expected_repeats": 1, "expected_rows": [q.row_index for q in all_questions],
        "complete": {int(r["row_index"]) for r in records} == {q.row_index for q in all_questions},
        "resumed": bool(args.resume),
        "config": {"models": [args.model], "prompt_profile": "specialist-native", "temperature": 0.0,
                   "max_tokens": args.max_tokens},
        "config_sha256_16": hashlib.sha256(f"{args.model}|{PROMPT}|{args.max_tokens}".encode()).hexdigest()[:16],
    }
    (RESULTS / f"bird_meta_{stamp}.json").write_text(json.dumps(meta, indent=1))
    ok = sum(r["official_ex"] for r in records)
    print(f"Wrote {raw}: EX {ok}/{len(records)} = {ok / len(records):.1%}")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("--model", required=True, help="e.g. local/arctic-text2sql-r1-7b-q4")
    parser.add_argument("--max-tokens", type=int, default=1536)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", help="path of an interrupted run's bird_raw_*.jsonl to continue")
    args = parser.parse_args()
    if args.limit:
        subset = load_questions(args.questions)[: args.limit]
        tmp = Path(f"/tmp/specialist_subset_{args.limit}.json")
        full = json.loads(Path(args.questions).read_text())
        tmp.write_text(json.dumps(full[: len(subset)]))
        args.questions = tmp
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
