"""Build the evaluation splits used by docs/SOTA_PLAN.md (no API calls).

- ``train_dev.json``: BIRD *train* questions on 4 train databases never used for prompts,
  few-shot pools, or GEPA. They are the frequent A/B set, so over time they *become* a
  development set; report them per database (``soccer_2016`` alone is half the rows).
- ``train_lockbox.json``: BIRD train questions on 7 further unseen databases across
  different domains, looked at only at gates (alongside Mini-Dev), never to choose between variants. This is the
  closest local proxy for the hidden test's unseen databases.
- ``dev_untouched.json``: BIRD dev minus every Mini-Dev question id (1,036 rows), scored on
  BIRD dev's own databases: 5 of Mini-Dev's 11 differ in content, changing 60 of these gold
  results (and 23 of Mini-Dev's), so each question set is scored only on its own databases.
  Same 11 schemas as Mini-Dev, so it is *not* a generalization check; it is reported
  separately and never tuned on.
- Mini-Dev itself (``mini_dev_sqlite.json``, 500 rows) stays the infrequent gate.

If BIRD-Verified (``data/bird/verified/bird-verified-train.json``, from ReViSQL; ids are
train.json row indices) is present, two more artifacts are built for the train splits:

- ``verified_train_dev.json`` / ``verified_train_lockbox.json``: the verified rows with their
  *corrected* question, evidence, and SQL: a separate corrected-input evaluation.
- ``verified_gold_same_inputs.json``: corrected SQL only for rows whose question and evidence
  are unchanged, so it can grade ordinary runs on the original questions
  (``analyze rescore --corrected-gold``). Rows with revised inputs are excluded: their
  corrected SQL answers a different question.

A ``manifest.json`` records each split's source fingerprints so scores from different dataset
versions are never mixed.

    uv run python -m benchmark.splits
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark.bird import DEFAULT_BIRD_DIR, dataset_fingerprint

# Train databases fetched without keeping the 8.9GB archive (scripts/stream_inner_zip.py):
# the first six in archive order, then five more chosen for domains the first six lack
# (healthcare, finance/complaints, education, government, logistics). Fixed once chosen:
# changing either list invalidates every score on it. The lockbox holds the databases whose
# gold SQL is cleanest (restaurant has 19/117 empty gold results, soccer_2016 5, movie 2;
# the lockbox's seven have 5 empty results in 974 rows and no gold errors).
TRAIN_DEV_DBS = ("movie", "restaurant", "sales_in_weather", "soccer_2016")
TRAIN_LOCKBOX_DBS = (
    "european_football_1",
    "food_inspection_2",
    "olympics",
    "retail_complains",
    "shipping",
    "synthea",
    "university",
)


def build(bird_dir: Path = DEFAULT_BIRD_DIR) -> dict[str, Any]:
    out_dir = bird_dir / "splits"
    out_dir.mkdir(exist_ok=True)
    mini_path = bird_dir / "mini_dev_sqlite.json"
    dev_path = bird_dir / "dev" / "dev.json"
    train_path = bird_dir / "train" / "train.json"

    mini_ids = {item["question_id"] for item in json.loads(mini_path.read_text())}
    untouched = [q for q in json.loads(dev_path.read_text()) if q["question_id"] not in mini_ids]
    # Train rows have no ids; the train.json row index is kept as a traceable id.
    train = [
        {"question_id": index, **item, "difficulty": item.get("difficulty", "unknown")}
        for index, item in enumerate(json.loads(train_path.read_text()))
    ]
    train_dir = "data/bird/train/train_databases"
    splits = {
        "train_dev": ([q for q in train if q["db_id"] in TRAIN_DEV_DBS], train_dir, train_path),
        "train_lockbox": (
            [q for q in train if q["db_id"] in TRAIN_LOCKBOX_DBS],
            train_dir,
            train_path,
        ),
        "dev_untouched": (untouched, "data/bird/dev/dev_databases", dev_path),
    }
    manifest: dict[str, Any] = {
        "mini_dev": {
            "questions": str(mini_path),
            "db_dir": "data/bird/dev_databases",
            "rows": len(json.loads(mini_path.read_text())),
            "sha256_16": dataset_fingerprint(mini_path),
        }
    }
    for name, (rows, db_dir, source) in splits.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(rows, indent=1) + "\n")
        manifest[name] = {
            "questions": str(path),
            "db_dir": db_dir,
            "rows": len(rows),
            "sha256_16": dataset_fingerprint(path),
            "source": str(source),
            "source_sha256_16": dataset_fingerprint(source),
            "by_db": dict(Counter(row["db_id"] for row in rows)),
            "by_difficulty": dict(Counter(row["difficulty"] for row in rows)),
        }
    verified_path = bird_dir / "verified" / "bird-verified-train.json"
    if verified_path.exists():
        manifest.update(_verified_splits(verified_path, train, out_dir))
    manifest["train_dev"]["databases"] = list(TRAIN_DEV_DBS)
    manifest["train_lockbox"]["databases"] = list(TRAIN_LOCKBOX_DBS)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def _normalized(text: str | None) -> str:
    return " ".join((text or "").split())


def _verified_splits(
    verified_path: Path, train: list[dict[str, Any]], out_dir: Path
) -> dict[str, Any]:
    verified = json.loads(verified_path.read_text())
    entries: dict[str, Any] = {}
    same_inputs_gold = []
    for name, databases in (
        ("verified_train_dev", TRAIN_DEV_DBS),
        ("verified_train_lockbox", TRAIN_LOCKBOX_DBS),
    ):
        rows = []
        for item in verified:
            if item["db_id"] not in databases:
                continue
            index = int(item["question_id"])
            original = train[index]
            inputs_revised = any(
                _normalized(item[field]) != _normalized(original[field])
                for field in ("question", "evidence")
            )
            sql_revised = _normalized(item["SQL"]) != _normalized(original["SQL"])
            rows.append(
                {
                    "question_id": index,
                    "db_id": item["db_id"],
                    "question": item["question"],
                    "evidence": item["evidence"],
                    "SQL": item["SQL"],
                    "difficulty": "unknown",
                    "inputs_revised": inputs_revised,
                    "sql_revised": sql_revised,
                    "grading_method": (item.get("grading_method") or "set").strip(),
                }
            )
            if not inputs_revised:
                same_inputs_gold.append({"question_id": index, "SQL": item["SQL"]})
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(rows, indent=1) + "\n")
        entries[name] = {
            "questions": str(path),
            "db_dir": "data/bird/train/train_databases",
            "rows": len(rows),
            "sha256_16": dataset_fingerprint(path),
            "source": str(verified_path),
            "source_sha256_16": dataset_fingerprint(verified_path),
            "inputs_revised": sum(row["inputs_revised"] for row in rows),
            "sql_revised": sum(row["sql_revised"] for row in rows),
            "non_set_grading": sum(row["grading_method"] != "set" for row in rows),
            "by_db": dict(Counter(row["db_id"] for row in rows)),
        }
    gold_path = out_dir / "verified_gold_same_inputs.json"
    gold_path.write_text(json.dumps(same_inputs_gold, indent=1) + "\n")
    entries["verified_gold_same_inputs"] = {
        "questions": str(gold_path),
        "rows": len(same_inputs_gold),
        "sha256_16": dataset_fingerprint(gold_path),
        "use": "analyze rescore --corrected-gold (ordinary runs on original questions)",
    }
    return entries


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
