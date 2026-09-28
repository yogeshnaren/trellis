"""Question-intent Jev shadow against frozen human labels; no SQL generation.

The regex baseline was frozen on a different 25-question development sample. This
script evaluates a separate hash-selected sample. Default mode is free preflight;
--run is the only path that sends paid OpenRouter requests.
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

INTENTS = {
    "ratio": "A ratio, rate, percentage, proportion, or fraction must be computed or returned.",
    "temporal": "A date, time, season, or ordered event constrains the answer, or a date/time is requested as output.",
    "upper_bound": "The question requires negation, exclusion, absence, or an upper-bound condition.",
    "extreme": "The question asks for a highest, lowest, first, last, best, top, or similar extremum.",
}
# Frozen before opening the validation sample. Match the original question, not the hint.
RULES = {
    "ratio": r"\b(?:percent(?:age)?|rate|ratio|proportion|fraction)\b",
    "temporal": r"\b(?:20\d{2}|19\d{2}|january|february|march|april|may|june|july|august|september|october|november|december|season|date|month|year|first match|earliest|latest|end of \d+ overs)\b",
    "upper_bound": r"\b(?:not|no more than|less than|below|under|at most|without)\b",
    "extreme": r"\b(?:highest|lowest|biggest|most|least|top|earliest|latest|youngest|maximum|minimum|best|longest|tallest|first match)\b",
}
THRESHOLD = 0.5


def request(question: Any) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    state = {"question": question.question, "evidence_hint": question.evidence}
    specs = {
        name: {
            "type": "noul",
            "instructions": (
                f"From the original question, is this requirement present: {meaning} "
                "The evidence hint may clarify wording but must not add an unasked requirement."
            ),
            "criteria": {"true": "Requirement is present", "false": "Requirement is absent"},
        }
        for name, meaning in INTENTS.items()
    }
    return state, specs


def rule_flags(question: str) -> dict[str, bool]:
    return {
        name: bool(re.search(pattern, question, re.IGNORECASE)) for name, pattern in RULES.items()
    }


def _confusion(labels: list[bool], pred: list[bool]) -> dict[str, int]:
    count = Counter(zip(labels, pred, strict=True))
    return {
        "tp": count[(True, True)],
        "fp": count[(False, True)],
        "tn": count[(False, False)],
        "fn": count[(True, False)],
    }


def scorecard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"completed": 0}
    by_intent = {}
    for name in INTENTS:
        labels = [name in row["intents"] for row in rows]
        rule = [row["rule_flags"][name] for row in rows]
        jev = [row["jev_flags"][name] for row in rows]

        by_intent[name] = {
            "positives": sum(labels),
            "rule": _confusion(labels, rule),
            "jev": _confusion(labels, jev),
            "brier": statistics.mean(
                (row["jev_probabilities"][name] - float(label)) ** 2
                for row, label in zip(rows, labels, strict=True)
            ),
        }
    return {
        "completed": len(rows),
        "threshold": THRESHOLD,
        "by_intent": by_intent,
        "exact_match_rule": sum(
            all(row["rule_flags"][n] == (n in row["intents"]) for n in INTENTS) for row in rows
        ),
        "exact_match_jev": sum(
            all(row["jev_flags"][n] == (n in row["intents"]) for n in INTENTS) for row in rows
        ),
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "p50_ms": statistics.median(row["latency_ms"] for row in rows),
    }


async def run(args: argparse.Namespace) -> None:
    manifest = json.loads(args.labels.read_text())
    source = Path(manifest["source"])
    sha = dataset_fingerprint(source)
    if sha != manifest["source_sha256_16"]:
        raise SystemExit("Question set changed since intent labels were frozen")
    questions = {q.row_index: q for q in load_questions(source)}
    selected = manifest["items"][: args.max_calls]
    prepared = []
    for item in selected:
        q = questions[item["row_index"]]
        if q.db_id != item["db_id"] or set(item["intents"]) - INTENTS.keys():
            raise SystemExit("Invalid frozen intent label")
        state, spec = request(q)
        prepared.append((item, q, state, spec))
    print(
        json.dumps(
            {
                "mode": "paid shadow" if args.run else "free preflight",
                "prepared": len(prepared),
                "positive_labels": Counter(
                    n for item, _, _, _ in prepared for n in item["intents"]
                ),
            }
        )
    )
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if prior.get("source_sha256_16") == sha and [
            r.get("row_index") for r in prior.get("results", [])
        ] == [x[0]["row_index"] for x in prepared]:
            print(json.dumps(prior["scorecard"], indent=2))
            return
        raise SystemExit("Partial intent output exists; refusing duplicate paid calls")
    if args.env_file:
        load_dotenv(args.env_file)
    client = JevClient(
        JevConfig.from_env(),
        BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path),
    )
    results = []
    for item, q, state, spec in prepared:
        try:
            answer = await client.decide(state, spec)
        except JevError as exc:
            results.append({"row_index": item["row_index"], "error": str(exc)})
            break
        probabilities = {name: float(answer.answers[name]["noul"]) for name in INTENTS}
        results.append(
            {
                **item,
                "rule_flags": rule_flags(q.question),
                "jev_probabilities": probabilities,
                "jev_flags": {
                    name: probability >= THRESHOLD for name, probability in probabilities.items()
                },
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
    print(json.dumps(scorecard([r for r in results if "jev_flags" in r]), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels", type=Path, default=Path("benchmark/results/jev_intent_v1_labels.json")
    )
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=24)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark/results/jev_intent_v1_results.json")
    )
    parser.add_argument("--run", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
