from benchmark.accuracy_review import Question, combos, summarize, tag_table


def _qs():
    return [
        Question(i, "db1" if i % 2 else "db2", "simple", ["sql: GROUP BY"] if i < 12 else ["sql: joins 0"],
                 [i % 3 != 0, i % 3 != 0], [["outcome: correct"], ["outcome: correct"]])
        for i in range(24)
    ]


def test_summarize_repeats_and_single():
    s = summarize(_qs(), repeats=2)
    assert s["questions"] == 24 and s["answers"] == 48 and s["correct_answers"] == 32
    # Every third question is wrong on both repeats: 16 always right, 8 always wrong.
    assert (s["q_all_correct"], s["q_all_wrong"], s["q_mixed"]) == (16, 8, 0)
    assert s["accuracy"] == 66.67 and s["missed"] == 8.0
    one = summarize([Question(0, "d", "simple", [], [True])], repeats=1)
    assert one["q_mixed"] is None


def test_tag_table_suppresses_small_cells():
    rows = tag_table(_qs(), repeats=2, suppress=13)
    assert all(r["questions"] >= 13 for r in rows)
    rows = tag_table(_qs(), repeats=2, suppress=1)
    assert {r["tag"] for r in rows} >= {"sql: GROUP BY", "sql: joins 0"}


def test_combos_reports_interactions_with_enough_support():
    # Each tag on its own is 75% right, but questions carrying both are 50% right:
    # an interaction worse than both parents. Every question also carries a shape tag, so
    # its pairs and the triple sit within 3 points of a parent and must not be reported.
    questions = [
        Question(i, "db", "simple", [*tags, "shape: single value"], [ok, ok])
        for i, (tags, ok) in enumerate(
            [(["sql: aggregate", "intent: count"], i % 2 == 0) for i in range(20)]
            + [(["sql: aggregate"], True)] * 20
            + [(["intent: count"], True)] * 20
        )
    ]
    found = combos(questions, repeats=2, min_support=15)
    assert [(c["tags"], c["questions"], c["accuracy"]) for c in found] == [
        (["intent: count", "sql: aggregate"], 20, 50.0)
    ]
    assert found[0]["parent_accuracy"] == [75.0, 75.0]
    assert combos(questions, repeats=2, min_support=21) == []  # the pair has only 20 questions

