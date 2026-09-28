"""Frozen train_dev2 Jev advisory pilot; preparing is free, --run is paid Jev only.

Fireworks generation uses benchmark.run_bird with the resulting annotation file.
The pilot never sends gold SQL to Jev and never removes tables from the schema.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from benchmark.bird import database_fingerprint, dataset_fingerprint, db_path_for, load_questions
from benchmark.jev_hint_shadow import request as hint_request
from benchmark.jev_table_shadow import request as table_request
from benchmark.jev_table_shadow import shortlist, table_catalog
from src.costs import DEFAULT_LEDGER, BudgetGuard
from src.jev import JevClient, JevConfig, JevError

SOURCE = Path("data/bird/splits/train_dev2.json")
PILOT = Path("benchmark/results/jev_live_pilot_questions.json")
MANIFEST = Path("benchmark/results/jev_live_pilot_manifest.json")
PRIOR_TABLE = Path("benchmark/results/jev_table_pb_v1_results.json")
HINT_PATTERN = re.compile(r"\b(?:max|min|avg|sum|count|divide|subtract)\s*\(|[<>]", re.IGNORECASE)
PER_DB = 25


def hint_fragment(evidence: str) -> str | None:
    """Select a single formula/comparison hint without looking at any SQL label."""
    if not evidence or ";" in evidence or len(re.findall("refers to", evidence, re.IGNORECASE)) > 1:
        return None
    return evidence.strip() if HINT_PATTERN.search(evidence) else None


def prepare_sample() -> None:
    if PILOT.exists() or MANIFEST.exists():
        raise SystemExit("Frozen pilot files already exist; refusing to replace them")
    raw = json.loads(SOURCE.read_text())
    questions = load_questions(SOURCE)
    excluded_basketball = {
        row["row_index"] for row in json.loads(PRIOR_TABLE.read_text())["results"]
    }
    by_db: dict[str, list[Any]] = defaultdict(list)
    for q in questions:
        if q.db_id == "professional_basketball" and q.row_index in excluded_basketball:
            continue
        by_db[q.db_id].append(q)
    selected = []
    for db_id in sorted(by_db):
        rows = by_db[db_id]
        targeted = [q for q in rows if hint_fragment(q.evidence)]
        if len(targeted) > PER_DB:
            raise SystemExit(f"Too many hint cases in {db_id} for the frozen quota")
        chosen = {q.row_index for q in targeted}
        remaining = sorted(
            (q for q in rows if q.row_index not in chosen),
            key=lambda q: hashlib.sha256(f"jev-live-v1:{q.row_index}".encode()).digest(),
        )
        selected.extend(targeted + remaining[: PER_DB - len(targeted)])
    selected.sort(key=lambda q: (q.db_id, q.row_index))
    if len(selected) != 4 * PER_DB:
        raise SystemExit("Pilot did not select 25 questions per development database")
    subset = [{**raw[q.row_index], "source_row_index": q.row_index} for q in selected]
    PILOT.write_text(json.dumps(subset, indent=2) + "\n")
    hint_rows = {
        index: fragment
        for index, q in enumerate(selected)
        if (fragment := hint_fragment(q.evidence)) is not None
    }
    manifest = {
        "source": str(SOURCE),
        "source_sha256_16": dataset_fingerprint(SOURCE),
        "pilot": str(PILOT),
        "pilot_sha256_16": dataset_fingerprint(PILOT),
        "selection": "25 per train_dev2 database; include every atomic formula/comparison hint; fill by sha256(jev-live-v1:source_row_index); exclude the 50 basketball table-shadow rows",
        "source_row_indices": [q.row_index for q in selected],
        "hint_fragments": hint_rows,
        "prior_table_sha256_16": dataset_fingerprint(PRIOR_TABLE),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "pilot_rows": len(selected),
                "hint_rows": len(hint_rows),
                "pilot_sha256_16": manifest["pilot_sha256_16"],
            }
        )
    )


def _prompt(mode: str, decision: dict[str, Any]) -> str | None:
    if mode == "table":
        chosen = decision["prioritized_tables"]
        if not chosen:
            return None
        names = ", ".join(f"`{table}`" for table in chosen)
        return (
            f"Schema navigation aid: prioritize {names} as starting tables. "
            "This is advisory, not a table restriction. Use any other lookup or join "
            "tables needed from the full schema, and follow the original question."
        )
    role = decision["role"]
    descriptions = {
        "return": "a value or computation to return only if the question asks for it",
        "filter": "a condition to enforce when finding matching rows or groups",
        "rank": "a ranking criterion for finding the requested entity",
    }
    return (
        f"Evidence-use aid: the hint fragment {json.dumps(decision['fragment'])} "
        f"primarily defines {descriptions[role]}. This is advisory; preserve every "
        "constraint in the original question and do not add unrequested output columns."
    )


async def annotate(args: argparse.Namespace) -> None:
    manifest = json.loads(MANIFEST.read_text())
    if (
        dataset_fingerprint(SOURCE) != manifest["source_sha256_16"]
        or dataset_fingerprint(PILOT) != manifest["pilot_sha256_16"]
        or dataset_fingerprint(PRIOR_TABLE) != manifest["prior_table_sha256_16"]
    ):
        raise SystemExit("A frozen Jev pilot input changed")
    questions = load_questions(PILOT)
    expected = (
        list(range(len(questions)))
        if args.mode == "table"
        else [int(row) for row in manifest["hint_fragments"]]
    )
    db_paths = {
        db_id: db_path_for(db_id, db_dir=args.db_dir)
        for db_id in sorted({q.db_id for q in questions})
    }
    db_hashes = {db_id: database_fingerprint(path) for db_id, path in db_paths.items()}
    catalogs = {db_id: table_catalog(path) for db_id, path in db_paths.items()}
    prepared = []
    for row in expected:
        q = questions[row]
        if args.mode == "table":
            tables = shortlist(q, catalogs[q.db_id])
            state, specs = table_request(q, tables, db_paths[q.db_id], with_fk=True)
            extra = tables
        else:
            fragment = manifest["hint_fragments"][str(row)]
            state, specs = hint_request(q, fragment)
            extra = fragment
        if "gold_sql" in state or "official_ex" in state:
            raise SystemExit("Gold or evaluation labels entered Jev state")
        prepared.append((row, q, state, specs, extra))
    print(
        json.dumps(
            {
                "mode": args.mode,
                "paid": args.run,
                "prepared": len(prepared),
                "mean_state_chars": round(
                    sum(len(json.dumps(x[2])) for x in prepared) / len(prepared)
                ),
                "pilot_sha256_16": manifest["pilot_sha256_16"],
            }
        )
    )
    if not args.run:
        return
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if (
            prior.get("complete") is True
            and prior.get("pilot_sha256_16") == manifest["pilot_sha256_16"]
            and prior.get("mode") == args.mode
            and prior.get("database_sha256_16") == db_hashes
            and [r["row_index"] for r in prior["results"]] == expected
        ):
            print(json.dumps({"already_complete": True, "cost_usd": prior["cost_usd"]}))
            return
        raise SystemExit("Partial or mismatched Jev annotations exist; refusing duplicate calls")
    if args.env_file:
        load_dotenv(args.env_file)
    client = JevClient(
        JevConfig.from_env(),
        BudgetGuard(float(os.getenv("FIREWORKS_BUDGET_USD", "6")), args.ledger_path),
    )
    results: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    for row, q, state, specs, extra in prepared:
        try:
            answer = await client.decide(state, specs)
        except JevError as exc:
            results.append({"row_index": row, "error": str(exc)})
            break
        if args.mode == "table":
            assert isinstance(extra, list)
            probabilities = {
                table: float(answer.answers[f"table_{i}"]["noul"]) for i, table in enumerate(extra)
            }
            result = {
                "row_index": row,
                "db_id": q.db_id,
                "prioritized_tables": [t for t in extra if probabilities[t] >= 0.5],
                "table_probabilities": probabilities,
            }
        else:
            assert isinstance(extra, str)
            result = {
                "row_index": row,
                "db_id": q.db_id,
                "fragment": extra,
                "role": answer.answers["role"]["choice"],
                "confidence": answer.answers["role"]["confidence"],
            }
        result.update(
            model_version=answer.model_version,
            cost_usd=answer.cost_usd,
            latency_ms=answer.latency_ms,
        )
        results.append(result)
        if (text := _prompt(args.mode, result)) is not None:
            annotations.append({"row_index": row, "db_id": q.db_id, "text": text})
        args.output.write_text(
            json.dumps(
                {
                    "questions_sha256_16": manifest["pilot_sha256_16"],
                    "pilot_sha256_16": manifest["pilot_sha256_16"],
                    "database_sha256_16": db_hashes,
                    "mode": args.mode,
                    "complete": len(results) == len(expected),
                    "results": results,
                    "annotations": annotations,
                    "cost_usd": sum(r.get("cost_usd", 0.0) for r in results),
                },
                indent=2,
            )
            + "\n"
        )
    print(
        json.dumps(
            {
                "completed": len(results),
                "expected": len(expected),
                "annotations": len(annotations),
                "cost_usd": sum(r.get("cost_usd", 0.0) for r in results),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--mode", choices=("table", "hint"))
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--db-dir", type=Path, default=Path("data/bird/train/train_databases"))
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare_sample()
    elif args.mode and args.output:
        asyncio.run(annotate(args))
    else:
        parser.error("Use --prepare or --mode with --output")


if __name__ == "__main__":
    main()
