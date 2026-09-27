"""Build a human-review packet: is BIRD's answer key wrong, or are we?

Collects, from runs on the *practice* splits only (``train_dev``, ``train_design``), every
question where a rejected experiment and the answer key disagreed in a way that decided
the experiment, plus the questions every candidate answered the same way against the key.
Evaluation sets (Mini-Dev, cleaned dev, ``dev_untouched``, lockbox) are excluded: reading
their questions one by one is off-limits by protocol (SOTA plan §5.10).

Each case carries the question, hint, answer-key SQL and every distinct answer we
produced, with what each returned when executed locally (first rows, row count), the
official score, an automatic category, and whether BIRD's own filtered train set kept the
question. Output is one JSON file for the review page.

    python -m benchmark.review_packet --out review_cases.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from benchmark.analyze import bucket, delivered_sql, load_runs
from benchmark.bird import BirdQuestion, db_path_for, load_questions
from src.db import connect_readonly, execute, timeout_for_database

RESULTS = Path("benchmark/results")
TRAIN_DB_DIR = Path("data/bird/train/train_databases")
FILTERED = Path("data/bird/train_filtered/train-00000-of-00001.jsonl")
PREVIEW_ROWS = 5
ROW_CAP = 10_000

# (key, title, what it tested, split, control run, variant run, variant label, control label)
EXPERIMENTS = [
    ("reasoning_low", "Reasoning (low effort)", "Let the model think before answering",
     "train_dev", "20260924T175733Z", "20260924T234400Z", "reasoning low", "accepted"),
    ("reasoning_high", "Reasoning (high effort)", "Let the model think longer before answering",
     "train_dev", "20260924T175733Z", "20260924T234952Z", "reasoning high", "accepted"),
    ("fewshot", "Few-shot examples", "Show 3 solved examples from other databases",
     "train_dev", "20260924T175733Z", "20260925T011431Z", "few-shot", "accepted"),
    ("dictionary", "Data dictionary", "Add BIRD's column descriptions for every column",
     "train_dev", "20260924T175733Z", "20260924T212220Z", "dictionary", "accepted"),
    ("column_meaning", "Relevant column notes (rank 1c)",
     "Add up to 6 relevant column descriptions",
     "train_dev", "20260926T212754Z", "20260927T034045Z", "column notes", "accepted (v4p1)"),
]
BANK = {  # rank 4 candidate bank on train_dev, first repeat of each
    "direct": "20260926T212754Z",
    "plan": "20260927T045227Z",
    "decompose": "20260927T045254Z",
    "glm-5p3-flash": "20260927T044613Z",
}
NUMERIC_TEXT_RUN = "20260927T041334Z"  # 194 train_design questions using numbers stored as text

_CAST = re.compile(r"\bCAST\s*\(|\bREPLACE\s*\(", re.IGNORECASE)
_NULL = re.compile(r"\bIS\s+(NOT\s+)?NULL\b|\bCOALESCE\s*\(|\bIFNULL\s*\(", re.IGNORECASE)
_DISTINCT = re.compile(r"COUNT\s*\(\s*DISTINCT", re.IGNORECASE)
_ROUND = re.compile(r"\bROUND\s*\(", re.IGNORECASE)


def tags(gold_sql: str, sql: str | None, shape: str, gold_rows: int | None) -> list[str]:
    """Automatic, observable categories for a wrong answer (a starting point for review)."""
    out: list[str] = []
    if gold_rows == 0:
        out.append("answer key returns nothing")
    if sql:
        for name, pattern in (
            ("numbers stored as text (convert vs not)", _CAST),
            ("NULL / empty-value handling", _NULL),
            ("COUNT DISTINCT vs COUNT", _DISTINCT),
            ("rounding", _ROUND),
        ):
            if bool(pattern.search(gold_sql)) != bool(pattern.search(sql)):
                out.append(name)
    shape_names = {
        "extra-columns": "returns extra columns",
        "missing-columns": "returns fewer columns",
        "row-count-differs": "different number of rows",
        "values-differ": "same shape, different values",
        "empty-result": "we return nothing",
        "gold-exec-error": "answer key fails to run",
    }
    if shape in shape_names:
        out.append(shape_names[shape])
    elif shape.startswith(("pipeline-", "answered-")):
        out.append("no SQL delivered")
    return out or ["other"]


class Executor:
    """Runs SQL locally once per (database, SQL), bounded, for previews."""

    def __init__(self) -> None:
        self.cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.conns: dict[str, Any] = {}

    def run(self, db_id: str, sql: str | None) -> dict[str, Any]:
        if not sql:
            return {"error": "no SQL delivered"}
        key = (db_id, sql)
        if key not in self.cache:
            if db_id not in self.conns:
                path = db_path_for(db_id, db_dir=TRAIN_DB_DIR)
                self.conns[db_id] = connect_readonly(
                    path, timeout_seconds=timeout_for_database(path, default=30.0)
                )
            try:
                columns, rows, truncated = execute(self.conns[db_id], sql, limit=ROW_CAP)
                self.cache[key] = {
                    "columns": columns,
                    "rows": [[_cell(v) for v in row] for row in rows[:PREVIEW_ROWS]],
                    "row_count": len(rows),
                    "row_count_capped": truncated,
                    "_all": rows,
                }
            except sqlite3.Error as exc:  # timeouts, SQLite errors: shown to the reviewer
                self.cache[key] = {"error": str(exc)[:200]}
        return self.cache[key]

    def close(self) -> None:
        for conn in self.conns.values():
            conn.close()


def _cell(value: Any) -> Any:
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, str) and len(value) > 80:
        return value[:79] + "…"
    return value


def _public(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if not k.startswith("_")}


def build() -> dict[str, Any]:
    kept = {
        (row["db_id"], row["question"].strip())
        for row in map(json.loads, FILTERED.read_text().splitlines())
    }
    splits = {
        name: load_questions(Path(f"data/bird/splits/{name}.json"))
        for name in ("train_dev", "train_design")
    }
    by_row = {name: {q.row_index: q for q in qs} for name, qs in splits.items()}
    executor = Executor()
    cases: dict[tuple[str, int], dict[str, Any]] = {}

    def case(split: str, row: int) -> dict[str, Any]:
        key = (split, row)
        if key not in cases:
            q: BirdQuestion = by_row[split][row]
            gold = executor.run(q.db_id, q.gold_sql)
            cases[key] = {
                "id": f"{split}:{row}",
                "split": split,
                "db_id": q.db_id,
                "question_id": q.question_id,
                "question": q.question,
                "evidence": q.evidence,
                "gold_sql": q.gold_sql,
                "gold": _public(gold),
                "bird_filter_kept": (q.db_id, q.question.strip()) in kept,
                "candidates": {},
                "sources": [],
                "_gold_rows": gold.get("_all"),
            }
        return cases[key]

    def add_candidate(c: dict[str, Any], label: str, record: dict[str, Any]) -> None:
        sql = delivered_sql(record)
        norm = " ".join((sql or "").split())
        entry = c["candidates"].setdefault(norm or f"<none:{label}>", {
            "sql": sql, "labels": [], "correct": bool(record.get("official_ex")),
            "error": record.get("error_category"),
        })
        if label not in entry["labels"]:
            entry["labels"].append(label)

    experiments = []
    for key, title, what, split, control, variant, vlabel, clabel in EXPERIMENTS:
        qs = splits[split]
        old = load_runs(RESULTS / f"bird_raw_{control}.jsonl", qs)
        new = load_runs(RESULTS / f"bird_raw_{variant}.jsonl", qs)
        fixes = regressions = 0
        for row in sorted(set(old) & set(new)):
            was = sum(bool(r.get("official_ex")) for r in old[row]) / len(old[row])
            now = sum(bool(r.get("official_ex")) for r in new[row]) / len(new[row])
            if was == now:
                continue
            effect = "fix" if now > was else "regression"
            fixes += effect == "fix"
            regressions += effect == "regression"
            c = case(split, row)
            c["sources"].append({"experiment": key, "effect": effect, "control_score": was,
                                 "variant_score": now})
            for r in old[row]:
                add_candidate(c, clabel, r)
            for r in new[row]:
                add_candidate(c, vlabel, r)
        experiments.append({
            "key": key, "title": title, "what": what, "split": split,
            "control_run": control, "variant_run": variant,
            "compared_questions": len(set(old) & set(new)),
            "fixes": fixes, "regressions": regressions,
            "control_label": clabel, "variant_label": vlabel,
        })

    bank = {label: load_runs(RESULTS / f"bird_raw_{ts}.jsonl", splits["train_dev"])
            for label, ts in BANK.items()}
    unanimous_wrong = 0
    for row in sorted(set.intersection(*(set(b) for b in bank.values()))):
        first = {label: runs[row][0] for label, runs in bank.items()}
        if any(r.get("official_ex") for r in first.values()):
            continue
        db_id = by_row["train_dev"][row].db_id
        results = set()
        for r in first.values():
            rows = executor.run(db_id, delivered_sql(r)).get("_all")
            results.add(None if rows is None else frozenset(rows))
        if len(results) != 1 or None in results:
            continue  # candidates disagree, or none returned a result
        unanimous_wrong += 1
        c = case("train_dev", row)
        c["sources"].append({"experiment": "bank_unanimous", "effect": "all wrong, same answer"})
        for label, r in first.items():
            add_candidate(c, label, r)
    experiments.append({
        "key": "bank_unanimous", "title": "All four approaches agree, answer key disagrees",
        "what": "Rank 4 bank: direct, plan, decompose and glm-5p3-flash returned the same "
                "result, scored wrong",
        "split": "train_dev", "control_run": BANK["direct"], "variant_run": None,
        "compared_questions": 501, "fixes": 0, "regressions": unanimous_wrong,
    })

    numeric = load_runs(RESULTS / f"bird_raw_{NUMERIC_TEXT_RUN}.jsonl", splits["train_design"])
    numeric_wrong = 0
    for row, runs in sorted(numeric.items()):
        if runs[0].get("official_ex"):
            continue
        numeric_wrong += 1
        c = case("train_design", row)
        c["sources"].append({"experiment": "numbers_as_text", "effect": "wrong"})
        add_candidate(c, "direct (v4p1)", runs[0])
    experiments.append({
        "key": "numbers_as_text", "title": "Numbers stored as text",
        "what": "194 practice questions that do maths or ordering on numbers stored as text",
        "split": "train_design", "control_run": NUMERIC_TEXT_RUN, "variant_run": None,
        "compared_questions": len(numeric), "fixes": 0, "regressions": numeric_wrong,
    })

    out = []
    for c in cases.values():
        gold_rows = c.pop("_gold_rows")
        candidates = []
        for entry in c["candidates"].values():
            result = executor.run(c["db_id"], entry["sql"])
            shape = (
                "correct" if entry["correct"] else bucket(
                    {"response_type": "query", "error_category": entry["error"]},
                    gold_rows, result.get("_all"),
                )
            )
            candidates.append({
                **entry,
                "result": _public(result),
                "shape": shape,
                "tags": [] if entry["correct"] else tags(
                    c["gold_sql"], entry["sql"], shape, c["gold"].get("row_count")
                ),
            })
        c["candidates"] = sorted(candidates, key=lambda e: (e["correct"], e["labels"]))
        wrong = [e for e in candidates if not e["correct"]]
        c["tags"] = sorted({t for e in wrong for t in e["tags"]}) or ["other"]
        out.append(c)
    executor.close()
    return {"experiments": experiments, "cases": out}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    packet = build()
    args.out.write_text(json.dumps(packet, default=str))
    print(f"{len(packet['cases'])} cases -> {args.out}")
    for e in packet["experiments"]:
        print(f"  {e['key']:16s} fixes {e['fixes']:3d}  regressions/wrong {e['regressions']:3d}")


if __name__ == "__main__":
    main()
