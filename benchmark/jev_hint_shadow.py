"""Atomic evidence-hint role shadow; default mode makes no paid calls.

Human roles are fixed from original questions before Jev calls. Gold SQL is not in
Jev state. This tests whether a formula should be returned, filtered, or ranked.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from benchmark.bird import dataset_fingerprint, load_questions
from src.costs import DEFAULT_LEDGER, BudgetGuard
from src.jev import JevClient, JevConfig, JevError

ROLES = {
    "return": "The hinted value or computation belongs in the returned SELECT output.",
    "filter": "The hinted condition restricts rows or groups in WHERE, HAVING, or an equivalent subquery.",
    "rank": "The hinted expression determines the top, bottom, earliest, latest, or other ranked entity to select.",
}


def request(question: Any, focal_hint: str) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    state = {
        "original_question": question.question,
        "full_evidence_hint": question.evidence,
        "focal_hint_fragment": focal_hint,
    }
    spec = {
        "role": {
            "type": "choice",
            "instructions": (
                "For the focal hint fragment only, choose its primary role in answering "
                "the original question. Do not return a value merely because the hint "
                "contains a formula. Use the original question to resolve the role."
            ),
            "criteria": ROLES,
        }
    }
    return state, spec


def rule_role(question: str, focal_hint: str) -> str:
    """Free rule frozen after v1 labels and before the separate v2 sample."""
    hint = focal_hint.lower()
    asked = question.lower()
    if re.search(r"<>|(?<![a-z])[<>](?![a-z])|\bbetween\b", hint):
        return "filter"
    if re.search(r"\b(?:divide|subtract|percentage|percent|rate|range)\b", hint):
        return "return"
    if re.search(r"\b(?:max|min)\s*\(", hint):
        return (
            "return"
            if asked.startswith(("what is the maximum", "what is the earliest", "state the max"))
            else "rank"
        )
    if asked.startswith(("what is", "give", "state", "tell")):
        return "return"
    return "filter"


def scorecard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"completed": 0}
    labels = Counter(row["role"] for row in rows)
    return {
        "completed": len(rows),
        "labels": dict(labels),
        "correct": sum(row["jev_role"] == row["role"] for row in rows),
        "rule_correct": sum(row["rule_role"] == row["role"] for row in rows),
        "accuracy": statistics.mean(row["jev_role"] == row["role"] for row in rows),
        "rule_accuracy": statistics.mean(row["rule_role"] == row["role"] for row in rows),
        "by_role": {
            role: {
                "n": labels[role],
                "correct": sum(row["role"] == role and row["jev_role"] == role for row in rows),
            }
            for role in ROLES
        },
        "confusions": {
            f"{gold}->{pred}": count
            for (gold, pred), count in Counter(
                (row["role"], row["jev_role"]) for row in rows
            ).items()
        },
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "p50_ms": statistics.median(row["latency_ms"] for row in rows),
    }


async def run(args: argparse.Namespace) -> None:
    manifest = json.loads(args.labels.read_text())
    source = Path(manifest["source"])
    sha = dataset_fingerprint(source)
    if sha != manifest["source_sha256_16"]:
        raise SystemExit("Question set changed since hint labels were frozen")
    questions = {q.row_index: q for q in load_questions(source)}
    selected = manifest["items"][: args.max_calls]
    prepared = []
    for item in selected:
        q = questions[item["row_index"]]
        if item["role"] not in ROLES or item["db_id"] != q.db_id:
            raise SystemExit("Invalid frozen role label")
        fragment = item["focal_hint_fragment"]
        if fragment.casefold() not in q.evidence.casefold():
            raise SystemExit(f"Focal hint is not present for row {q.row_index}")
        state, spec = request(q, fragment)
        prepared.append((item, state, spec))
    print(
        json.dumps(
            {
                "mode": "paid shadow" if args.run else "free preflight",
                "prepared": len(prepared),
                "labels": dict(Counter(item["role"] for item, _, _ in prepared)),
            }
        )
    )
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if prior.get("source_sha256_16") == sha and [
            r.get("row_index") for r in prior.get("results", [])
        ] == [item["row_index"] for item, _, _ in prepared]:
            print(json.dumps(prior["scorecard"], indent=2))
            return
        raise SystemExit("Partial hint output exists; refusing duplicate paid calls")
    if args.env_file:
        load_dotenv(args.env_file)
    client = JevClient(
        JevConfig.from_env(),
        BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path),
    )
    results = []
    for item, state, spec in prepared:
        try:
            answer = await client.decide(state, spec)
        except JevError as exc:
            results.append({"row_index": item["row_index"], "error": str(exc)})
            break
        results.append(
            {
                **item,
                "jev_role": answer.answers["role"]["choice"],
                "rule_role": rule_role(state["original_question"], item["focal_hint_fragment"]),
                "confidence": answer.answers["role"]["confidence"],
                "model_version": answer.model_version,
                "cost_usd": answer.cost_usd,
                "latency_ms": answer.latency_ms,
            }
        )
        args.output.write_text(
            json.dumps(
                {
                    "source_sha256_16": sha,
                    "results": results,
                    "scorecard": scorecard(results),
                },
                indent=2,
            )
            + "\n"
        )
    print(json.dumps(scorecard([r for r in results if "jev_role" in r]), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels", type=Path, default=Path("benchmark/results/jev_hint_v1_labels.json")
    )
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=29)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark/results/jev_hint_v1_results.json")
    )
    parser.add_argument("--run", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
