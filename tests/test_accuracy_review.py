from benchmark.accuracy_review import Question, combos, summarize, tag_table
from benchmark.patterns import (
    gold_shape_tags,
    gold_sql_tags,
    outcome_tag,
    question_tags,
    signal_tags,
)
from benchmark.probe import probe


def test_gold_sql_tags_detects_structure():
    tags = gold_sql_tags(
        "SELECT T1.a, COUNT(DISTINCT T2.b) FROM t1 AS T1 JOIN t2 AS T2 ON T1.id = T2.id "
        "GROUP BY T1.a ORDER BY 2 DESC LIMIT 1"
    )
    assert "sql: joins 1" in tags
    assert {"sql: GROUP BY", "sql: ORDER BY + LIMIT", "sql: DISTINCT", "sql: aggregate"} <= set(tags)
    assert "sql: unparsed" not in gold_sql_tags("SELECT 1")


def test_question_tags_intent_and_evidence():
    tags = question_tags("How many players scored the highest goals in 2008?", "")
    assert {"intent: count", "intent: superlative", "intent: temporal", "evidence: none"} <= set(tags)
    tags = question_tags("What percentage of games were won?", "percentage = DIVIDE(COUNT(won), COUNT(*))")
    assert {"intent: ratio / percent / average", "evidence: formula"} <= set(tags)


def test_shape_and_outcome_tags():
    assert gold_shape_tags([]) == ["shape: answer key returns nothing"]
    assert gold_shape_tags(None) == ["shape: answer key fails or times out locally"]
    assert "shape: single value" in gold_shape_tags([(1,)])
    record = {"error": None, "response_type": "query", "result_row_count": 0, "columns": ["a"]}
    assert outcome_tag(record, [(1,)], False) == "outcome: we return nothing"
    record = {"error": None, "response_type": "query", "result_row_count": 1, "columns": ["a", "b"]}
    assert outcome_tag(record, [(1,)], False) == "outcome: extra columns"
    assert outcome_tag(record, [(1,)], True) == "outcome: correct"
    assert "signal: database facts in prompt" in signal_tags({"t_total_ms": 100}, True)


def _qs():
    return [
        Question(i, "db1" if i % 2 else "db2", "simple", ["sql: GROUP BY"] if i < 12 else ["sql: joins 0"],
                 [i % 3 != 0, i % 3 != 0], [["outcome: correct"], ["outcome: correct"]])
        for i in range(24)
    ]


def test_summarize_repeats_and_single():
    s = summarize(_qs(), repeats=2)
    assert s["questions"] == 24 and s["answers"] == 48
    assert s["q_all_correct"] + s["q_all_wrong"] + s["q_mixed"] == 24
    one = summarize([Question(0, "d", "simple", [], [True])], repeats=1)
    assert one["q_mixed"] is None


def test_tag_table_suppresses_small_cells():
    rows = tag_table(_qs(), repeats=2, suppress=13)
    assert all(r["questions"] >= 13 for r in rows)
    rows = tag_table(_qs(), repeats=2, suppress=1)
    assert {r["tag"] for r in rows} >= {"sql: GROUP BY", "sql: joins 0"}


def test_combos_respects_support():
    assert all(c["questions"] >= 15 for c in combos(_qs(), repeats=2, min_support=15))


def test_probe_is_read_only_and_training_only():
    assert probe("no_such_db_x", "SELECT 1")["error"].startswith("no training database")
    assert probe("bad id;", "SELECT 1")["error"] == "invalid database id"
