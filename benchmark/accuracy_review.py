"""Accuracy review data: every saved run, scored and tagged, for the interactive report.

No model calls and no spend. Headline numbers use each run's **recorded** official EX;
the only re-execution is of gold SQL, to tag the answer key's result shape (a diagnostic).

Privacy rule (docs/SOTA_PLAN.md protocol): evaluation sets (Mini-Dev, dev, cleaned dev)
are emitted as aggregates only, with cells under ``MIN_CELL`` questions suppressed; no
question id or text from them is written. The lockbox appears only as its published
aggregate. Training splits keep per-question rows for review.

    uv run python -m benchmark.accuracy_review --out review_data.json \\
        [--verdicts verdicts.json] [--audit audit_labels.json]
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchmark.analyze import (
    _bootstrap,
    cost_latency,
    delivered_sql,
    load_runs,
    max_answer_cost,
    p90_seconds,
    sql_complexity,
)
from benchmark.bird import BirdQuestion, db_path_for, load_questions
from benchmark.evaluate import BIRD_OFFICIAL_TIMEOUT_S
from benchmark.patterns import (
    family,
    gold_shape_tags,
    gold_sql_tags,
    outcome_tag,
    question_tags,
    signal_tags,
    size_tag,
)
from benchmark.profile_context import render_profile_facts
from src.db import connect_readonly, execute
from src.db_profile import build_profile

RESULTS = Path("benchmark/results")
MIN_CELL = 10  # evaluation-set cells below this many questions are suppressed
MIN_COMBO_TRAIN = 15
PREVIEW_ROWS = 5
LOCKBOX_RUNS = {"20260927T062743Z", "20260927T063407Z"}  # sealed: never loaded


@dataclass
class SetSpec:
    key: str
    title: str
    kind: str  # "train" | "eval"
    run: str  # raw-file stem suffix of the latest scored configuration
    expect: tuple[int, int]  # recorded (correct answers, answers), asserted exactly
    sample: str | None = None  # why this is not a full set, if it isn't
    note: str = ""


SETS = [
    SetSpec("cleaned_dev", "Cleaned dev (BIRD dev-1106)", "eval", "rank1b_cleaned_dev_full",
            (1020, 1534), note="Primary public checkpoint; 3 of 4 looks used."),
    SetSpec("mini_dev", "Mini-Dev (gate 3)", "eval", "20260927T083717Z", (962, 1500),
            note="500 questions × 3 repeats; 3 of 4 looks used."),
    SetSpec("dev_untouched", "Original dev, untouched rows", "eval", "20260926T212111Z",
            (700, 1036), note="Reporting only; scored before database facts were adopted."),
    SetSpec("train_dev", "train_dev (practice set)", "train", "20260927T060549Z", (703, 1002),
            note="4 train databases × 2 repeats; heavily used for iteration."),
    SetSpec("train_dev2_pilot", "train_dev2 pilot", "train", "20260927T095517Z", (56, 100),
            sample="100 of 503 questions (25 per database), Jev-pilot control arm"),
    SetSpec("numbers_as_text", "Numbers stored as text (train_design)", "train",
            "20260927T041334Z", (59, 194),
            sample="194 targeted questions whose gold uses text-stored numbers numerically; "
                   "scored before database facts"),
]

# Published aggregate only (benchmark/results/rank1b_lockbox_midpoint_outcome.md).
LOCKBOX = {
    "title": "train_lockbox midpoint (sealed)",
    "sample": "175 of 974 questions (25 per database × 7), 3 repeats per arm",
    "without_facts": 79.24, "with_facts": 81.14, "delta": 1.90, "ci": [-0.19, 4.19],
    "note": "1 of 2 looks used; 799 rows sealed. Only the published aggregate is shown.",
}

# Legacy runs without a metadata sidecar, as documented (docs/SOTA_PLAN.md §0.2).
LEGACY = [
    {"set": "mini_dev", "label": "v1 baseline, deepseek-v4-flash-0731, product prompt",
     "ex": 47.6, "questions": 500, "repeats": 1, "date": "2026-09-23",
     "note": "Official re-score; the old local metric showed 45.8%."},
]

# (set key, control run, variant run, lever label). Deltas are paired on shared questions.
PAIRS = [
    ("train_dev", "20260924T005317Z", "20260924T170715Z", "Benchmark prompt profile"),
    ("train_dev", "20260924T170715Z", "20260924T175733Z", "Identifier quoting + pipeline repairs"),
    ("train_dev", "20260924T175733Z", "20260926T203859Z", "Model v4-flash-0731 → v4p1-flash"),
    ("train_dev", "20260926T212754Z", "20260927T060549Z", "Database facts (rank 1b)"),
    ("train_dev", "20260924T175733Z", "20260924T234400Z", "Reasoning, low effort"),
    ("train_dev", "20260924T175733Z", "20260924T234952Z", "Reasoning, high effort"),
    ("train_dev", "20260924T175733Z", "20260925T011431Z", "Few-shot examples"),
    ("train_dev", "20260924T175733Z", "20260924T212220Z", "Data dictionary"),
    ("train_dev", "20260926T212754Z", "20260927T034045Z", "Column notes (rank 1c)"),
    ("train_dev", "20260924T175733Z", "20260925T014638Z", "Model → gpt-oss-120b"),
    ("train_dev", "20260926T212754Z", "20260927T045227Z", "Strategy: query plan first"),
    ("train_dev", "20260926T212754Z", "20260927T045254Z", "Strategy: decompose"),
    ("train_dev", "20260926T212754Z", "20260927T044613Z", "Model → glm-5p3-flash"),
    ("mini_dev", "20260924T232302Z", "20260926T211555Z", "Model v4-flash-0731 → v4p1-flash"),
    ("mini_dev", "20260926T211555Z", "20260927T083717Z", "Database facts + truncation retry"),
    ("dev_untouched", "20260925T015202Z", "20260926T212111Z", "Model v4-flash-0731 → v4p1-flash"),
    ("dev_untouched", "20260925T015202Z", "20260926T215536Z", "Model → gpt-oss-120b"),
    ("cleaned_dev", "20260927T025554Z", "rank1b_cleaned_dev_full", "Database facts (rank 1b)"),
    ("train_dev2_pilot", "20260927T095517Z", "20260927T095645Z", "Jev starting-table advisory"),
    ("train_dev2_pilot", "20260927T095517Z", "20260927T095825Z", "Jev evidence-role advisory"),
]


def raw_path(run: str) -> Path:
    return RESULTS / f"bird_raw_{run}.jsonl"


def meta_for(run: str) -> dict[str, Any]:
    path = RESULTS / f"bird_meta_{run}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def is_correct(record: dict[str, Any]) -> bool:
    return bool(record.get("official_ex"))


def config_label(meta: dict[str, Any]) -> str:
    """Short human label for a run's configuration, from its sidecar."""
    cfg = meta.get("config") or {}
    models = cfg.get("models") or [cfg.get("model", "?")]
    parts = [str(models[0]).split("/")[-1]]
    if cfg.get("prompt_profile"):
        parts.append(f"{cfg['prompt_profile']} profile")
    if cfg.get("reasoning_effort") not in (None, "none"):
        parts.append(f"reasoning {cfg['reasoning_effort']}")
    for flag, name in (("profile_facts", "facts"), ("dictionary", "dictionary"),
                       ("truncation_retry_tokens", "truncation retry"),
                       ("column_meaning", "column notes")):
        if cfg.get(flag):
            parts.append(name)
    if cfg.get("fewshot"):
        parts.append(f"{cfg['fewshot']}-shot")
    if cfg.get("strategy") and cfg["strategy"] != "direct":
        parts.append(f"strategy {cfg['strategy']}")
    if cfg.get("quote_identifiers") is False or cfg.get("pipeline_repairs") is False:
        parts.append("no quoting/repairs")
    return ", ".join(parts)


# --------------------------------------------------------------------------- execution


class GoldCache:
    """Gold results, executed once per (database, SQL) and cached on disk (diagnostic)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}

    def rows(self, db_path: Path, sql: str) -> list[tuple[Any, ...]] | None:
        key = hashlib.sha256(f"{db_path}\n{sql}".encode()).hexdigest()[:24]
        if key not in self.data:
            conn = connect_readonly(db_path, timeout_seconds=BIRD_OFFICIAL_TIMEOUT_S)
            try:
                rows = [list(r) for r in execute(conn, sql, limit=None)[1]]
                self.data[key] = {"rows": rows[:PREVIEW_ROWS], "n": len(rows),
                                  "all_null": all(v is None for r in rows for v in r),
                                  "cols": len(rows[0]) if rows else 0}
            except sqlite3.Error:
                self.data[key] = None
            finally:
                conn.close()
        entry = self.data[key]
        if entry is None:
            return None
        # A compact stand-in that keeps the facts the shape tags need.
        if entry["n"] == 0:
            return []
        filler = [None] * entry["cols"] if entry["all_null"] else [0] * entry["cols"]
        head = [tuple(r) for r in entry["rows"]]
        return head + [tuple(filler)] * (entry["n"] - len(head))

    def preview(self, db_path: Path, sql: str) -> dict[str, Any] | None:
        key = hashlib.sha256(f"{db_path}\n{sql}".encode()).hexdigest()[:24]
        return self.data.get(key)

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, default=str))


def schema_size(db_path: Path) -> tuple[int, int]:
    # connect_readonly's authorizer blocks PRAGMA; schema counting needs a plain read-only handle.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        cols = sum(len(conn.execute(f'PRAGMA table_info("{t}")').fetchall()) for t in tables)
        return len(tables), cols
    finally:
        conn.close()


# --------------------------------------------------------------------------- statistics


@dataclass
class Question:
    key: int
    db: str
    difficulty: str
    q_tags: list[str]
    answers: list[bool]
    answer_tags: list[list[str]] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return sum(self.answers) / len(self.answers)


def summarize(questions: list[Question], repeats: int) -> dict[str, Any]:
    answers = [a for q in questions for a in q.answers]
    out: dict[str, Any] = {
        "questions": len(questions),
        "answers": len(answers),
        "correct_answers": sum(answers),
        "accuracy": round(100 * sum(answers) / len(answers), 2) if answers else None,
        "missed": round(sum(1 - q.mean for q in questions), 2),
    }
    if repeats > 1:
        out["q_all_correct"] = sum(1 for q in questions if all(q.answers))
        out["q_all_wrong"] = sum(1 for q in questions if not any(q.answers))
        out["q_mixed"] = len(questions) - out["q_all_correct"] - out["q_all_wrong"]
    else:
        out["q_correct"] = sum(1 for q in questions if q.answers[0])
        out["q_wrong"] = len(questions) - out["q_correct"]
        out["q_mixed"] = None  # not applicable with one repeat
    if len(questions) >= 2:
        means = [q.mean for q in questions]
        mu = sum(means) / len(means)
        sd = math.sqrt(sum((m - mu) ** 2 for m in means) / (len(means) - 1))
        half = 1.96 * sd / math.sqrt(len(means))
        out["ci"] = [round(100 * (mu - half), 1), round(100 * (mu + half), 1)]
    return out


def breakdown(questions: list[Question], attr: str, repeats: int, suppress: int) -> dict[str, Any]:
    groups: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        groups[getattr(q, attr)].append(q)
    return {k: summarize(v, repeats) for k, v in sorted(groups.items()) if len(v) >= suppress}


def tag_table(questions: list[Question], repeats: int, suppress: int) -> list[dict[str, Any]]:
    """One row per tag. Question-level tags count questions; answer-level tags (outcome,
    signal) count the answers carrying them and the questions with any such answer."""
    base = summarize(questions, repeats)["accuracy"] or 0.0
    rows = []
    q_level: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        for tag in q.q_tags:
            q_level[tag].append(q)
    for tag, members in q_level.items():
        if len(members) < suppress:
            continue
        row = {"tag": tag, "family": family(tag), **summarize(members, repeats)}
        row["lift"] = round(row["accuracy"] - base, 2)
        row["by_db"] = breakdown(members, "db", repeats, suppress)
        row["by_difficulty"] = breakdown(members, "difficulty", repeats, suppress)
        rows.append(row)
    a_level: dict[str, list[tuple[Question, bool]]] = defaultdict(list)
    for q in questions:
        for tags, ok in zip(q.answer_tags, q.answers, strict=True):
            for tag in tags:
                a_level[tag].append((q, ok))
    for tag, pairs in a_level.items():
        distinct = {id(q) for q, _ in pairs}
        if len(distinct) < suppress:
            continue
        correct = sum(ok for _, ok in pairs)
        rows.append({
            "tag": tag, "family": family(tag), "answer_level": True,
            "questions": len(distinct), "answers": len(pairs), "correct_answers": correct,
            "accuracy": round(100 * correct / len(pairs), 2),
            "missed": round(sum(1 for _, ok in pairs if not ok) / repeats, 2),
            "lift": round(100 * correct / len(pairs) - base, 2),
        })
    return sorted(rows, key=lambda r: -r["missed"])


def combos(questions: list[Question], repeats: int, min_support: int) -> list[dict[str, Any]]:
    """Pairs and triples of question-level tags that are *worse or better* than both
    parents by ≥ 3 points; ranked by missed questions. Redundant combinations are dropped."""
    acc_of: dict[frozenset[str], tuple[float, int, float]] = {}

    def stats(members: list[Question]) -> tuple[float, int, float]:
        s = summarize(members, repeats)
        return s["accuracy"], s["questions"], s["missed"]

    index: dict[str, set[int]] = defaultdict(set)
    for i, q in enumerate(questions):
        for tag in q.q_tags:
            if family(tag) in {"sql", "intent", "evidence", "shape", "size"}:
                index[tag].add(i)
    frequent = sorted(t for t, ids in index.items() if len(ids) >= min_support)
    for tag in frequent:
        acc_of[frozenset([tag])] = stats([questions[i] for i in index[tag]])
    out: list[dict[str, Any]] = []
    for size in (2, 3):
        for combo in itertools.combinations(frequent, size):
            ids = set.intersection(*(index[t] for t in combo))
            if len(ids) < min_support:
                continue
            acc, n, missed = stats([questions[i] for i in ids])
            parents = [frozenset(p) for p in itertools.combinations(combo, size - 1)]
            parent_accs = [acc_of[p][0] for p in parents if p in acc_of]
            if len(parent_accs) != len(parents):
                continue
            acc_of[frozenset(combo)] = (acc, n, missed)
            if acc <= min(parent_accs) - 3 or acc >= max(parent_accs) + 3:
                out.append({"tags": list(combo), "questions": n, "accuracy": acc,
                            "missed": missed, "parent_accuracy": parent_accs})
    return sorted(out, key=lambda r: -r["missed"])[:40]


# --------------------------------------------------------------------------- sets


def load_set(spec: SetSpec, cache: GoldCache) -> tuple[list[BirdQuestion], dict[int, list[dict[str, Any]]], dict[str, Any], Path]:
    meta = meta_for(spec.run)
    questions = load_questions(meta["questions"])
    runs = load_runs(raw_path(spec.run), questions)
    return questions, runs, meta, Path(meta["db_dir"])


def build_set(spec: SetSpec, cache: GoldCache, verdicts: dict[str, dict[str, Any]],
              audit: dict[str, dict[str, Any]]) -> dict[str, Any]:
    questions, runs, meta, db_dir = load_set(spec, cache)
    by_row = {q.row_index: q for q in questions}
    repeats = int(meta.get("repeats") or 1)
    recorded = sum(is_correct(r) for rows in runs.values() for r in rows)
    answers = sum(len(rows) for rows in runs.values())
    if (recorded, answers) != spec.expect:
        raise SystemExit(f"{spec.key}: recorded {recorded}/{answers} ≠ expected {spec.expect}")
    facts_on = bool((meta.get("config") or {}).get("profile_facts"))
    profiles: dict[str, Any] = {}
    sizes: dict[str, tuple[int, int]] = {}
    items: list[Question] = []
    train_rows: list[dict[str, Any]] = []
    for row in sorted(runs):
        q = by_row[row]
        db_path = db_path_for(q.db_id, db_dir=db_dir)
        if q.db_id not in sizes:
            sizes[q.db_id] = schema_size(db_path)
            if facts_on:
                profiles[q.db_id] = build_profile(db_path)
        gold = cache.rows(db_path, q.gold_sql)
        difficulty = q.difficulty if q.difficulty != "unknown" else f"proxy: {sql_complexity(q.gold_sql)}"
        q_tags = (gold_sql_tags(q.gold_sql) + question_tags(q.question, q.evidence)
                  + gold_shape_tags(gold) + [size_tag(*sizes[q.db_id])])
        facts = (bool(render_profile_facts(profiles[q.db_id], q.question, q.evidence))
                 if facts_on else None)
        records = runs[row]
        oks = [is_correct(r) for r in records]
        a_tags = [[outcome_tag(r, gold, ok)] + signal_tags(r, facts) for r, ok in zip(records, oks, strict=True)]
        items.append(Question(row, q.db_id, difficulty, q_tags, oks, a_tags))
        if spec.kind == "train":
            # Review-packet ids use the question file's stem and the dataset row.
            case_id = f"{Path(meta['questions']).stem}:{row}"
            preview = cache.preview(db_path, q.gold_sql)
            train_rows.append({
                "id": case_id, "db": q.db_id, "question": q.question, "evidence": q.evidence,
                "gold_sql": q.gold_sql, "gold_preview": preview,
                "ours": [{"sql": delivered_sql(r), "correct": ok,
                          "rows": (r.get("rows") or [])[:PREVIEW_ROWS],
                          "row_count": r.get("result_row_count"),
                          "error": r.get("error_category")}
                         for r, ok in zip(records, oks, strict=True)],
                "difficulty": difficulty, "tags": q_tags,
                "answer_tags": a_tags, "verdict": verdicts.get(case_id),
                "audit": audit.get(case_id),
            })
    suppress = MIN_CELL if spec.kind == "eval" else 1
    measured, uncached, p50 = cost_latency(runs)
    stability = None
    if repeats > 1:
        sig_differs = sum(1 for rows in runs.values()
                          if len({r.get("result_signature") for r in rows}) > 1)
        stability = {"mixed_questions": sum(1 for q in items if 0 < sum(q.answers) < len(q.answers)),
                     "signature_differs": sig_differs, "questions": len(items)}
    by_db = breakdown(items, "db", repeats, suppress)
    macro = sum(v["accuracy"] for v in by_db.values()) / len(by_db) if by_db else None
    out = {
        "key": spec.key, "title": spec.title, "kind": spec.kind, "sample": spec.sample,
        "note": spec.note, "run": spec.run, "config": config_label(meta),
        "commit": (meta.get("git_commit") or "")[:7], "dirty": meta.get("git_dirty"),
        "config_hash": meta.get("config_sha256_16"), "dataset_hash": meta.get("dataset_sha256_16"),
        "database_hash": meta.get("database_sha256_16") if isinstance(meta.get("database_sha256_16"), str) else None,
        "repeats": repeats, "summary": summarize(items, repeats), "macro": round(macro, 2) if macro else None,
        "by_db": by_db, "by_difficulty": breakdown(items, "difficulty", repeats, suppress),
        "tags": tag_table(items, repeats, suppress),
        "combos": combos(items, repeats, MIN_CELL if spec.kind == "eval" else MIN_COMBO_TRAIN),
        "cost": {"measured_usd": round(measured, 6), "uncached_usd": round(uncached, 6),
                 "max_answer_usd": round(max_answer_cost(runs), 6),
                 "p50_s": round(p50, 2), "p90_s": round(p90_seconds(runs), 2)},
        "stability": stability,
    }
    if spec.kind == "train":
        out["rows"] = train_rows
    return out


def all_runs() -> list[dict[str, Any]]:
    """Every run with a sidecar (lockbox excluded), for the scores table."""
    out = []
    for meta_path in sorted(RESULTS.glob("bird_meta_*.json")):
        run = meta_path.stem.removeprefix("bird_meta_")
        if run in LOCKBOX_RUNS or not raw_path(run).exists():
            continue
        meta = json.loads(meta_path.read_text())
        records = [json.loads(line) for line in raw_path(run).read_text().splitlines() if line.strip()]
        if not records:
            continue
        questions_file = str(meta.get("questions", "?"))
        full = len(load_questions(questions_file)) if Path(questions_file).exists() else None
        out.append({
            "run": run, "questions_file": Path(questions_file).name,
            "config": config_label(meta), "questions": meta.get("question_count"),
            "full_size": full, "sample": bool(full and meta.get("question_count") and meta["question_count"] < full),
            "repeats": meta.get("repeats"), "answers": len(records),
            "correct_answers": sum(is_correct(r) for r in records),
            "accuracy": round(100 * sum(is_correct(r) for r in records) / len(records), 2),
            "commit": (meta.get("git_commit") or "")[:7], "dirty": meta.get("git_dirty"),
            "config_hash": meta.get("config_sha256_16"), "complete": meta.get("complete"),
        })
    return out


def paired(set_key: str, control: str, variant: str, label: str) -> dict[str, Any]:
    meta = meta_for(variant) or meta_for(control)
    questions = load_questions(meta["questions"])
    a, b = load_runs(raw_path(control), questions), load_runs(raw_path(variant), questions)
    by_row = {q.row_index: q for q in questions}
    shared = sorted(set(a) & set(b))
    deltas: dict[str, list[float]] = defaultdict(list)
    fixes = regressions = 0
    for row in shared:
        ca = sum(is_correct(r) for r in a[row]) / len(a[row])
        cb = sum(is_correct(r) for r in b[row]) / len(b[row])
        deltas[by_row[row].db_id].append(cb - ca)
        fixes += cb > ca
        regressions += cb < ca
    mean = sum(sum(v) for v in deltas.values()) / len(shared)
    (row_ci, macro_ci) = _bootstrap(deltas, 2000, 0)
    return {"set": set_key, "lever": label, "control": control, "variant": variant,
            "control_config": config_label(meta_for(control)), "variant_config": config_label(meta),
            "questions": len(shared), "delta": round(100 * mean, 2),
            "ci": [round(100 * row_ci[0], 2), round(100 * row_ci[1], 2)],
            "macro_ci": [round(100 * macro_ci[0], 2), round(100 * macro_ci[1], 2)],
            "fixes": fixes, "regressions": regressions}


def assert_private(data: dict[str, Any]) -> None:
    """Fail if any evaluation-set question text or id leaked into the output."""
    blob = json.dumps(data)
    for spec in SETS:
        if spec.kind != "eval":
            continue
        meta = meta_for(spec.run)
        for q in load_questions(meta["questions"]):
            if len(q.question) > 25 and q.question in blob:
                raise SystemExit(f"privacy check failed: {spec.key} question text in output")
        for entry in data["sets"]:
            if entry["key"] == spec.key and "rows" in entry:
                raise SystemExit(f"privacy check failed: {spec.key} has per-question rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/profiles/gold_cache.json"))
    parser.add_argument("--verdicts", type=Path, help="answer-key review verdicts {case_id: {...}}")
    parser.add_argument("--audit", type=Path, help="two-stage audit labels {case_id: {...}}")
    args = parser.parse_args()
    verdicts = json.loads(args.verdicts.read_text()) if args.verdicts else {}
    audit = json.loads(args.audit.read_text()) if args.audit else {}
    cache = GoldCache(args.cache)
    try:
        sets = [build_set(spec, cache, verdicts, audit) for spec in SETS]
    finally:
        cache.save()
    data = {
        "generated": "benchmark/accuracy_review.py",
        "sets": sets, "lockbox": LOCKBOX, "legacy": LEGACY,
        "runs": all_runs(), "pairs": [paired(*p) for p in PAIRS],
        "min_cell": MIN_CELL,
        "verdict_counts": dict(Counter(v.get("verdict") for v in verdicts.values())),
    }
    assert_private(data)
    args.out.write_text(json.dumps(data, default=str))
    for s in sets:
        summary = s["summary"]
        print(f"{s['key']:18} {summary['correct_answers']}/{summary['answers']} "
              f"({summary['accuracy']}%) tags={len(s['tags'])} combos={len(s['combos'])}")


if __name__ == "__main__":
    main()
