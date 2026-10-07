"""Code behind published numbers: the R-VES scorer and the held-out split builder."""

import json
import sqlite3
from pathlib import Path

import pytest

from benchmark import rves, splits


@pytest.mark.parametrize(
    "ratio,expected",
    # BIRD's evaluation_ves.py reward bands; boundaries belong to the upper band.
    [(0.0, 0.0), (0.1, 0.25), (0.25, 0.5), (0.49, 0.5), (0.5, 0.75), (0.99, 0.75), (1.0, 1.0),
     (1.99, 1.0), (2.0, 1.25), (50.0, 1.25)],
)
def test_reward_bands_match_bird(ratio: float, expected: float) -> None:
    assert rves.reward(ratio) == expected


def test_clean_abnormal_drops_values_beyond_three_population_sds() -> None:
    timings = [1.0] * 20 + [100.0]
    assert rves.clean_abnormal(timings) == [1.0] * 20
    # Identical timings have zero spread; BIRD's version keeps nothing (a NaN mean), ours keeps all.
    assert rves.clean_abnormal([2.0, 2.0, 2.0]) == [2.0, 2.0, 2.0]


def test_time_ratio_is_positive_and_zero_on_error(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(100)])
    assert rves.time_ratio(db, "SELECT COUNT(*) FROM t", "SELECT COUNT(x) FROM t", 3, 5.0) > 0
    assert rves.time_ratio(db, "SELECT COUNT(*) FROM t", "SELECT nope FROM t", 3, 5.0) == 0.0


def test_rves_scores_only_delivered_correct_answers_of_one_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    questions = tmp_path / "q.json"
    questions.write_text(json.dumps([
        {"question_id": i, "db_id": "d", "question": "q", "SQL": "SELECT 1", "difficulty": tier}
        for i, tier in enumerate(["simple", "simple", "moderate"])
    ]))
    records = [
        {"row_index": 0, "repeat": 0, "official_ex": True, "sql": "SELECT 1", "error": None},
        {"row_index": 1, "repeat": 0, "official_ex": False, "sql": "SELECT 2", "error": None},
        # Marked correct but not delivered (an error): it earns no reward.
        {"row_index": 2, "repeat": 0, "official_ex": True, "sql": "SELECT 1", "error": "x"},
        {"row_index": 1, "repeat": 1, "official_ex": True, "sql": "SELECT 1", "error": None},
    ]
    Path("benchmark/results").mkdir(parents=True)
    Path("benchmark/results/bird_raw_run.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records)
    )
    timed: list[str] = []
    monkeypatch.setattr(rves, "time_ratio", lambda _db, _gold, sql, _it, _to: timed.append(sql) or 4.0)
    out = rves.rves(questions, tmp_path, "run", iterations=1, timeout_s=1.0)
    assert timed == ["SELECT 1"]  # only the delivered, correct answer of repeat 0 is timed
    # One reward of 1.25 out of three questions: sqrt(1.25) * 100 / 3.
    assert out["all"]["questions"] == 3 and out["all"]["ex"] == pytest.approx(33.33)
    assert out["all"]["r_ves"] == pytest.approx(round(1.25 ** 0.5 * 100 / 3, 2))
    assert out["simple"]["r_ves"] == pytest.approx(round(1.25 ** 0.5 * 100 / 2, 2))
    assert out["moderate"]["r_ves"] == 0.0
    assert out["all"]["reward_mix"]["1.25"] == 1


def test_held_out_database_lists_never_overlap() -> None:
    groups = [splits.TRAIN_DEV_DBS, splits.TRAIN_DEV2_DBS, splits.TRAIN_LOCKBOX_DBS]
    every = [db for group in groups for db in group]
    assert len(every) == len(set(every))
    assert [len(group) for group in groups] == [4, 4, 7]


def test_build_routes_each_database_to_exactly_one_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # build() finds local train databases by a repo-relative path
    bird = Path("data/bird")
    lockbox = splits.TRAIN_LOCKBOX_DBS[0]
    local = ["movie", lockbox, *splits.TRAIN_DEV2_DBS, "design_db"]
    for db in local:
        path = bird / "train" / "train_databases" / db / f"{db}.sqlite"
        path.parent.mkdir(parents=True)
        path.touch()
    train = [{"db_id": db, "question": f"q {db}", "evidence": "", "SQL": "SELECT 1"}
             for db in [*local, "not_downloaded"]]
    (bird / "train" / "train.json").write_text(json.dumps(train))
    (bird / "dev").mkdir()
    dev = [{"question_id": i, "db_id": "dev_db", "question": "q", "SQL": "SELECT 1",
            "difficulty": "simple"} for i in (10, 11, 12)]
    (bird / "dev" / "dev.json").write_text(json.dumps(dev))
    (bird / "mini_dev_sqlite.json").write_text(json.dumps([dev[1]]))

    manifest = splits.build(bird)

    def dbs(name: str) -> set[str]:
        rows = json.loads(Path(manifest[name]["questions"]).read_text())
        return {row["db_id"] for row in rows}

    assert dbs("train_dev") == {"movie"}
    assert dbs("train_lockbox") == {lockbox}
    assert dbs("train_dev2") == set(splits.TRAIN_DEV2_DBS)
    # Design gets every other *local* database: never a reserved one, never a missing one.
    assert dbs("train_design") == {"design_db"}
    untouched = json.loads(Path(manifest["dev_untouched"]["questions"]).read_text())
    assert [row["question_id"] for row in untouched] == [10, 12]  # Mini-Dev's id 11 removed
    train_dev = json.loads(Path(manifest["train_dev"]["questions"]).read_text())
    assert train_dev[0]["question_id"] == 0  # train rows keep their train.json index
    assert manifest["mini_dev"]["rows"] == 1 and len(manifest["train_dev"]["sha256_16"]) == 16
