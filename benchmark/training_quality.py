"""Prepare a leakage-checked BIRD training candidate pool and free quality-review sample.

This does not declare examples semantically correct. SQLite EXPLAIN validates names and SQL
compilation when the database is local; a human must review the question, evidence and SQL.
Evaluation-set database IDs and normalized question text are used only for leakage checks;
no evaluation gold SQL, prediction, result, or failure is used to select or repair labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlglot import parse_one
from sqlglot.errors import SqlglotError

from benchmark.analyze import sql_complexity
from benchmark.bird import database_fingerprint, db_path_for

BIRD = Path("data/bird")
FILTERED = BIRD / "train_filtered/train-00000-of-00001.jsonl"
ORIGINAL = BIRD / "train/train.json"
DB_DIR = BIRD / "train/train_databases"
EVALUATION = {
    "train_dev": BIRD / "splits/train_dev.json",
    "train_dev2": BIRD / "splits/train_dev2.json",
    "train_lockbox": BIRD / "splits/train_lockbox.json",
    "mini_dev": BIRD / "mini_dev_sqlite.json",
    "dev_untouched": BIRD / "splits/dev_untouched.json",
    "cleaned_dev": BIRD / "dev_cleaned/dev_20251106.json",
}
POOL = BIRD / "training_quality/candidate_pool.jsonl"  # gitignored with BIRD data
MANIFEST = Path("benchmark/results/training_quality_manifest.json")
SAMPLE = Path("benchmark/results/training_quality_review_sample.jsonl")
REPORT = Path("benchmark/results/training_quality_audit.md")
SAMPLE_SEED = "training-quality-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    result = json.loads(path.read_text())
    if not isinstance(result, list):
        raise TypeError(f"Expected a JSON array in {path}")
    return result


def identity(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(item.get(key) or "") for key in ("db_id", "question", "evidence", "SQL"))  # type: ignore[return-value]


def normalize_question(question: str) -> str:
    return " ".join(question.casefold().split())


def allocate_sample(by_db: dict[str, list[dict[str, Any]]], count: int) -> dict[str, int]:
    """One per database, then proportional extras; within-db draws are hash ordered."""
    if count < len(by_db) or count > sum(map(len, by_db.values())):
        raise ValueError("Review sample must cover every locally available database")
    remaining = count - len(by_db)
    extras_population = sum(len(group) - 1 for group in by_db.values())
    targets = {
        db: remaining * (len(group) - 1) / extras_population if extras_population else 0.0
        for db, group in by_db.items()
    }
    assigned = {db: 1 + int(targets[db]) for db in by_db}
    leftovers = count - sum(assigned.values())
    for db in sorted(by_db, key=lambda name: (-(targets[name] % 1), name))[:leftovers]:
        assigned[db] += 1
    return assigned


def sample_rows(pool: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    by_db: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in pool:
        if item["local_database"]:
            by_db[item["db_id"]].append(item)
    allocation = allocate_sample(by_db, count)
    selected: list[dict[str, Any]] = []
    for db in sorted(by_db):
        group = sorted(
            by_db[db],
            key=lambda item: hashlib.sha256(
                f"{SAMPLE_SEED}:{item['filtered_row_index']}".encode()
            ).digest(),
        )
        for item in group[: allocation[db]]:
            selected.append(
                {
                    **item,
                    "review_label": "pending",
                    "review_reason": "",
                    "population_in_database": len(group),
                    "sampled_in_database": allocation[db],
                    "row_weight": len(group) / allocation[db],
                }
            )
    return sorted(selected, key=lambda item: (item["db_id"], item["filtered_row_index"]))


def build(
    filtered_path: Path = FILTERED,
    original_path: Path = ORIGINAL,
    evaluation_paths: dict[str, Path] | None = None,
    db_dir: Path = DB_DIR,
    pool_path: Path = POOL,
    manifest_path: Path = MANIFEST,
    sample_path: Path = SAMPLE,
    report_path: Path = REPORT,
    sample_size: int = 100,
) -> dict[str, Any]:
    evaluations = evaluation_paths if evaluation_paths is not None else EVALUATION
    originals = rows(original_path)
    filtered = rows(filtered_path)
    original_indices: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for index, item in enumerate(originals):
        original_indices[identity(item)].append(index)
    excluded_by: dict[str, list[str]] = defaultdict(list)
    evaluation_questions: set[str] = set()
    for name, path in evaluations.items():
        for item in rows(path):
            if name not in excluded_by[item["db_id"]]:
                excluded_by[item["db_id"]].append(name)
            evaluation_questions.add(normalize_question(item["question"]))

    conns: dict[str, sqlite3.Connection] = {}
    candidate_pool: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    excluded_db_rows = 0
    mechanical: Counter[str] = Counter()
    ambiguous_source_rows = 0
    exact_question_overlap = 0
    try:
        for index, item in enumerate(filtered):
            original_matches = original_indices.get(identity(item), [])
            if not original_matches:
                raise ValueError(f"Filtered row {index} has no exact original-train match")
            ambiguous_source_rows += len(original_matches) > 1
            db_id = str(item["db_id"])
            if db_id in excluded_by:
                excluded_db_rows += 1
                for name in excluded_by[db_id]:
                    excluded_counts[name] += 1
                continue
            exact_question_overlap += normalize_question(item["question"]) in evaluation_questions
            db_path = db_path_for(db_id, db_dir=db_dir)
            local = db_path.exists()
            parse_error = None
            explain_error = None
            try:
                parse_one(item["SQL"], read="sqlite")
            except SqlglotError as exc:
                parse_error = str(exc)[:180]
            if local:
                if db_id not in conns:
                    conns[db_id] = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
                try:
                    conns[db_id].execute("EXPLAIN QUERY PLAN " + item["SQL"]).fetchall()
                except sqlite3.Error as exc:
                    explain_error = str(exc)[:180]
            status = (
                "database_missing"
                if not local
                else "parse_error"
                if parse_error
                else "explain_error"
                if explain_error
                else "explain_ok"
            )
            mechanical[status] += 1
            candidate_pool.append(
                {
                    "filtered_row_index": index,
                    "original_row_indices": original_matches,
                    "db_id": db_id,
                    "question": item["question"],
                    "evidence": item.get("evidence") or "",
                    "SQL": item["SQL"],
                    "complexity": sql_complexity(item["SQL"]),
                    "local_database": local,
                    "mechanical_status": status,
                    "parse_error": parse_error,
                    "explain_error": explain_error,
                }
            )
    finally:
        for conn in conns.values():
            conn.close()

    if exact_question_overlap:
        raise ValueError(f"{exact_question_overlap} training questions duplicate evaluation text")
    sample = sample_rows(candidate_pool, sample_size)
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    for path, data in ((pool_path, candidate_pool), (sample_path, sample)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in data))
    manifest = {
        "status": "candidate-only: filtered by BIRD, not semantically verified for SFT",
        "source_sha256": {"filtered": sha256(filtered_path), "original": sha256(original_path)},
        "evaluation_sha256": {name: sha256(path) for name, path in evaluations.items()},
        "excluded_database_ids": sorted(excluded_by),
        "excluded_filtered_rows": excluded_db_rows,
        "exclusion_counts_by_split_overlap": dict(excluded_counts),
        "candidate_rows": len(candidate_pool),
        "local_database_rows": sum(item["local_database"] for item in candidate_pool),
        "missing_database_rows": sum(not item["local_database"] for item in candidate_pool),
        "candidate_databases": len({item["db_id"] for item in candidate_pool}),
        "local_databases": len(conns),
        "local_database_sha256_16": {
            db_id: database_fingerprint(db_path_for(db_id, db_dir=db_dir))
            for db_id in sorted(conns)
        },
        "mechanical_status": dict(mechanical),
        "ambiguous_original_row_mapping": ambiguous_source_rows,
        "exact_cross_database_question_overlap": exact_question_overlap,
        "complexity": dict(Counter(item["complexity"] for item in candidate_pool)),
        "sample_seed": SAMPLE_SEED,
        "sample_rows": len(sample),
        "sample_databases": len({item["db_id"] for item in sample}),
        "sample_complexity": dict(Counter(item["complexity"] for item in sample)),
        "pool_sha256": sha256(pool_path),
        "sample_sha256": sha256(sample_path),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    report_path.write_text(
        "# Filtered training-pool quality preflight\n\n"
        f"- BIRD filtered source: {len(filtered):,} rows; excluded evaluation-database rows: "
        f"{excluded_db_rows:,}; candidate pool: **{len(candidate_pool):,}** across "
        f"{manifest['candidate_databases']} databases.\n"
        f"- Locally checkable: **{manifest['local_database_rows']:,}** rows / "
        f"{manifest['local_databases']} databases. Database unavailable: "
        f"**{manifest['missing_database_rows']:,}** rows.\n"
        f"- Mechanical SQL checks: `{dict(mechanical)}`. An EXPLAIN success verifies "
        "compilation against the local schema, **not** that the SQL answers the question.\n"
        f"- Exact question-text overlap with evaluation sets after database exclusion: "
        f"{exact_question_overlap}. Filtered rows with multiple identical original-train "
        f"matches: {ambiguous_source_rows} (all original indices retained).\n"
        f"- Frozen semantic-review sample: {len(sample)} rows, one or more from every "
        f"local database ({manifest['sample_databases']}), deterministic within-database "
        "hash selection. `row_weight` permits database-stratified row-level estimates "
        "after labels are assigned. This coverage-oriented sample must not be treated "
        "as having a measured semantic error rate while `review_label` is pending.\n\n"
        "The generated candidate pool is gitignored under `data/bird/training_quality/`; "
        "the checked manifest and 100-row review sample are in `benchmark/results/`. "
        "**Do not train on this pool yet.** Inspect question, evidence, SQL and relevant "
        "database contents, then label each sample `sound`, `defect`, or `uncertain`. "
        "The predeclared training gate is a weighted defect rate no greater than 15% "
        "among reviewed local-database rows; uncertain cases are reported separately. "
        "The missing-database tier requires another download before execution checks.\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample-size", type=int, default=100)
    args = parser.parse_args()
    result = build(sample_size=args.sample_size)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "candidate_rows",
                    "local_database_rows",
                    "missing_database_rows",
                    "mechanical_status",
                    "sample_rows",
                    "sample_databases",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
