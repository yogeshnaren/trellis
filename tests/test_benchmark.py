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
