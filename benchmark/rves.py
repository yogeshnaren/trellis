"""R-VES (BIRD's reward-based valid efficiency score) for a saved run, aggregates only.

Follows BIRD's ``evaluation_ves.py`` (mini_dev repo): for each question whose prediction is
correct under the official set comparison, both queries are timed ``iterations`` times; the
per-iteration ratio is gold time / predicted time; values beyond three standard deviations
are dropped and the mean ratio becomes a reward (≥2: 1.25, ≥1: 1, ≥0.5: 0.75, ≥0.25: 0.5,
otherwise 0.25; wrong answers 0). The score is the mean of sqrt(reward) × 100 over all
questions. BIRD's script defaults to more iterations; timings are machine-relative, so only
the ratio to gold is meaningful. Prints totals by difficulty, never per question.

    uv run python -m benchmark.rves --questions data/bird/mini_dev_sqlite.json \\
        --db-dir data/bird/dev_databases 20260930T085941Z
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmark.analyze import delivered_sql
from benchmark.bird import db_path_for, load_questions


def reward(ratio: float) -> float:
    if ratio <= 0:
        return 0.0
    if ratio >= 2:
        return 1.25
    if ratio >= 1:
        return 1.0
    if ratio >= 0.5:
        return 0.75
    if ratio >= 0.25:
        return 0.5
    return 0.25


def clean_abnormal(values: list[float]) -> list[float]:
    mean, std = statistics.fmean(values), statistics.pstdev(values)
    kept = [v for v in values if mean - 3 * std < v < mean + 3 * std]
    return kept or values


def _timed(conn: sqlite3.Connection, sql: str, timeout_s: float) -> float:
    deadline = time.perf_counter() + timeout_s
    conn.set_progress_handler(lambda: int(time.perf_counter() > deadline), 10_000)
    started = time.perf_counter()
    conn.execute(sql).fetchall()
    return time.perf_counter() - started


def time_ratio(db_path: Path, gold: str, predicted: str, iterations: int, timeout_s: float) -> float:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        ratios = []
        for _ in range(iterations):
            pred_t = _timed(conn, predicted, timeout_s)
            gold_t = _timed(conn, gold, timeout_s)
            ratios.append(gold_t / max(pred_t, 1e-9))
        kept = clean_abnormal(ratios)
        return sum(kept) / len(kept)
    except sqlite3.Error:
        return 0.0
    finally:
        conn.close()


def rves(questions_path: Path, db_dir: Path, run: str, iterations: int, timeout_s: float,
         repeat: int = 0) -> dict[str, Any]:
    questions = {q.row_index: q for q in load_questions(questions_path)}
    with open(f"benchmark/results/bird_raw_{run}.jsonl") as handle:
        records = [json.loads(line) for line in handle]
    records = [r for r in records if int(r.get("repeat", 0)) == repeat]
    by_tier: dict[str, list[float]] = defaultdict(list)
    rewards: dict[str, list[float]] = defaultdict(list)
    for rec in records:
        q = questions[rec["row_index"]]
        sql = delivered_sql(rec)
        r = 0.0
        if rec.get("official_ex") and sql:
            r = reward(time_ratio(db_path_for(q.db_id, db_dir=db_dir), q.gold_sql, sql, iterations, timeout_s))
        for tier in (q.difficulty, "all"):
            by_tier[tier].append(math.sqrt(r) * 100)
            if r:
                rewards[tier].append(r)
    return {tier: {"questions": len(v), "r_ves": round(sum(v) / len(v), 2),
                   "ex": round(100 * len(rewards[tier]) / len(v), 2),
                   "reward_mix": {str(k): sum(1 for x in rewards[tier] if x == k) for k in (1.25, 1.0, 0.75, 0.5, 0.25)}}
            for tier, v in by_tier.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("run")
    args = parser.parse_args()
    out = rves(args.questions, args.db_dir, args.run, args.iterations, args.timeout, args.repeat)
    print(json.dumps({"run": args.run, "iterations": args.iterations, "repeat": args.repeat, **out}, indent=1))


if __name__ == "__main__":
    main()
