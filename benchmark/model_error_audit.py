"""Summarize labeled train-dev failures and freeze new cases for human review.

Uses development questions and stored predictions only. It never opens Mini-Dev,
cleaned dev or lockbox results, and it makes no model calls.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark.analyze import load_runs
from benchmark.bird import dataset_fingerprint, load_questions

QUESTIONS = Path("data/bird/splits/train_dev.json")
RUN = Path("benchmark/results/bird_raw_20260926T212754Z.jsonl")
PRIOR = Path("docs/postmortem_v2/data/train_dev_failure_audit.csv")
SAMPLE = Path("benchmark/results/model_error_review_sample.jsonl")
REPORT = Path("benchmark/results/model_error_audit.md")
PER_DB = 6
SEED = "model-error-audit-v1"


def build(
    questions_path: Path = QUESTIONS,
    run_path: Path = RUN,
    prior_path: Path = PRIOR,
    sample_path: Path = SAMPLE,
    report_path: Path = REPORT,
    per_db: int = PER_DB,
) -> dict[str, Any]:
    questions = load_questions(questions_path)
    meta_path = run_path.with_name(run_path.name.replace("bird_raw_", "bird_meta_")).with_suffix(
        ".json"
    )
    meta = json.loads(meta_path.read_text())
    if (
        meta.get("dataset_sha256_16") != dataset_fingerprint(questions_path)
        or meta.get("expected_repeats") != 2
        or meta.get("complete") is not True
    ):
        raise ValueError("Stored development run is incomplete or mismatches the question set")
    runs = load_runs(run_path, questions)
    labeled = list(csv.DictReader(prior_path.open()))
    labels = {int(row["row_index"]): row for row in labeled}
    if len(labels) != len(labeled):
        raise ValueError("Prior human audit has duplicate row indices")
    stable_wrong: dict[str, list[int]] = defaultdict(list)
    stable_correct = mixed = 0
    for q in questions:
        records = runs.get(q.row_index, [])
        if len(records) != 2:
            raise ValueError(f"Expected two baseline repeats at train-dev row {q.row_index}")
        scores = [bool(r.get("official_ex")) for r in records]
        if not any(scores):
            stable_wrong[q.db_id].append(q.row_index)
        elif all(scores):
            stable_correct += 1
        else:
            mixed += 1
    eligible_by_db = {
        db: [row for row in stable_wrong[db] if row not in labels] for db in sorted(stable_wrong)
    }
    chosen_rows = {
        row
        for eligible in eligible_by_db.values()
        for row in sorted(eligible, key=lambda i: hashlib.sha256(f"{SEED}:{i}".encode()).digest())[
            :per_db
        ]
    }
    target = min(per_db * len(stable_wrong), sum(map(len, eligible_by_db.values())))
    overflow = sorted(
        (row for eligible in eligible_by_db.values() for row in eligible if row not in chosen_rows),
        key=lambda i: hashlib.sha256(f"{SEED}:{i}".encode()).digest(),
    )
    chosen_rows.update(overflow[: target - len(chosen_rows)])
    selected = []
    for row in sorted(chosen_rows):
        q = questions[row]
        records = runs[row]
        selected.append(
            {
                "row_index": row,
                "db_id": q.db_id,
                "question_id": q.question_id,
                "question": q.question,
                "evidence": q.evidence,
                "gold_sql": q.gold_sql,
                "candidate_sql_repeats": [r.get("sql") for r in records],
                "candidate_errors": [r.get("error") for r in records],
                "candidate_result_row_counts": [r.get("result_row_count") for r in records],
                "review_label": "pending",
                "review_reason": "",
            }
        )
    sample_path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in selected))
    tags = Counter(row["tag"] for row in labeled)
    current_labeled = Counter(
        row["tag"] for row in labeled if int(row["row_index"]) in stable_wrong[row["db_id"]]
    )
    result = {
        "questions_sha256_16": dataset_fingerprint(questions_path),
        "run": str(run_path),
        "rows": len(questions),
        "stable_wrong": sum(map(len, stable_wrong.values())),
        "stable_wrong_by_db": {db: len(v) for db, v in stable_wrong.items()},
        "stable_correct": stable_correct,
        "mixed": mixed,
        "prior_labeled_rows": len(labeled),
        "prior_tags": dict(tags),
        "prior_labels_still_stable_wrong": dict(current_labeled),
        "new_review_rows": len(selected),
        "sample_sha256_16": dataset_fingerprint(sample_path),
    }
    report_path.write_text(
        "# Development-set genuine-error audit\n\n"
        f"The current v4p1 `train_dev` two-repeat run has {result['stable_wrong']} "
        f"stable-wrong, {stable_correct} stable-correct and {mixed} mixed rows "
        f"across {len(questions)} questions. Stable wrong **does not imply a genuine "
        "model error**: the training gold is noisy. No evaluation gate was read.\n\n"
        f"The prior 46-case hand audit tagged {dict(tags)}. Of those, "
        f"{dict(current_labeled)} remain stable-wrong under v4p1. This was a "
        "sample of failures, not a representative sample of all questions; its "
        "defect fraction must not be applied to cleaned dev or test.\n\n"
        "The eight previously labeled genuine errors identify concrete mechanisms: "
        "unconstrained or incorrectly scoped joins, a dropped street-number constraint, "
        "the wrong location table, case-sensitive value mismatch, and arithmetic on "
        "text-encoded money or duration. These deserve narrowly tested fixes after the "
        "training-label screen. The 24 new, hash-selected stable-wrong rows (six per "
        "database, excluding prior labels) are saved as a review packet; they are "
        "unlabeled until question, SQL, and database results are inspected.\n"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
