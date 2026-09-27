"""Preregistered Jev shadow scorecard on saved train_dev SQL; never changes answers.

The input labels are hand audited from the original question, evidence, and delivered SQL,
without gold. Default mode only validates/builds requests. --run dispatches paid calls.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlglot import exp, parse_one

from benchmark.bird import dataset_fingerprint, db_path_for, load_questions
from src.costs import DEFAULT_LEDGER, BudgetGuard
from src.jev import JevClient, JevConfig, JevError

REQUIREMENTS = {
    "negation": "the stated exclusion, negation, or upper-bound condition",
    "ratio": "the requested percentage or ratio, including its numerator and denominator",
    "time": "the requested date/time condition or date/time output",
    "extreme": "the highest/lowest or most/least criterion, including its scope and metric",
}
FLAG_THRESHOLD = 0.8  # fixed before any Jev call


def sql_facts(sql: str) -> dict[str, Any]:
    """Deterministic structural facts; no gold or result rows."""
    try:
        tree = parse_one(sql, read="sqlite")
    except Exception:  # noqa: BLE001 - malformed saved SQL is represented as no AST
        return {"parse_error": True}
    if tree is None:
        return {"parse_error": True}
    return {
        "tables": sorted({t.name for t in tree.find_all(exp.Table)}),
        "columns": sorted({c.sql(dialect="sqlite") for c in tree.find_all(exp.Column)})[:40],
        "where": [w.sql(dialect="sqlite")[:500] for w in tree.find_all(exp.Where)][:3],
        "group_by": [g.sql(dialect="sqlite")[:300] for g in tree.find_all(exp.Group)][:2],
        "order_by": [o.sql(dialect="sqlite")[:300] for o in tree.find_all(exp.Order)][:2],
        "limit": any(True for _ in tree.find_all(exp.Limit)),
        "functions": sorted({f.key.upper() for f in tree.find_all(exp.Func)})[:25],
    }


def schema_slice(db_path: Path, tables: list[str], *, max_tables: int = 3) -> dict[str, list[str]]:
    """Only actual columns of up to three SQL-referenced tables, never sample rows."""
    schema: dict[str, list[str]] = {}
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as db:
        for table in tables[:max_tables]:
            quoted = table.replace('"', '""')
            rows = db.execute(f'PRAGMA table_info("{quoted}")').fetchall()
            if rows:
                schema[table] = [str(row[1]) for row in rows[:20]]
    return schema


def decision_request(
    question: Any, record: dict[str, Any], kind: str, db_dir: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if kind not in REQUIREMENTS:
        raise ValueError(f"Unknown requirement kind: {kind}")
    sql = str(record.get("sql") or "")
    facts = sql_facts(sql)
    state = {
        "question": question.question,
        "evidence": question.evidence,
        "candidate_sql": sql,
        "sql_facts": facts,
        "schema_shortlist": schema_slice(
            db_path_for(question.db_id, db_dir=db_dir), facts.get("tables", [])
        ),
        "execution": {
            "error_category": record.get("error_category"),
            "row_count": len(record.get("rows") or []),
        },
    }
    spec = {
        "omitted": {
            "type": "noul",
            "instructions": (
                f"Does the candidate SQL omit or misapply {REQUIREMENTS[kind]} "
                "from the original question? Judge only this one requirement. "
                "Use the evidence as a hint but preserve the original question. "
                "An equivalent SQL formulation counts as present."
            ),
            "criteria": {
                "true": "This specific requested requirement is omitted or applied incorrectly.",
                "false": "This specific requested requirement is correctly represented in the SQL.",
            },
        }
    }
    return state, spec


def deterministic_flag(kind: str, facts: dict[str, Any], sql: str) -> bool:
    """Cheap structural baseline; deliberately abstains from semantic guesses."""
    upper = sql.upper()
    if kind == "ratio":
        return "/" not in sql
    if kind == "extreme":
        return not (facts.get("order_by") or "MAX(" in upper or "MIN(" in upper)
    if kind == "negation":
        return not any(x in upper for x in (" NOT ", " != ", " <> ", " < ", " <= ", " EXCEPT "))
    if kind == "time":
        return not any(
            x in upper for x in ("DATE", "YEAR", "MONTH", "TIME", "STRFTIME", "20", "19")
        )
    raise ValueError(kind)


def scorecard(items: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [x for x in items if isinstance(x.get("jev_probability"), (int, float))]
    if not completed:
        return {"completed": 0}

    def confusion(field: str) -> dict[str, int]:
        counts = Counter((bool(x["omitted"]), bool(x[field])) for x in completed)
        return {
            "tp": counts[(True, True)],
            "fp": counts[(False, True)],
            "tn": counts[(False, False)],
            "fn": counts[(True, False)],
        }

    latencies = sorted(float(x["latency_ms"]) for x in completed)
    jev = confusion("jev_flag")
    return {
        "completed": len(completed),
        "positive_labels": sum(bool(x["omitted"]) for x in completed),
        "threshold": FLAG_THRESHOLD,
        "jev": jev,
        "deterministic": confusion("deterministic_flag"),
        "jev_precision": jev["tp"] / (jev["tp"] + jev["fp"]) if jev["tp"] + jev["fp"] else None,
        "jev_recall": jev["tp"] / (jev["tp"] + jev["fn"]) if jev["tp"] + jev["fn"] else None,
        "jev_brier": statistics.mean(
            (float(x["jev_probability"]) - float(x["omitted"])) ** 2 for x in completed
        ),
        "false_flags_on_correct_sql": sum(x["jev_flag"] and x["official_ex"] for x in completed),
        "correct_sql_controls": sum(x["official_ex"] for x in completed),
        "cost_usd": sum(float(x["cost_usd"]) for x in completed),
        "p50_ms": latencies[len(latencies) // 2],
        "p90_ms": latencies[min(len(latencies) - 1, int(0.9 * len(latencies)))],
    }


async def run(args: argparse.Namespace) -> None:
    manifest = json.loads(await asyncio.to_thread(args.labels.read_text))
    source = Path(manifest["source"])
    assert dataset_fingerprint(source) == manifest["source_sha256_16"]
    questions = {q.row_index: q for q in load_questions(source)}
    raw_text = await asyncio.to_thread(Path(manifest["raw"]).read_text)
    raw_sha256_16 = dataset_fingerprint(Path(manifest["raw"]))
    if raw_sha256_16 != manifest["raw_sha256_16"]:
        raise SystemExit("Saved predictions changed since Jev labels were frozen")
    records = {
        row["row_index"]: row
        for row in (json.loads(line) for line in raw_text.splitlines())
        if row["repeat"] == 0
    }
    chosen = manifest["items"][: args.max_calls]
    if any(not isinstance(item.get("omitted"), bool) for item in chosen):
        raise SystemExit("Hand labels must be completed before running Jev")
    prepared = []
    for item in chosen:
        row = item["row_index"]
        question, record = questions[row], records[row]
        assert question.db_id == item["db_id"]
        state, spec = decision_request(question, record, item["kind"], args.db_dir)
        assert "gold_sql" not in state and "official_ex" not in state
        prepared.append((item, record, state, spec))
    print(
        json.dumps(
            {
                "prepared": len(prepared),
                "mean_state_chars": round(statistics.mean(len(json.dumps(x[2])) for x in prepared)),
                "labeled_omissions": sum(x[0]["omitted"] for x in prepared),
                "mode": "paid shadow" if args.run else "free preflight",
            }
        )
    )
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        prior_rows = [x.get("row_index") for x in prior.get("results", [])]
        expected_rows = [x[0]["row_index"] for x in prepared]
        if (
            prior.get("source") == manifest["raw"]
            and prior.get("raw_sha256_16") == raw_sha256_16
            and prior_rows == expected_rows
        ):
            print(json.dumps(prior.get("scorecard", {}), indent=2))
            return  # complete prior run: never pay twice by accident
        raise SystemExit("Partial Jev output exists; refusing duplicate paid calls")
    if args.env_file:
        load_dotenv(args.env_file)
    config = JevConfig.from_env()
    guard = BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path)
    client = JevClient(config, guard)
    results = []
    for item, record, state, spec in prepared:
        try:
            answer = await client.decide(state, spec)
        except JevError as exc:
            results.append({"row_index": item["row_index"], "error": str(exc)})
            break  # no repeated charges after an unknown endpoint failure
        probability = float(answer.answers["omitted"]["noul"])
        results.append(
            {
                **item,
                "jev_probability": probability,
                "jev_flag": probability >= FLAG_THRESHOLD,
                "deterministic_flag": deterministic_flag(
                    item["kind"], state["sql_facts"], str(record["sql"])
                ),
                "official_ex": bool(record["official_ex"]),
                "model_version": answer.model_version,
                "cost_usd": answer.cost_usd,
                "latency_ms": answer.latency_ms,
            }
        )
        args.output.write_text(
            json.dumps(
                {
                    "source": manifest["raw"],
                    "raw_sha256_16": raw_sha256_16,
                    "results": results,
                    "scorecard": scorecard(results),
                },
                indent=2,
            )
            + "\n"
        )
    print(json.dumps(scorecard(results), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels", type=Path, default=Path("benchmark/results/jev_shadow_v1_labels.json")
    )
    parser.add_argument("--db-dir", type=Path, default=Path("data/bird/train/train_databases"))
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=50)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark/results/jev_shadow_v1_results.json")
    )
    parser.add_argument(
        "--run", action="store_true", help="Make paid Jev calls; omitted by default"
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
