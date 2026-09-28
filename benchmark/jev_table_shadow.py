"""Bounded table-selection Jev shadow on a frozen soccer train_dev pilot.

Gold table names are used only after Jev answers, for scoring. The shortlist is
built from question/evidence and verified SQLite schema, never from gold SQL.
Default mode performs a free preflight; --run permits bounded paid calls.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import statistics
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlglot import exp, parse_one

from benchmark.bird import database_fingerprint, dataset_fingerprint, db_path_for, load_questions
from benchmark.jev_shadow import schema_slice
from src.costs import DEFAULT_LEDGER, BudgetGuard
from src.jev import JevClient, JevConfig, JevError

STOPWORDS = {
    "id",
    "name",
    "number",
    "date",
    "year",
    "time",
    "type",
    "code",
    "the",
    "of",
    "for",
    "and",
    "which",
    "what",
    "how",
    "many",
    "with",
    "from",
    "each",
    "are",
    "was",
    "were",
    "that",
    "all",
    "in",
    "on",
    "to",
    "by",
    "is",
    "as",
    "a",
    "an",
    "per",
}
SHORTLIST_SIZE = 8


def words(value: str) -> set[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", spaced)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def table_catalog(db_path: Path) -> dict[str, list[str]]:
    catalog = {}
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as db:
        names = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in names:
            quoted = table.replace('"', '""')
            catalog[table] = [str(r[1]) for r in db.execute(f'PRAGMA table_info("{quoted}")')]
    return catalog


def shortlist(question: Any, catalog: dict[str, list[str]]) -> list[str]:
    asked = words(question.question + " " + question.evidence)
    vocabulary = {t: words(t + " " + " ".join(cols)) for t, cols in catalog.items()}
    return sorted(
        catalog,
        key=lambda table: (
            len(asked & vocabulary[table]),
            len(asked & words(table)),
            -len(vocabulary[table]),
        ),
        reverse=True,
    )[:SHORTLIST_SIZE]


def foreign_key_edges(db_path: Path, tables: list[str]) -> list[str]:
    """Verified join edges touching shortlisted tables, including lookup parents."""
    edges = []
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as db:
        for table in tables:
            quoted = table.replace('"', '""')
            for row in db.execute(f'PRAGMA foreign_key_list("{quoted}")'):
                edges.append(f"{table}.{row[3]} -> {row[2]}.{row[4]}")
    return sorted(edges)


def request(
    question: Any, tables: list[str], db_path: Path, *, with_fk: bool = False
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    state = {
        "question": question.question,
        "evidence_hint": question.evidence,
        "verified_schema_shortlist": schema_slice(db_path, tables, max_tables=SHORTLIST_SIZE),
    }
    if with_fk:
        state["verified_foreign_keys"] = foreign_key_edges(db_path, tables)
    specs = {
        f"table_{i}": {
            "type": "noul",
            "instructions": (
                f"Would a correct SQLite query for the original question need table {table!r} "
                "to obtain requested data or join required entities? The evidence is only a hint."
            ),
            "criteria": {
                "true": "This table is needed for the original question.",
                "false": "This table is not needed for the original question.",
            },
        }
        for i, table in enumerate(tables)
    }
    return state, specs


def gold_tables(sql: str) -> set[str]:
    try:
        tree = parse_one(sql, read="sqlite")
    except Exception:  # noqa: BLE001 - a malformed gold query cannot label table use
        return set()
    if tree is None:
        return set()
    return {table.name.lower() for table in tree.find_all(exp.Table)}


def scorecard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"completed": 0}

    def policy(which: str) -> dict[str, float | int]:
        tp = fp = fn = complete = 0
        for row in rows:
            gold = set(row["gold_tables"])
            chosen = set(row[which])
            tp += len(gold & chosen)
            fp += len(chosen - gold)
            fn += len(gold - chosen)
            complete += gold <= chosen
        return {
            "all_gold_present": complete,
            "table_precision": tp / (tp + fp) if tp + fp else 0,
            "table_recall": tp / (tp + fn) if tp + fn else 0,
            "table_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            "selected_tables_per_question": sum(len(row[which]) for row in rows) / len(rows),
        }

    return {
        "completed": len(rows),
        "top3": policy("top3"),
        "all8": policy("all8"),
        "jev_threshold_0_5": policy("jev_tables"),
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "p50_ms": statistics.median(row["latency_ms"] for row in rows),
    }


async def run(args: argparse.Namespace) -> None:
    if dataset_fingerprint(args.questions) != args.questions_sha256_16:
        raise SystemExit("Question set changed since the table-selection sample was frozen")
    all_questions = load_questions(args.questions)
    sample = sorted(
        (q for q in all_questions if q.db_id == args.db_id),
        key=lambda q: hashlib.sha256(f"jev-table-v1:{q.row_index}".encode()).digest(),
    )[: args.max_calls]
    db_path = db_path_for(args.db_id, db_dir=args.db_dir)
    db_sha256_16 = database_fingerprint(db_path)
    catalog = table_catalog(db_path)
    prepared = []
    for q in sample:
        gold = gold_tables(q.gold_sql)
        if not gold:
            raise SystemExit(f"No parseable gold table label for row {q.row_index}")
        tables = shortlist(q, catalog)
        state, specs = request(q, tables, db_path, with_fk=args.with_fk)
        assert "gold" not in state and "SQL" not in state
        prepared.append((q, gold, tables, state, specs))
    ceiling = sum(gold <= {table.lower() for table in tables} for _, gold, tables, _, _ in prepared)
    print(
        json.dumps(
            {
                "mode": "paid shadow" if args.run else "free preflight",
                "prepared": len(prepared),
                "tables_in_database": len(catalog),
                "shortlist_size": SHORTLIST_SIZE,
                "all_gold_in_shortlist": ceiling,
                "mean_state_chars": round(statistics.mean(len(json.dumps(x[3])) for x in prepared)),
            }
        )
    )
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if (
            prior.get("questions_sha256_16") == args.questions_sha256_16
            and prior.get("db_id", "soccer_2016") == args.db_id
            and prior.get("database_sha256_16") == db_sha256_16
            and prior.get("with_fk", False) == args.with_fk
            and [r.get("row_index") for r in prior.get("results", [])]
            == [q.row_index for q, _, _, _, _ in prepared]
        ):
            print(json.dumps(prior["scorecard"], indent=2))
            return
        raise SystemExit("Partial table output exists; refusing duplicate paid calls")
    if args.env_file:
        load_dotenv(args.env_file)
    client = JevClient(
        JevConfig.from_env(),
        BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path),
    )
    results = []
    for q, gold, tables, state, specs in prepared:
        try:
            answer = await client.decide(state, specs)
        except JevError as exc:
            results.append({"row_index": q.row_index, "error": str(exc)})
            break
        probabilities = {
            table: float(answer.answers[f"table_{i}"]["noul"]) for i, table in enumerate(tables)
        }
        results.append(
            {
                "row_index": q.row_index,
                "gold_tables": sorted(gold),
                "top3": [t.lower() for t in tables[:3]],
                "all8": [t.lower() for t in tables],
                "jev_tables": [t.lower() for t in tables if probabilities[t] >= 0.5],
                "jev_probabilities": probabilities,
                "model_version": answer.model_version,
                "cost_usd": answer.cost_usd,
                "latency_ms": answer.latency_ms,
            }
        )
        args.output.write_text(
            json.dumps(
                {
                    "questions_sha256_16": args.questions_sha256_16,
                    "db_id": args.db_id,
                    "database_sha256_16": db_sha256_16,
                    "with_fk": args.with_fk,
                    "selection": f"sha256(jev-table-v1:row_index), {args.db_id}, {args.max_calls} rows",
                    "results": results,
                    "scorecard": scorecard(results),
                },
                indent=2,
            )
            + "\n"
        )
    print(json.dumps(scorecard([r for r in results if "jev_tables" in r]), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("data/bird/splits/train_dev.json"))
    parser.add_argument("--db-id", default="soccer_2016")
    parser.add_argument("--questions-sha256-16", default="e5503cce83be1678")
    parser.add_argument("--db-dir", type=Path, default=Path("data/bird/train/train_databases"))
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=50)
    parser.add_argument("--with-fk", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark/results/jev_table_v1_results.json")
    )
    parser.add_argument("--run", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
