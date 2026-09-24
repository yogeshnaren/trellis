import json
from pathlib import Path

from benchmark.evaluate import evaluate_sql, evaluate_task_success
from benchmark.report import build_report
from benchmark.run_bench import arm_matrix, extract_baseline_sql
from src.costs import MODEL_DEEPSEEK, MODEL_GPT_OSS, MODEL_MINIMAX
from src.db import connect_readonly


def test_arm_matrix_limits_baseline_to_control() -> None:
    matrix = arm_matrix(
        [MODEL_GPT_OSS, MODEL_DEEPSEEK, MODEL_MINIMAX], ["agent", "baseline"]
    )
    assert matrix.count((MODEL_DEEPSEEK, "baseline")) == 1
    assert (MODEL_GPT_OSS, "baseline") not in matrix
    assert sum(arm == "agent" for _, arm in matrix) == 3


def test_baseline_extractor_handles_quoted_semicolon() -> None:
    assert extract_baseline_sql("```sql\nSELECT ';' AS value;\n```") == "SELECT ';' AS value"


def test_evaluation_aligns_columns_by_name_and_preserves_duplicates() -> None:
    conn = connect_readonly()
    try:
        aligned = evaluate_sql(
            "test",
            "SELECT FirstName, LastName FROM Customer WHERE Country='Brazil'",
            "SELECT LastName, FirstName FROM Customer WHERE Country='Brazil'",
            conn,
        )
        assert aligned.correct and aligned.sql_equivalent
        duplicate_mismatch = evaluate_sql(
            "test",
            "SELECT Name FROM Playlist",
            "SELECT DISTINCT Name FROM Playlist",
            conn,
        )
        assert not duplicate_mismatch.correct
    finally:
        conn.close()


def test_e2e_success_requires_agent_delivery() -> None:
    assert evaluate_task_success(
        error="Unknown column: c.genre_count",
        response_type="query",
        rows=None,
        sql_equivalent=True,
    ) is False
    assert evaluate_task_success(
        error=None,
        response_type="query",
        rows=[(1,)],
        sql_equivalent=True,
    )


def test_month_date_grain_contract_equates_formats() -> None:
    conn = connect_readonly()
    try:
        without = evaluate_sql(
            "live_006",
            "SELECT strftime('%m', InvoiceDate) as Month, SUM(Total) as MonthlyRevenue "
            "FROM Invoice WHERE strftime('%Y', InvoiceDate) = '2021' "
            "GROUP BY Month ORDER BY MonthlyRevenue DESC",
            "SELECT strftime('%Y-%m', InvoiceDate) as Month, SUM(Total) as MonthlyRevenue "
            "FROM Invoice WHERE strftime('%Y', InvoiceDate) = '2021' "
            "GROUP BY Month ORDER BY MonthlyRevenue DESC",
            conn,
        )
        assert not without.correct
        with_contract = evaluate_sql(
            "live_006",
            "SELECT strftime('%m', InvoiceDate) as Month, SUM(Total) as MonthlyRevenue "
            "FROM Invoice WHERE strftime('%Y', InvoiceDate) = '2021' "
            "GROUP BY Month ORDER BY MonthlyRevenue DESC",
            "SELECT strftime('%Y-%m', InvoiceDate) as Month, SUM(Total) as MonthlyRevenue "
            "FROM Invoice WHERE strftime('%Y', InvoiceDate) = '2021' "
            "GROUP BY Month ORDER BY MonthlyRevenue DESC",
            conn,
            contract={"date_grain": "month", "order_policy": "strict", "tie_policy": "bag_within_ties"},
        )
        assert with_contract.correct and with_contract.sql_equivalent
    finally:
        conn.close()


def test_required_columns_contract_fails_closed() -> None:
    conn = connect_readonly()
    try:
        missing = evaluate_sql(
            "diag",
            "SELECT Name FROM Artist LIMIT 1",
            "SELECT Name FROM Artist LIMIT 1",
            conn,
            contract={"required_columns": ["Name", "ArtistCount"]},
        )
        assert not missing.correct
        assert "Missing required columns" in (missing.reason or "")
    finally:
        conn.close()


def test_report_contains_sql_eq_e2e_and_only_p50_p90() -> None:
    record = {
        "model": MODEL_GPT_OSS,
        "arm": "agent",
        "concurrency": 1,
        "question_id": "q_001",
        "t_total_ms": 1000,
        "repaired": False,
        "llm_calls": [{"cost_usd": 0.001, "output_tokens": 10}],
        "evaluation": {"correct": True, "sql_equivalent": True, "e2e_success": True},
    }
    report = build_report([record])
    assert "SQL Eq" in report and "E2E Acc" in report
    assert "P50" in report and "P90" in report
    assert "P95" not in report
    assert "not** a head-to-head" in report


def test_official_ex_uses_bird_set_semantics() -> None:
    from benchmark.evaluate import official_ex

    conn = connect_readonly()
    try:
        gold = "SELECT Name FROM Genre ORDER BY Name"
        # Order and duplicate rows are ignored, as in BIRD's evaluation_ex.py.
        assert official_ex(conn, gold, "SELECT Name FROM Genre ORDER BY Name DESC")
        assert official_ex(
            conn, gold, "SELECT g.Name FROM Genre g JOIN Track t ON t.GenreId = g.GenreId"
        )
        # Extra columns, unrounded-vs-rounded values, errors, and missing SQL all score 0.
        assert not official_ex(conn, gold, "SELECT Name, GenreId FROM Genre")
        assert not official_ex(
            conn, "SELECT AVG(Milliseconds) FROM Track", "SELECT ROUND(AVG(Milliseconds), 2) FROM Track"
        )
        assert not official_ex(conn, gold, "SELECT Nope FROM Genre")
        assert not official_ex(conn, gold, None)
    finally:
        conn.close()


def test_output_contract_rewrites() -> None:
    from benchmark.analyze import (
        count_without_distinct,
        matches_after_dropping_columns,
        split_concat,
        strip_round,
    )

    assert matches_after_dropping_columns([("a",), ("b",)], [(1, "a"), (2, "b")])
    assert not matches_after_dropping_columns([("a",)], [(1, "z")])
    assert strip_round("SELECT ROUND(AVG(x), 2) AS a FROM t") == "SELECT AVG(x) AS a FROM t"
    assert strip_round("SELECT x FROM t") is None
    assert split_concat("SELECT first || ' ' || last AS name FROM t") == (
        "SELECT first, last FROM t"
    )
    assert split_concat("SELECT first FROM t") is None
    assert count_without_distinct("SELECT COUNT(DISTINCT id) FROM t") == "SELECT COUNT(id) FROM t"
    assert count_without_distinct("SELECT COUNT(id) FROM t") is None


def test_bucket_and_delivered_sql() -> None:
    from benchmark.analyze import bucket, delivered_sql

    ok = {"response_type": "query", "sql": "SELECT 1", "error": None, "error_category": None}
    assert bucket(ok, [(1,)], [(1,)]) == "correct"
    assert bucket(ok, [(1,)], []) == "empty-result"
    assert bucket(ok, [(1,)], [(1, 2)]) == "extra-columns"
    assert bucket(ok, [(1, 2)], [(1,)]) == "missing-columns"
    assert bucket(ok, [(1,), (2,)], [(1,)]) == "row-count-differs"
    assert bucket(ok, [(1,)], [(2,)]) == "values-differ"
    rejected = {**ok, "error": "Unknown column: x", "error_category": "safety-rejected"}
    assert delivered_sql(rejected) is None
    assert bucket(rejected, [(1,)], None) == "pipeline-safety-rejected"
    refused = {**ok, "response_type": "unsupported", "sql": None}
    assert bucket(refused, [(1,)], None) == "answered-unsupported"


def test_mcnemar_exact_p() -> None:
    from benchmark.analyze import mcnemar_exact_p

    assert mcnemar_exact_p(0, 0) == 1.0
    assert mcnemar_exact_p(5, 5) == 1.0
    assert mcnemar_exact_p(0, 10) < 0.01
    assert 0.05 < mcnemar_exact_p(3, 8) < 0.3


def test_load_questions_keeps_duplicate_rows_and_defaults(tmp_path: Path) -> None:
    from benchmark.bird import load_questions

    path = tmp_path / "q.json"
    path.write_text(
        json.dumps(
            [
                {"question_id": 7, "db_id": "d", "question": "a", "SQL": "SELECT 1",
                 "difficulty": "simple"},
                {"question_id": 7, "db_id": "d", "question": "a", "SQL": "SELECT 1",
                 "difficulty": "simple"},
                {"db_id": "d", "question": "train-style", "SQL": "SELECT 2"},
            ]
        )
    )
    rows = load_questions(path)
    assert [q.row_index for q in rows] == [0, 1, 2]
    assert rows[2].question_id == 2 and rows[2].difficulty == "unknown"


def test_load_run_maps_legacy_duplicate_ids_to_distinct_rows(tmp_path: Path) -> None:
    from benchmark.analyze import load_run
    from benchmark.bird import BirdQuestion

    questions = [
        BirdQuestion(137, "d", "q", "", "SELECT 1", "moderate", row_index=0),
        BirdQuestion(5, "d", "q", "", "SELECT 1", "simple", row_index=1),
        BirdQuestion(137, "d", "q", "", "SELECT 1", "moderate", row_index=2),
    ]
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text(
        "\n".join(json.dumps({"question_id": q, "model": "m", "sql": s}) for q, s in
                  [(137, "a"), (5, "b"), (137, "c")])
    )
    assert {row: rec["sql"] for row, rec in load_run(legacy, questions).items()} == {
        0: "a", 1: "b", 2: "c"
    }
    current = tmp_path / "current.jsonl"
    current.write_text(json.dumps({"question_id": 137, "row_index": 2, "model": "m"}))
    assert set(load_run(current, questions)) == {2}


def test_score_bird_executes_once_for_all_metrics() -> None:
    from benchmark.evaluate import score_bird

    conn = connect_readonly()
    try:
        gold = "SELECT Name FROM Genre"
        same = score_bird(conn, "q", gold, "SELECT DISTINCT Name FROM Genre", delivered=True)
        assert same.official_ex and same.row_count == 25
        # Local metric keeps its multiset semantics; official uses sets.
        assert not score_bird(
            conn, "q", "SELECT Name FROM Track LIMIT 5", "SELECT Name FROM Track LIMIT 5",
            delivered=False,
        ).official_ex
        reordered = score_bird(conn, "q", gold, "SELECT Name FROM Genre ORDER BY 1 DESC",
                               delivered=True)
        assert reordered.signature == same.signature
        other = score_bird(conn, "q", gold, "SELECT Name FROM MediaType", delivered=True)
        assert other.signature != same.signature and not other.official_ex
    finally:
        conn.close()


def test_select_questions_stratifies_targets_and_groups_by_database(tmp_path: Path) -> None:
    import argparse

    from benchmark.run_bird import select_questions

    rows = [
        {"question_id": i, "db_id": db, "question": "q", "SQL": "SELECT 1", "difficulty": "simple"}
        for i, db in enumerate(["b"] * 10 + ["a"] * 3)
    ]
    path = tmp_path / "q.json"
    path.write_text(json.dumps(rows))
    args = argparse.Namespace(
        questions=path, difficulty=None, db=None, limit=None, per_db=2, ids=[9], seed=1
    )
    chosen = select_questions(args)
    per_db: dict[str, int] = {}
    for q in chosen:
        per_db[q.db_id] = per_db.get(q.db_id, 0) + 1
    assert per_db["a"] == 2 and 9 in {q.question_id for q in chosen}
    assert per_db["b"] in (2, 3)  # 2 sampled + the targeted id unless already sampled
    assert [q.db_id for q in chosen] == sorted(q.db_id for q in chosen)


def test_sql_complexity_bands() -> None:
    from benchmark.analyze import sql_complexity

    assert sql_complexity("SELECT name FROM t WHERE id = 1") == "low"
    assert sql_complexity("SELECT a.x, COUNT(*) FROM a JOIN b ON a.id = b.id GROUP BY a.x") == (
        "medium"
    )
    assert sql_complexity(
        "SELECT x FROM a JOIN b ON a.i = b.i JOIN c ON b.j = c.j "
        "WHERE a.k IN (SELECT k FROM d) GROUP BY x"
    ) == "high"
    assert sql_complexity("NOT SQL AT ALL (((") == "unparsed"


def _write_run(path: Path, rows: list[tuple[int, int, bool]], meta: dict[str, object]) -> None:
    path.write_text(
        "\n".join(
            json.dumps({"row_index": row, "question_id": row, "repeat": rep, "model": "m",
                        "official_ex": ok})
            for row, rep, ok in rows
        )
    )
    path.with_name(path.name.replace("bird_raw_", "bird_meta_")).with_suffix(".json").write_text(
        json.dumps(meta)
    )


def test_flips_refuses_undeclared_differences_and_bootstraps_by_question(tmp_path: Path) -> None:
    import pytest

    from benchmark.analyze import flips_report
    from benchmark.bird import BirdQuestion

    questions = [
        BirdQuestion(i, "big" if i < 6 else "small", "q", "", "SELECT 1", "unknown", row_index=i)
        for i in range(8)
    ]
    base = {"dataset_sha256_16": "d", "database_sha256_16": {"big": "1", "small": "2"},
            "effective_prompt_sha256_16": "p0", "config_sha256_16": "c",
            "git_commit": "g", "code_state_sha256_16": "s0",
            "expected_rows": list(range(8)), "expected_repeats": 2, "complete": True}
    old, new = tmp_path / "bird_raw_old.jsonl", tmp_path / "bird_raw_new.jsonl"
    # Two repeats each. The large database improves and the small one collapses: the
    # row-weighted gain is positive while the database macro is negative (review 4, #1).
    _write_run(old, [(r, rep, r in (0, 6, 7)) for r in range(8) for rep in (0, 1)], base)
    changed = {**base, "effective_prompt_sha256_16": "p1", "code_state_sha256_16": "s1"}
    _write_run(new, [(r, rep, r in (0, 1, 2, 3)) for r in range(8) for rep in (0, 1)], changed)
    with pytest.raises(SystemExit, match=r"undeclared ways: code\."):
        flips_report(old, new, questions, tmp_path, allow={"prompt"})
    report = flips_report(old, new, questions, tmp_path, allow={"prompt", "code"}, iterations=500)
    assert "| Row-weighted | +12.50 |" in report  # (+3 fixes -2 regressions) / 8 rows
    assert "| Database macro | -25.00 |" in report  # (+50 + -100) / 2 databases
    assert "REGRESSION: `small` question 6" in report


def test_database_fingerprint_detects_content_changes(tmp_path: Path) -> None:
    import os

    from benchmark.bird import database_fingerprint

    db, cache = tmp_path / "x.sqlite", tmp_path / "cache.json"
    db.write_bytes(b"one")
    first = database_fingerprint(db, cache)
    assert database_fingerprint(db, cache) == first and cache.exists()
    db.write_bytes(b"two")
    os.utime(db, ns=(1, 1))  # force a new stamp even on coarse-mtime filesystems
    assert database_fingerprint(db, cache) != first


def test_load_runs_keeps_repeats_and_maps_legacy_duplicates_per_repeat(tmp_path: Path) -> None:
    from benchmark.analyze import load_runs
    from benchmark.bird import BirdQuestion

    questions = [
        BirdQuestion(137, "d", "q", "", "SELECT 1", "moderate", row_index=0),
        BirdQuestion(137, "d", "q", "", "SELECT 1", "moderate", row_index=1),
    ]
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text(
        "\n".join(
            json.dumps({"question_id": 137, "repeat": rep, "model": "m", "sql": f"{rep}{k}"})
            for rep in (0, 1)
            for k in "ab"
        )
    )
    runs = load_runs(legacy, questions)
    assert [r["sql"] for r in runs[0]] == ["0a", "1a"]
    assert [r["sql"] for r in runs[1]] == ["0b", "1b"]


def _two_row_runs(tmp_path: Path, new_rows: list[tuple[int, int, bool]], **new_meta: object):
    from benchmark.bird import BirdQuestion

    questions = [BirdQuestion(i, "db", "q", "", "SELECT 1", "unknown", row_index=i) for i in (0, 1)]
    meta = {"dataset_sha256_16": "d", "database_sha256_16": {"db": "1"},
            "effective_prompt_sha256_16": "p", "config_sha256_16": "c", "git_commit": "g",
            "code_state_sha256_16": "s", "expected_rows": [0, 1], "expected_repeats": 2,
            "complete": True}
    old, new = tmp_path / "bird_raw_old.jsonl", tmp_path / "bird_raw_new.jsonl"
    _write_run(old, [(0, 0, False), (0, 1, False), (1, 0, True), (1, 1, True)], meta)
    _write_run(new, new_rows, {**meta, **new_meta})
    return old, new, questions


def test_full_comparison_refuses_partial_runs_but_pilot_allows_them(tmp_path: Path) -> None:
    import pytest

    from benchmark.analyze import flips_report

    # The review's example: a budget stop left the variant with one result.
    old, new, questions = _two_row_runs(tmp_path, [(0, 0, True)], complete=False)
    with pytest.raises(SystemExit, match="incomplete.*lacks 1 expected rows"):
        flips_report(old, new, questions, tmp_path)
    pilot = flips_report(old, new, questions, tmp_path, pilot=True, iterations=100)
    assert "PILOT comparison" in pilot and "NOT acceptance evidence" in pilot


def test_full_comparison_requires_two_repeats_and_same_expected_rows(tmp_path: Path) -> None:
    import pytest

    from benchmark.analyze import flips_report

    one_repeat = [(0, 0, True), (1, 0, True)]
    old, new, questions = _two_row_runs(tmp_path, one_repeat)
    with pytest.raises(SystemExit, match="without exactly 2 repeats"):
        flips_report(old, new, questions, tmp_path)
    full = [(r, k, True) for r in (0, 1) for k in (0, 1)]
    old, new, questions = _two_row_runs(tmp_path, full, expected_rows=[0, 1, 2])
    with pytest.raises(SystemExit, match="expected different question rows"):
        flips_report(old, new, questions, tmp_path)
    old, new, questions = _two_row_runs(tmp_path, full)
    report = flips_report(old, new, questions, tmp_path, iterations=100)
    assert "full comparison, coverage verified" in report and "| Row-weighted | +50.00 |" in report
