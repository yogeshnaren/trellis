"""Offline measurement for plan rank 1a: profile build cost, text-format flags, and value
retrieval recall.

Gold SQL is used **only here, offline**, to measure whether the value index would have
retrieved the literals the gold query filters on; it never reaches the inference path.
The key number is recall on literals that are *not* already written in the question or
evidence, because those are the ones the model can't simply copy.

    python -m benchmark.grounding --questions data/bird/splits/train_dev.json \\
        --db-dir data/bird/train/train_databases
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from pathlib import Path

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from benchmark.bird import BirdQuestion, db_path_for, load_questions
from src.db_profile import DEFAULT_CACHE_DIR, DatabaseProfile, build_profile, retrieve_values

K_VALUES = (5, 10, 20)


def gold_literals(sql: str) -> list[tuple[str, str]]:
    """(column, value) pairs where the gold SQL compares a column with a string literal
    (=, !=, LIKE, IN). LIKE wildcards are stripped."""
    try:
        tree = parse_one(sql, read="sqlite")
    except SqlglotError:
        return []
    pairs: list[tuple[str, str]] = []
    for node in tree.find_all(exp.EQ, exp.NEQ, exp.Like, exp.In):
        column = node.find(exp.Column)
        if column is None:
            continue
        literals = (
            node.expressions if isinstance(node, exp.In) else [node.args.get("expression")]
        )
        for literal in literals:
            if isinstance(literal, exp.Literal) and literal.is_string:
                value = literal.this.strip("%")
                if value:
                    pairs.append((column.name, value))
    return pairs


def literal_recall(
    questions: list[BirdQuestion], profiles: dict[str, DatabaseProfile]
) -> dict[str, float | int]:
    hits: dict[int, int] = defaultdict(int)
    hits_unseen: dict[int, int] = defaultdict(int)
    total = unseen = 0
    for question in questions:
        text = f"{question.question} {question.evidence}"
        retrieved = retrieve_values(profiles[question.db_id], text, k=max(K_VALUES))
        for column, value in gold_literals(question.gold_sql):
            total += 1
            in_text = value.casefold() in text.casefold()
            unseen += not in_text
            for k in K_VALUES:
                found = any(
                    col.casefold() == column.casefold() and val.casefold() == value.casefold()
                    for _, col, val in retrieved[:k]
                )
                hits[k] += found
                hits_unseen[k] += found and not in_text
    result: dict[str, float | int] = {"literals": total, "not_in_question_text": unseen}
    for k in K_VALUES:
        result[f"recall@{k}"] = round(hits[k] / total, 3) if total else 0.0
        result[f"recall@{k}_not_in_text"] = round(hits_unseen[k] / unseen, 3) if unseen else 0.0
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    questions = load_questions(args.questions)
    profiles = {
        db_id: build_profile(db_path_for(db_id, db_dir=args.db_dir), args.cache_dir,
                             refresh=args.refresh)
        for db_id in sorted({q.db_id for q in questions})
    }
    print(f"# Grounding measurement: `{args.questions.name}`\n")
    print("| Database | Build s | Columns | Text-formatted | FK joins (1:1 / 1:N / N:M) | "
          "Indexed values |")
    print("|---|---:|---:|---|---|---:|")
    for db_id, profile in profiles.items():
        formatted = ", ".join(
            f"{c.table}.{c.column}={c.text_format}" for c in profile.text_formatted()
        ) or "none"
        kinds = [j.cardinality for j in profile.joins]
        print(
            f"| `{db_id}` | {profile.build_seconds:.2f} | {len(profile.columns)} | "
            f"{formatted} | {len(kinds)} ({kinds.count('1:1')} / {kinds.count('1:N')} / "
            f"{kinds.count('N:M')}) | {profile.indexed_values:,} |"
        )
    builds = [p.build_seconds for p in profiles.values()]
    print(f"\nBuild time: median {statistics.median(builds):.2f}s, max {max(builds):.2f}s "
          "(first build; later runs load the cache).\n")
    recall = literal_recall(questions, profiles)
    print("## Value retrieval (gold string literals; offline measurement only)\n")
    for key, value in recall.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
