"""Offline training-pool leakage and sampling checks; no downloaded BIRD data needed."""

import json
import sqlite3
from pathlib import Path

import pytest

from benchmark.training_quality import allocate_sample, build, sample_rows


def test_filtered_pool_excludes_all_evaluation_databases(tmp_path: Path) -> None:
    db_dir = tmp_path / "databases"
    candidate_db = db_dir / "candidate"
    candidate_db.mkdir(parents=True)
    with sqlite3.connect(candidate_db / "candidate.sqlite") as conn:
        conn.execute("CREATE TABLE things (id INTEGER)")
    train = [
        {
            "db_id": "candidate",
            "question": "How many things?",
            "evidence": "",
            "SQL": "SELECT COUNT(*) FROM things",
        },
        {"db_id": "sealed", "question": "How many things?", "evidence": "", "SQL": "SELECT 1"},
    ]
    original = tmp_path / "original.json"
    original.write_text(json.dumps(train))
    filtered = tmp_path / "filtered.jsonl"
    filtered.write_text("".join(json.dumps(item) + "\n" for item in train))
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps([{"db_id": "sealed", "question": "Test case", "SQL": "SELECT 1"}])
    )
    pool, manifest, sample, report = (
        tmp_path / "pool.jsonl",
        tmp_path / "manifest.json",
        tmp_path / "sample.jsonl",
        tmp_path / "report.md",
    )
    result = build(
        filtered,
        original,
        {"lockbox": evaluation},
        db_dir,
        pool,
        manifest,
        sample,
        report,
        sample_size=1,
    )
    assert result["candidate_rows"] == 1
    assert result["excluded_filtered_rows"] == 1
    assert result["mechanical_status"] == {"explain_ok": 1}
    saved = [json.loads(line) for line in pool.read_text().splitlines()]
    assert [item["db_id"] for item in saved] == ["candidate"]
    assert json.loads(sample.read_text().splitlines()[0])["review_label"] == "pending"


def test_pool_rejects_cross_database_question_overlap(tmp_path: Path) -> None:
    item = {"db_id": "candidate", "question": "Secret question", "evidence": "", "SQL": "SELECT 1"}
    original = tmp_path / "original.json"
    original.write_text(json.dumps([item]))
    filtered = tmp_path / "filtered.jsonl"
    filtered.write_text(json.dumps(item) + "\n")
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps([{"db_id": "sealed", "question": "secret   QUESTION", "SQL": "SELECT 2"}])
    )
    with pytest.raises(ValueError, match="duplicate evaluation text"):
        build(
            filtered,
            original,
            {"gate": evaluation},
            tmp_path / "db",
            tmp_path / "pool",
            tmp_path / "manifest",
            tmp_path / "sample",
            tmp_path / "report",
            sample_size=1,
        )


def test_sample_covers_databases_and_weights_population() -> None:
    by_db = {
        "small": [{"filtered_row_index": 0, "db_id": "small", "local_database": True}],
        "large": [
            {"filtered_row_index": i, "db_id": "large", "local_database": True}
            for i in range(1, 10)
        ],
    }
    allocation = allocate_sample(by_db, 4)
    assert sum(allocation.values()) == 4
    assert all(value >= 1 for value in allocation.values())
    sample = sample_rows(by_db["small"] + by_db["large"], 4)
    assert len(sample) == 4
    assert {item["db_id"] for item in sample} == {"small", "large"}
    assert sum(item["row_weight"] for item in sample) == pytest.approx(10)
