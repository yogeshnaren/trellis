"""Aggregate real benchmark JSONL into a markdown evidence report."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def build_report(records: list[dict[str, Any]]) -> str:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["model"], record["arm"], record["concurrency"])].append(record)

    lines = [
        "# Model Bake-off Report",
        "",
        (
            "This compares the schema-grounded agent with a same-model raw-prompt control on "
            "DeepSeek-V4-Flash. It is **not** a head-to-head run against a proprietary frontier "
            "model; any such comparison elsewhere in this repo is directional context, not a "
            "benchmark run here."
        ),
        "",
        (
            "Concurrency 1 is authoritative for the interactive P50 < 3s SLO. Concurrency 5 is "
            "reported separately as throughput/load evidence."
        ),
        "",
        "| Model | Arm | Concurrency | SQL Eq | E2E Acc | P50 (s) | P90 (s) | Repair % | Out tok (med) | $/query | $/day @30k |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (model, arm, concurrency), rows in sorted(groups.items()):
        latencies = [float(row["t_total_ms"]) / 1_000 for row in rows]
        sql_eq = sum(
            bool(row.get("evaluation", {}).get("sql_equivalent", row.get("evaluation", {}).get("correct")))
            for row in rows
        )
        e2e = sum(bool(row.get("evaluation", {}).get("e2e_success")) for row in rows)
        costs = [sum(call["cost_usd"] for call in row.get("llm_calls", [])) for row in rows]
        output = [sum(call["output_tokens"] for call in row.get("llm_calls", [])) for row in rows]
        repairs = sum(bool(row.get("repaired")) for row in rows)
        mean_cost = statistics.mean(costs) if costs else 0.0
        lines.append(
            f"| `{model}` | {arm} | {concurrency} | {sql_eq / len(rows):.1%} | "
            f"{e2e / len(rows):.1%} | "
            f"{percentile(latencies, .5):.2f} | {percentile(latencies, .9):.2f} | "
            f"{repairs / len(rows):.1%} | {statistics.median(output) if output else 0:.0f} | "
            f"${mean_cost:.6f} | ${mean_cost * 30_000:.2f} |"
        )

    lines.extend(["", "## Cache-reuse diagnostic"])
    suspicious = []
    by_question: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in records:
        by_question[(row["model"], row["arm"], row["question_id"])].append(
            float(row["t_total_ms"])
        )
    for key, timings in by_question.items():
        if len(timings) > 1 and min(timings) < 0.5 * max(timings):
            suspicious.append(f"- `{key}`: {', '.join(f'{value:.0f}ms' for value in timings)}")
    lines.extend(suspicious or ["No repeat showed a >2× latency spread attributable to possible cache reuse."])

    lines.extend(["", "## Failure analysis"])
    failures = [
        row
        for row in records
        if not row.get("evaluation", {}).get(
            "sql_equivalent", row.get("evaluation", {}).get("correct")
        )
    ]
    if not failures:
        lines.append("No SQL-equivalence failures in the recorded run.")
    else:
        # Repeats/concurrency levels reproduce the same failure deterministically;
        # collapse to one line per distinct (question, model, arm, reason) with a count.
        grouped: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
        for row in failures:
            reason = row.get("evaluation", {}).get("reason") or row.get("error") or "Unknown"
            category = row.get("error_category") or "wrong-result"
            grouped[(row["question_id"], row["model"], row["arm"], reason, category)] += 1
        for (question_id, model, arm, reason, category), count in sorted(grouped.items()):
            occurrences = f" (x{count})" if count > 1 else ""
            lines.append(f"- {question_id} / `{model}` / {arm}: {reason} (category: {category}){occurrences}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark/results/report.md"))
    args = parser.parse_args()
    records = [
        json.loads(line)
        for path in args.inputs
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not records:
        raise SystemExit("No real benchmark records found; refusing to write placeholder report")
    args.output.write_text(build_report(records))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
