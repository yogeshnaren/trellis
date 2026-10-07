from benchmark.accuracy_review import Question, combos, summarize, tag_table


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

