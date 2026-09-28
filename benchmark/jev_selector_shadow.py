"""Jev choice diagnostic on the saved four-family train_dev bank; no SQL changes.

The bank predates bounded facts, so this is selector feasibility only. Default mode
builds all requests and scores the no-Jev bank without paid calls. --run calls Jev.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from benchmark.analyze import load_run
from benchmark.bank import rescore_signatures
from benchmark.bird import db_path_for, load_questions
from benchmark.jev_shadow import schema_slice, sql_facts
from src.costs import DEFAULT_LEDGER, BudgetGuard
from src.jev import JevClient, JevConfig, JevError

BANK = {
    "direct": Path("benchmark/results/bird_raw_20260926T212754Z.jsonl"),
    "decompose": Path("benchmark/results/bird_raw_20260927T045254Z.jsonl"),
    "plan": Path("benchmark/results/bird_raw_20260927T045227Z.jsonl"),
    "glm": Path("benchmark/results/bird_raw_20260927T044613Z.jsonl"),
}
LABELS = "ABCD"


def _sample_rows(record: dict[str, Any]) -> list[str]:
    rows = record.get("rows") or []
    return [repr(row)[:160] for row in rows[:3]]


def majority_label(signatures: dict[str, str | None]) -> str:
    votes = Counter(sig for sig in signatures.values() if sig is not None)
    if not votes:
        return "direct"
    largest = max(votes.values())
    return next(name for name, sig in signatures.items() if sig is not None and votes[sig] == largest)


def make_request(
    question: Any, records: dict[str, dict[str, Any]], signatures: dict[str, str | None], db_dir: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    # One representative per distinct result. The choice labels are assigned in frozen
    # bank order; no official-ex or gold fields are supplied to Jev.
    representatives: dict[str | None, str] = {}
    for name, sig in signatures.items():
        representatives.setdefault(sig, name)
    choices = list(representatives.values())
    mapping = dict(zip(LABELS, choices, strict=False))
    referenced_tables = sorted({
        table
        for name in mapping.values()
        for table in sql_facts(str(records[name].get("sql") or "")).get("tables", [])
    })
    state = {
        "question": question.question,
        "evidence": question.evidence,
        "schema_shortlist": schema_slice(
            db_path_for(question.db_id, db_dir=db_dir), referenced_tables, max_tables=5
        ),
        "candidates": {
            label: {
                "sql": str(records[name].get("sql") or ""),
                "sql_facts": sql_facts(str(records[name].get("sql") or "")),
                "sample_rows": _sample_rows(records[name]),
                "row_count": len(records[name].get("rows") or []),
                "error_category": records[name].get("error_category"),
            }
            for label, name in mapping.items()
        },
    }
    criteria = {
        label: f"Candidate {label} best satisfies the question and evidence."
        for label in mapping
    }
    criteria["none"] = "No candidate reliably satisfies the original question."
    spec = {
        "best": {
            "type": "choice",
            "instructions": (
                "Choose the candidate SQL that best answers the original question, "
                "including requested projection, filters, aggregation, and value meaning. "
                "The evidence is a hint; preserve the question. The sample rows are "
                "incomplete and must not replace SQL reasoning. Choose none if all fail."
            ),
            "criteria": criteria,
        }
    }
    return state, spec, mapping


def scorecard(results: list[dict[str, Any]], uncontested_correct: int, total: int) -> dict[str, Any]:
    if not results:
        return {"completed": 0}
    majority = uncontested_correct + sum(x["majority_correct"] for x in results)
    chosen = uncontested_correct + sum(x["chosen_correct"] for x in results)
    return {
        "completed": len(results),
        "bank_questions": total,
        "uncontested_correct": uncontested_correct,
        "majority_on_completed": sum(x["majority_correct"] for x in results),
        "jev_on_completed": sum(x["chosen_correct"] for x in results),
        "majority_correct_with_completed": majority,
        "jev_correct_with_completed": chosen,
        "net_fixes": sum(x["chosen_correct"] and not x["majority_correct"] for x in results),
        "net_regressions": sum(x["majority_correct"] and not x["chosen_correct"] for x in results),
        "none_choices": sum(x["choice"] == "none" for x in results),
        "cost_usd": sum(float(x["cost_usd"]) for x in results),
        "per_database": {
            db: {
                "n": sum(x["db_id"] == db for x in results),
                "majority": sum(x["db_id"] == db and x["majority_correct"] for x in results),
                "jev": sum(x["db_id"] == db and x["chosen_correct"] for x in results),
            }
            for db in sorted({x["db_id"] for x in results})
        },
    }


async def run(args: argparse.Namespace) -> None:
    questions = load_questions(args.questions)
    by_row = {q.row_index: q for q in questions}
    runs = {name: load_run(path, questions) for name, path in BANK.items()}
    signatures = await asyncio.to_thread(rescore_signatures, runs, by_row, args.db_dir)
    shared = sorted(set.intersection(*(set(run) for run in runs.values())))
    requests = []
    uncontested_correct = 0
    for row in shared:
        row_sigs = {name: signatures[name][row] for name in BANK}
        majority = majority_label(row_sigs)
        if len(set(row_sigs.values())) < 2:
            uncontested_correct += bool(runs[majority][row]["official_ex"])
            continue
        records = {name: runs[name][row] for name in BANK}
        state, spec, mapping = make_request(by_row[row], records, row_sigs, args.db_dir)
        assert "official_ex" not in state and "gold_sql" not in state
        requests.append((row, majority, records, state, spec, mapping))
    paths = {name: hashlib.sha256(path.read_bytes()).hexdigest()[:16] for name, path in BANK.items()}
    print(json.dumps({
        "mode": "paid shadow" if args.run else "free preflight",
        "bank_rows": len(shared), "disagreements": len(requests),
        "uncontested_correct": uncontested_correct,
        "mean_state_chars": round(sum(len(json.dumps(x[3])) for x in requests) / len(requests)),
        "bank_sha256_16": paths,
    }))
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        prior_rows = [x.get("row_index") for x in prior.get("results", [])]
        expected_rows = [x[0] for x in requests[: args.max_calls]]
        if prior.get("bank_sha256_16") == paths and prior_rows == expected_rows:
            print(json.dumps(scorecard(prior["results"], uncontested_correct, len(shared)), indent=2))
            return  # complete prior run: never pay twice by accident
        raise SystemExit("Partial Jev selector output exists; refusing duplicate paid calls")
    if args.env_file:
        load_dotenv(args.env_file)
    config = JevConfig.from_env()
    guard = BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path)
    client = JevClient(config, guard)
    results = []
    for row, majority, records, state, spec, mapping in requests[: args.max_calls]:
        try:
            decision = await client.decide(state, spec)
        except JevError as exc:
            results.append({"row_index": row, "error": str(exc)})
            break
        choice = str(decision.answers["best"]["choice"])
        chosen = mapping.get(choice, majority)
        results.append({
            "row_index": row,
            "db_id": by_row[row].db_id,
            "choice": choice,
            "selected_candidate": chosen,
            "majority_candidate": majority,
            "majority_correct": bool(records[majority]["official_ex"]),
            "chosen_correct": bool(records[chosen]["official_ex"]),
            "model_version": decision.model_version,
            "confidence": decision.answers["best"].get("confidence"),
            "cost_usd": decision.cost_usd,
            "latency_ms": decision.latency_ms,
        })
        args.output.write_text(json.dumps({
            "bank_sha256_16": paths,
            "uncontested_correct": uncontested_correct,
            "bank_rows": len(shared),
            "disagreements": len(requests),
            "results": results,
        }, indent=2) + "\n")
    usable = [x for x in results if "choice" in x]
    print(json.dumps(scorecard(usable, uncontested_correct, len(shared)), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("data/bird/splits/train_dev.json"))
    parser.add_argument("--db-dir", type=Path, default=Path("data/bird/train/train_databases"))
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=102)
    parser.add_argument("--output", type=Path, default=Path("benchmark/results/jev_selector_v1_results.json"))
    parser.add_argument("--run", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
