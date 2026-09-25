"""Offline re-scoring and failure analysis for BIRD runs — no API calls, no spend.

``rescore`` re-executes every gold and predicted query of a raw ``run_bird`` JSONL under BIRD's
official execution-accuracy rule, buckets failures by result shape, and measures
*output-contract counterfactuals*: failures that become correct under a purely presentational
rewrite (dropping extra columns, removing ROUND, splitting a name concatenation). This is how
docs/SOTA_PLAN.md §2 was produced. Those rewrites are chosen *using the gold result*, so they
are an oracle ceiling for investigation, never a measured gain.

``flips`` compares two runs question-by-question: a per-difficulty flip matrix plus an exact
McNemar test, so a change is judged on paired evidence rather than two noisy headline numbers.

    uv run python -m benchmark.analyze rescore benchmark/results/bird_raw_<ts>.jsonl \\
        --corrected-gold data/bird/arcwise_plat_sql.json
    uv run python -m benchmark.analyze flips OLD.jsonl NEW.jsonl
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from benchmark.bird import (
    DEFAULT_DB_DIR,
    DEFAULT_QUESTIONS,
    BirdQuestion,
    db_path_for,
    load_questions,
)
from benchmark.evaluate import BIRD_OFFICIAL_TIMEOUT_S
from src.costs import cost_usd
from src.db import connect_readonly, execute

DIFFICULTIES = ("simple", "moderate", "challenging")
Rows = list[tuple[Any, ...]]
# Bound the column-subset search when a prediction projects many more columns than gold.
MAX_PROJECTION_TRIES = 5_000


def run_query(db_path: Path, sql: str) -> Rows | None:
    """Execute one query read-only with BIRD's evaluation timeout; None on any error."""
    conn = connect_readonly(db_path, timeout_seconds=BIRD_OFFICIAL_TIMEOUT_S)
    try:
        return execute(conn, sql, limit=None)[1]
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def load_runs(path: Path, questions: list[BirdQuestion]) -> dict[int, list[dict[str, Any]]]:
    """Load a single-model raw run keyed by dataset row, keeping every repeat.

    Runs recorded before ``row_index`` existed are mapped by question id, assigning repeated
    ids (Mini-Dev's duplicated 137/138) to their dataset rows in order of appearance,
    separately within each repeat.
    """
    rows_for_id: dict[int, list[int]] = defaultdict(list)
    for question in questions:
        rows_for_id[question.question_id].append(question.row_index)
    seen: Counter[tuple[int, int]] = Counter()
    records: dict[int, list[dict[str, Any]]] = defaultdict(list)
    models: set[str] = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        models.add(str(record.get("model")))
        if "row_index" in record:
            row = int(record["row_index"])
        else:
            question_id, repeat = int(record["question_id"]), int(record.get("repeat", 0))
            candidates = rows_for_id[question_id]
            if seen[(question_id, repeat)] >= len(candidates):
                continue
            row = candidates[seen[(question_id, repeat)]]
            seen[(question_id, repeat)] += 1
        records[row].append(record)
    if len(models) > 1:
        raise SystemExit(f"{path} mixes models {sorted(models)}; analyze one model per file")
    for runs in records.values():
        runs.sort(key=lambda record: int(record.get("repeat", 0)))
    return dict(records)


def load_run(path: Path, questions: list[BirdQuestion]) -> dict[int, dict[str, Any]]:
    """First repeat of each row (see ``load_runs``)."""
    return {row: runs[0] for row, runs in load_runs(path, questions).items()}


def sql_complexity(sql: str) -> str:
    """Deterministic complexity band from gold SQL, for splits without difficulty labels.

    Counts joins, extra SELECT scopes (subqueries/CTE bodies), set operations, window
    functions, and aggregation/grouping; bands are low (0-1), medium (2-3), high (4+).
    """
    try:
        tree = parse_one(sql, read="sqlite")
    except SqlglotError:
        return "unparsed"
    score = (
        len(list(tree.find_all(exp.Join)))
        + 2 * (len(list(tree.find_all(exp.Select))) - 1)
        + 2 * len(list(tree.find_all(exp.Union, exp.Intersect, exp.Except)))
        + 2 * len(list(tree.find_all(exp.Window)))
        + (1 if tree.find(exp.Group) or tree.find(exp.AggFunc) else 0)
        + (1 if tree.find(exp.Case) else 0)
    )
    return "low" if score <= 1 else "medium" if score <= 3 else "high"


def matches_after_dropping_columns(gold: Rows, pred: Rows) -> bool:
    """True if some ordered subset of the predicted columns reproduces gold exactly."""
    if not gold or not pred or len(pred[0]) <= len(gold[0]):
        return False
    target = set(gold)
    candidates = itertools.permutations(range(len(pred[0])), len(gold[0]))
    for columns in itertools.islice(candidates, MAX_PROJECTION_TRIES):
        if {tuple(row[i] for i in columns) for row in pred} == target:
            return True
    return False


def strip_round(sql: str) -> str | None:
    """Replace every ROUND(x, n) with x; None when there is nothing to strip."""
    tree = parse_one(sql, read="sqlite")
    if tree.find(exp.Round) is None:
        return None
    rewritten: str = tree.transform(
        lambda node: node.this if isinstance(node, exp.Round) else node
    ).sql(dialect="sqlite")
    return rewritten


def split_concat(sql: str) -> str | None:
    """Split an outer projection ``a || ' ' || b`` into separate columns ``a, b``."""
    tree = parse_one(sql, read="sqlite")
    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        return None
    projections: list[exp.Expression] = []
    changed = False
    for projection in select.expressions:
        inner = projection.this if isinstance(projection, exp.Alias) else projection
        # Depth-first keeps the name parts in source order (first, then last).
        columns = (
            list(inner.find_all(exp.Column, bfs=False)) if isinstance(inner, exp.DPipe) else []
        )
        if len(columns) >= 2:
            projections.extend(columns)
            changed = True
        else:
            projections.append(projection)
    if not changed:
        return None
    select.set("expressions", projections)
    return tree.sql(dialect="sqlite")


def count_without_distinct(sql: str) -> str | None:
    """Rewrite COUNT(DISTINCT x) to COUNT(x); None when absent."""
    tree = parse_one(sql, read="sqlite")
    if not any(isinstance(node.this, exp.Distinct) for node in tree.find_all(exp.Count)):
        return None

    def rewrite(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Count) and isinstance(node.this, exp.Distinct):
            return exp.Count(this=node.this.expressions[0])
        return node

    return tree.transform(rewrite).sql(dialect="sqlite")


def delivered_sql(record: dict[str, Any]) -> str | None:
    """The SQL the agent actually returned to the user; rejected or failed queries don't count."""
    return record.get("sql") if record.get("error") is None else None


def bucket(record: dict[str, Any], gold: Rows | None, pred: Rows | None) -> str:
    """Classify one prediction by pipeline outcome and result shape."""
    if gold is not None and pred is not None and set(pred) == set(gold):
        return "correct"
    if record.get("response_type") not in (None, "query"):
        return f"answered-{record['response_type']}"
    if record.get("error_category"):
        return f"pipeline-{record['error_category']}"
    if pred is None:
        return "prediction-exec-error"
    if gold is None:
        return "gold-exec-error"
    if gold and not pred:
        return "empty-result"
    if gold and pred and len(gold[0]) != len(pred[0]):
        return "extra-columns" if len(pred[0]) > len(gold[0]) else "missing-columns"
    if len(set(gold)) != len(set(pred)):
        return "row-count-differs"
    return "values-differ"


def contract_fix(db_path: Path, sql: str, gold: Rows, pred: Rows) -> str | None:
    """Name the first presentational rewrite that makes a wrong prediction correct."""
    if matches_after_dropping_columns(gold, pred):
        return "drop-extra-columns"
    target = set(gold)
    for name, rewrite in (
        ("strip-round", strip_round),
        ("split-concat", split_concat),
        ("count-without-distinct", count_without_distinct),
    ):
        try:
            rewritten = rewrite(sql)
        except SqlglotError:
            continue
        if rewritten is None:
            continue
        rows = run_query(db_path, rewritten)
        if rows is not None and (
            set(rows) == target or matches_after_dropping_columns(gold, rows)
        ):
            return name
    return None


def rescore(
    raw_path: Path,
    questions: list[BirdQuestion],
    db_dir: Path,
    corrected_gold: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Official re-score per dataset row; optionally also against corrected gold SQL."""
    by_row = {question.row_index: question for question in questions}
    results = []
    for row, record in sorted(load_run(raw_path, questions).items()):
        question = by_row[row]
        db_path = db_path_for(question.db_id, db_dir=db_dir)
        gold = run_query(db_path, question.gold_sql)
        sql = delivered_sql(record)
        pred = run_query(db_path, sql) if sql else None
        kind = bucket(record, gold, pred)
        fix = None
        if kind in {"extra-columns", "missing-columns", "row-count-differs", "values-differ"}:
            assert gold is not None and pred is not None and sql is not None
            fix = contract_fix(db_path, sql, gold, pred)
        corrected: bool | None = None
        if corrected_gold is not None and question.question_id in corrected_gold:
            fixed_gold = run_query(db_path, corrected_gold[question.question_id])
            corrected = fixed_gold is not None and pred is not None and set(pred) == set(fixed_gold)
        results.append(
            {
                "row_index": row,
                "question_id": question.question_id,
                "db_id": question.db_id,
                "difficulty": question.difficulty,
                "official_ex": kind == "correct",
                "official_ex_corrected": corrected,
                "bucket": kind,
                # Oracle: found using the gold result, so an upper bound, not a live gain.
                "contract_fix_oracle": fix,
            }
        )
    return results


def _pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.1%}" if denominator else "—"


def macro_ex(by_db: dict[str, list[bool]]) -> str:
    """Accuracy averaged over databases, so one large database cannot dominate."""
    if not by_db:
        return "—"
    return f"{sum(sum(v) / len(v) for v in by_db.values()) / len(by_db):.1%}"


def rescore_report(raw_path: Path, results: list[dict[str, Any]]) -> str:
    total = len(results)
    correct = sum(r["official_ex"] for r in results)
    has_corrected = any(r["official_ex_corrected"] is not None for r in results)
    lines = [
        f"# Official re-score: `{raw_path.name}`",
        "",
        (
            "Scoring unit: dataset rows (duplicates included, as in BIRD's official "
            "evaluator). The last column is an **oracle ceiling**: presentational rewrites "
            "chosen using the gold result, so it bounds what output-contract work could "
            "recover; it is not a gain."
        ),
        "",
        "| Difficulty | N | Official EX |"
        + (" Corrected labels |" if has_corrected else "")
        + " Oracle contract ceiling |",
        "|---|---:|---:|" + ("---:|" if has_corrected else "") + "---:|",
    ]
    for label in (*DIFFICULTIES, "unknown", "overall"):
        rows = [r for r in results if label in ("overall", r["difficulty"])]
        if not rows:
            continue
        ok = sum(r["official_ex"] for r in rows)
        fixable = sum(bool(r["contract_fix_oracle"]) for r in rows)
        corrected_cell = ""
        if has_corrected:
            scored = [r for r in rows if r["official_ex_corrected"] is not None]
            corrected_cell = f" {_pct(sum(r['official_ex_corrected'] for r in scored), len(scored))} |"
        lines.append(
            f"| {label} | {len(rows)} | {_pct(ok, len(rows))} |{corrected_cell} "
            f"{_pct(ok + fixable, len(rows))} |"
        )
    lines += ["", "## Per database", "", "| db_id | N | Official EX |", "|---|---:|---:|"]
    by_db: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_db[r["db_id"]].append(r["official_ex"])
    for db_id, values in sorted(by_db.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        lines.append(f"| `{db_id}` | {len(values)} | {_pct(sum(values), len(values))} |")
    lines.append(f"| **macro (mean over databases)** | {len(by_db)} DBs | {macro_ex(by_db)} |")
    buckets = Counter(r["bucket"] for r in results if not r["official_ex"])
    lines += ["", f"## Failure buckets ({total - correct} failures)", ""]
    lines += [f"- {kind}: {count}" for kind, count in buckets.most_common()]
    fixes = Counter(r["contract_fix_oracle"] for r in results if r["contract_fix_oracle"])
    lines += ["", "## Oracle output-contract rewrites (first rewrite that matches gold)", ""]
    lines += [f"- {kind}: {count}" for kind, count in fixes.most_common()] or ["- none"]
    return "\n".join(lines) + "\n"


def mcnemar_exact_p(regressions: int, improvements: int) -> float:
    """Two-sided exact McNemar p-value over the discordant pairs."""
    n = regressions + improvements
    if n == 0:
        return 1.0
    k = min(regressions, improvements)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2.0 * float(tail))


def official_correct(record: dict[str, Any], question: BirdQuestion, db_dir: Path) -> bool:
    """Recorded official EX, or re-executed for runs that predate the ``official_ex`` field."""
    if "official_ex" in record:
        return bool(record["official_ex"])
    sql = delivered_sql(record)
    if not sql:
        return False
    db_path = db_path_for(question.db_id, db_dir=db_dir)
    gold, pred = run_query(db_path, question.gold_sql), run_query(db_path, sql)
    return gold is not None and pred is not None and set(pred) == set(gold)


# Metadata field groups a comparison may be *declared* to vary (``flips --allow``).
META_GROUPS = {
    "data": ("dataset_sha256_16",),
    "databases": ("database_sha256_16",),
    "prompt": ("effective_prompt_sha256_16",),
    "config": ("config_sha256_16",),
    "code": ("git_commit", "code_state_sha256_16"),
}


def load_meta(raw_path: Path) -> dict[str, Any] | None:
    meta = raw_path.with_name(raw_path.name.replace("bird_raw_", "bird_meta_")).with_suffix(
        ".json"
    )
    return json.loads(meta.read_text()) if meta.exists() else None


def comparability(
    old_meta: dict[str, Any] | None, new_meta: dict[str, Any] | None
) -> tuple[set[str], list[str]]:
    """Return (differing field groups, report lines) between two runs' metadata."""
    if old_meta is None or new_meta is None:
        return set(), ["- ⚠️ a run has no meta sidecar (pre-v2.3); comparability unchecked."]
    differing: set[str] = set()
    lines = []
    for group, fields in META_GROUPS.items():
        for field in fields:
            old, new = old_meta.get(field), new_meta.get(field)
            if group == "databases" and isinstance(old, dict) and isinstance(new, dict):
                shared = set(old) & set(new)
                old = {db: old[db] for db in shared}
                new = {db: new[db] for db in shared}
            if old != new:
                differing.add(group)
                lines.append(f"- `{group}` differs (`{field}`)")
    return differing, lines or ["- identical data, databases, prompt, config, and code"]


def _bootstrap(
    deltas: dict[str, list[float]], iterations: int, seed: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """95% CIs for (row-weighted, database-macro) mean deltas, resampling questions
    with replacement *within* each database; a question's repeats stay together because
    each delta is already that question's mean over repeats."""
    rng = random.Random(seed)
    rows_total = sum(len(values) for values in deltas.values())
    row_stats, macro_stats = [], []
    for _ in range(iterations):
        db_means, row_sum = [], 0.0
        for values in deltas.values():
            sample = [values[rng.randrange(len(values))] for _ in values]
            row_sum += sum(sample)
            db_means.append(sum(sample) / len(sample))
        row_stats.append(row_sum / rows_total)
        macro_stats.append(sum(db_means) / len(db_means))

    def interval(stats: list[float]) -> tuple[float, float]:
        ordered = sorted(stats)
        return ordered[int(0.025 * iterations)], ordered[int(0.975 * iterations) - 1]

    return interval(row_stats), interval(macro_stats)


def _flip_rows(
    label: str, rows: list[int], was: dict[int, float], now: dict[int, float]
) -> str:
    regressions = sum(now[r] < was[r] for r in rows)
    fixes = sum(now[r] > was[r] for r in rows)
    delta = sum(now[r] - was[r] for r in rows) / len(rows)
    return (
        f"| {label} | {len(rows)} | {_pct(round(sum(was[r] for r in rows)), len(rows))} | "
        f"{_pct(round(sum(now[r] for r in rows)), len(rows))} | {delta * 100:+.1f} | "
        f"{regressions} | {fixes} | {mcnemar_exact_p(regressions, fixes):.3f} |"
    )


FULL_COMPARISON_REPEATS = 2
# Acceptance minimum (docs/SOTA_PLAN.md §5.4): base gain, plus 1 pt per +50% cost and per
# +1s P50. Cost is compared at *uncached-equivalent* prices: measured $/query moves with the
# provider's prompt-cache state (46% vs 23% hits across two identical-prefix runs), which is
# not a property of the change under test.
DEFAULT_MIN_GAIN_PTS = 1.5


def cost_latency(runs: dict[int, list[dict[str, Any]]]) -> tuple[float, float, float]:
    """(measured $/answer, uncached-equivalent $/answer, P50 seconds) over all repeats."""
    records = [record for rows in runs.values() for record in rows]
    calls = [call for record in records for call in record.get("llm_calls", [])]
    measured = sum(float(call["cost_usd"]) for call in calls) / len(records)
    uncached = (
        sum(
            cost_usd(call["model"], int(call["input_tokens"]), 0, int(call["output_tokens"]))
            for call in calls
        )
        / len(records)
    )
    latencies = sorted(float(record.get("t_total_ms", 0.0)) for record in records)
    return measured, uncached, latencies[len(latencies) // 2] / 1_000


def required_gain(
    base_min: float, old: tuple[float, float, float], new: tuple[float, float, float]
) -> float:
    """Declared minimum gain in points, raised for added (uncached) cost and P50 latency."""
    cost_increase = max(0.0, new[1] / old[1] - 1.0) if old[1] else 0.0
    latency_increase = max(0.0, new[2] - old[2])
    return base_min + cost_increase / 0.5 + latency_increase


def check_full_comparison(
    old_meta: dict[str, Any] | None,
    new_meta: dict[str, Any] | None,
    old: dict[int, list[dict[str, Any]]],
    new: dict[int, list[dict[str, Any]]],
    repeats: int = FULL_COMPARISON_REPEATS,
) -> None:
    """Refuse a full (acceptance) comparison unless both runs are complete and identical in
    coverage: the same expected rows, each present with exactly ``repeats`` repeats.

    Without this, a variant cut short by a budget stop is scored only on the rows it
    reached; one lucky row reads as +100 points with a [100, 100] interval.
    """
    problems = []
    for label, meta, runs in (("old", old_meta, old), ("new", new_meta, new)):
        if meta is None or "expected_rows" not in meta:
            problems.append(f"{label} run has no expected-row metadata (predates v2.3)")
            continue
        if not meta.get("complete"):
            problems.append(f"{label} run is incomplete (budget stop or missing results)")
        expected = set(meta["expected_rows"])
        missing = expected - set(runs)
        if missing:
            problems.append(f"{label} run lacks {len(missing)} expected rows")
        wrong = [
            row
            for row in expected & set(runs)
            if sorted(int(r.get("repeat", 0)) for r in runs[row]) != list(range(repeats))
        ]
        if wrong:
            problems.append(f"{label} run has {len(wrong)} rows without exactly {repeats} repeats")
    if old_meta and new_meta and old_meta.get("expected_rows") != new_meta.get("expected_rows"):
        problems.append("the runs expected different question rows")
    if problems:
        raise SystemExit(
            "Not a valid full comparison: "
            + "; ".join(problems)
            + ". Use --pilot for an explicitly partial (non-acceptance) comparison."
        )


def flips_report(
    old_path: Path,
    new_path: Path,
    questions: list[BirdQuestion],
    db_dir: Path,
    *,
    allow: set[str] | None = None,
    force: bool = False,
    pilot: bool = False,
    min_gain: float = DEFAULT_MIN_GAIN_PTS,
    iterations: int = 2_000,
    seed: int = 0,
) -> str:
    """Paired comparison per §5 of docs/SOTA_PLAN.md (acceptance evidence, not a verdict).

    Full mode (default) requires complete runs with identical expected rows and exactly
    two repeats per question. ``pilot=True`` compares whatever rows overlap and labels the
    result as pilot evidence only.
    """
    old_meta, new_meta = load_meta(old_path), load_meta(new_path)
    differing, meta_lines = comparability(old_meta, new_meta)
    undeclared = differing - (allow or set())
    if undeclared and not force:
        raise SystemExit(
            "Runs differ in undeclared ways: "
            + ", ".join(sorted(undeclared))
            + ". Pass --allow for the variable under test (or --force)."
        )
    by_row = {question.row_index: question for question in questions}
    old, new = load_runs(old_path, questions), load_runs(new_path, questions)
    if not pilot:
        check_full_comparison(old_meta, new_meta, old, new)
    shared = sorted(set(old) & set(new))
    if not shared:
        raise SystemExit("The runs share no question rows.")

    def score(runs: list[dict[str, Any]], row: int) -> float:
        return sum(official_correct(r, by_row[row], db_dir) for r in runs) / len(runs)

    was = {r: score(old[r], r) for r in shared}
    now = {r: score(new[r], r) for r in shared}
    per_db: dict[str, list[float]] = defaultdict(list)
    for r in shared:
        per_db[by_row[r].db_id].append(now[r] - was[r])
    row_delta = sum(now[r] - was[r] for r in shared) / len(shared)
    macro_delta = sum(sum(v) / len(v) for v in per_db.values()) / len(per_db)
    row_ci, macro_ci = _bootstrap(per_db, iterations, seed)
    old_cost = cost_latency({r: old[r] for r in shared})
    new_cost = cost_latency({r: new[r] for r in shared})
    minimum = required_gain(min_gain, old_cost, new_cost)
    repeats = (
        max(len(runs) for runs in old.values()),
        max(len(runs) for runs in new.values()),
    )
    header = "| {} | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |"
    rule = "|---|---:|---:|---:|---:|---:|---:|---:|"
    lines = [
        f"# Paired comparison: `{old_path.name}` → `{new_path.name}`",
        "",
        "## Comparability",
        "",
        *meta_lines,
        (
            f"- undeclared differences overridden with --force: {sorted(undeclared)}"
            if undeclared
            else f"- declared variable(s): {sorted(allow or set()) or 'none'}"
        ),
        "",
        (
            "## ⚠️ PILOT comparison: partial overlap allowed, NOT acceptance evidence"
            if pilot
            else "## Acceptance evidence (official EX): full comparison, coverage verified"
        ),
        "",
        (
            f"{len(shared)} shared questions; repeats old/new = {repeats[0]}/{repeats[1]} "
            "(each question scored as its mean over repeats). CIs: 95% bootstrap resampling "
            f"questions within each database ({iterations} draws)."
        ),
        "",
        "| Metric | Δ pts | 95% CI |",
        "|---|---:|---|",
        (
            f"| Row-weighted | {row_delta * 100:+.2f} | "
            f"[{row_ci[0] * 100:+.2f}, {row_ci[1] * 100:+.2f}] |"
        ),
        (
            f"| Database macro | {macro_delta * 100:+.2f} | "
            f"[{macro_ci[0] * 100:+.2f}, {macro_ci[1] * 100:+.2f}] |"
        ),
        "",
        "| Run | $/answer measured | $/answer uncached-equivalent | P50 (s) |",
        "|---|---:|---:|---:|",
        f"| old | {old_cost[0]:.6f} | {old_cost[1]:.6f} | {old_cost[2]:.2f} |",
        f"| new | {new_cost[0]:.6f} | {new_cost[1]:.6f} | {new_cost[2]:.2f} |",
        "",
        (
            f"**Required minimum: {minimum:+.2f} pts** (base {min_gain:+.2f}, plus 1 pt per "
            "+50% uncached cost and per +1s P50). Meets it: row-weighted "
            f"**{'yes' if row_delta * 100 >= minimum and row_ci[0] > 0 else 'no'}**, "
            f"macro **{'yes' if macro_delta * 100 >= minimum and macro_ci[0] > 0 else 'no'}**"
            " (point estimate ≥ minimum and CI lower bound > 0)."
        ),
        (
            "Audit required: a CI lower bound is within 1 pt of 0."
            if min(row_ci[0], macro_ci[0]) * 100 < 1.0
            else "No borderline audit required."
        ),
        "Subgroup tables below are for investigating regressions, not for voting.",
        "",
        header.format("Database"),
        rule,
    ]
    for db_id in sorted(per_db):
        rows = [r for r in shared if by_row[r].db_id == db_id]
        lines.append(_flip_rows(f"`{db_id}`", rows, was, now))
    difficulties = sorted({by_row[r].difficulty for r in shared})
    if difficulties != ["unknown"]:
        lines += ["", header.format("Difficulty"), rule]
        for label in difficulties:
            rows = [r for r in shared if by_row[r].difficulty == label]
            lines.append(_flip_rows(label, rows, was, now))
    lines += ["", header.format("Gold-SQL complexity"), rule]
    bands: dict[str, list[int]] = defaultdict(list)
    for r in shared:
        bands[sql_complexity(by_row[r].gold_sql)].append(r)
    for band in ("low", "medium", "high", "unparsed"):
        if bands.get(band):
            lines.append(_flip_rows(band, bands[band], was, now))
    consistent = [r for r in shared if abs(now[r] - was[r]) == 1.0]
    lines += [
        "",
        "## Flips to audit against gold",
        "",
        (
            "Questions that flipped in every repeat. Gold labels are noisy, so read these "
            "before trusting a borderline result:"
        ),
        "",
    ]
    lines += [
        f"- {'fix' if now[r] > was[r] else 'REGRESSION'}: `{by_row[r].db_id}` "
        f"question {by_row[r].question_id} (row {r})"
        for r in consistent
    ] or ["- none"]
    return "\n".join(lines) + "\n"


def _majority_correct(sample: list[dict[str, Any]]) -> bool:
    """Majority vote over delivered answers by full-result signature (ties: earliest wins)."""
    votes: dict[str, list[dict[str, Any]]] = {}
    for record in sample:
        signature = record.get("result_signature")
        if record.get("error") is None and signature:
            votes.setdefault(signature, []).append(record)
    if not votes:
        return False
    winner = max(votes.values(), key=len)  # dict order = first appearance, so ties -> earliest
    return bool(winner[0].get("official_ex"))


def sample_curves(
    runs: dict[int, list[dict[str, Any]]], max_k: int
) -> dict[int, tuple[float, float]]:
    """k -> (oracle pass@k, majority@k), each averaged over all k-subsets of a question's
    samples, so the result doesn't depend on sample order."""
    curves: dict[int, tuple[float, float]] = {}
    for k in range(1, max_k + 1):
        passes, majorities = [], []
        for samples in runs.values():
            subsets = list(itertools.combinations(samples, k))
            passes.append(
                sum(any(r.get("official_ex") for r in subset) for subset in subsets)
                / len(subsets)
            )
            majorities.append(sum(_majority_correct(list(subset)) for subset in subsets) / len(subsets))
        curves[k] = (sum(passes) / len(passes), sum(majorities) / len(majorities))
    return curves


def samples_report(raw_path: Path, questions: list[BirdQuestion]) -> str:
    """Oracle pass@k vs majority@k from a run whose repeats are independent samples
    (temperature > 0): the Phase 4 bottleneck test. A large pass@k − majority@k gap means
    selection is the bottleneck; a low pass@k means generation is."""
    runs = load_runs(raw_path, questions)
    max_k = min(len(samples) for samples in runs.values())
    by_row = {question.row_index: question for question in questions}
    lines = [
        f"# Sample curves: `{raw_path.name}`",
        "",
        f"{len(runs)} questions × {max_k} samples; averaged over all k-subsets.",
        "",
        "| k | Oracle pass@k | Majority@k | Gap (selection headroom) |",
        "|---:|---:|---:|---:|",
    ]
    for k, (passes, majority) in sample_curves(runs, max_k).items():
        lines.append(f"| {k} | {passes:.1%} | {majority:.1%} | {(passes - majority) * 100:+.1f} pts |")
    lines += ["", f"| Database | N | pass@1 | pass@{max_k} | majority@{max_k} |", "|---|---:|---:|---:|---:|"]
    for db_id in sorted({by_row[r].db_id for r in runs}):
        subset = {r: v for r, v in runs.items() if by_row[r].db_id == db_id}
        curve = sample_curves(subset, max_k)
        lines.append(
            f"| `{db_id}` | {len(subset)} | {curve[1][0]:.1%} | {curve[max_k][0]:.1%} | "
            f"{curve[max_k][1]:.1%} |"
        )
    return "\n".join(lines) + "\n"


def load_corrected_gold(path: Path) -> dict[int, str]:
    """Corrected gold SQL keyed by question id (e.g. Arcwise-Plat-SQL)."""
    return {int(item["question_id"]): item["SQL"] for item in json.loads(path.read_text())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    rescore_cmd = commands.add_parser("rescore", help="Official re-score + failure analysis")
    rescore_cmd.add_argument("raw", type=Path)
    rescore_cmd.add_argument(
        "--corrected-gold", type=Path, help="Also score against corrected gold SQL (Arcwise)."
    )
    flips_cmd = commands.add_parser("flips", help="Paired flip matrix between two runs")
    flips_cmd.add_argument("old", type=Path)
    flips_cmd.add_argument("new", type=Path)
    flips_cmd.add_argument(
        "--allow",
        nargs="+",
        default=[],
        choices=sorted(META_GROUPS),
        help="Metadata groups the comparison is declared to vary (the variable under test).",
    )
    flips_cmd.add_argument("--force", action="store_true", help="Compare despite differences.")
    flips_cmd.add_argument(
        "--min-gain",
        type=float,
        default=DEFAULT_MIN_GAIN_PTS,
        help="Declared base minimum gain in points, before cost/latency adjustment.",
    )
    flips_cmd.add_argument(
        "--pilot",
        action="store_true",
        help="Allow partial overlap / unequal repeats; the report is labeled non-acceptance.",
    )
    samples_cmd = commands.add_parser(
        "samples", help="Oracle pass@k vs majority@k from a multi-sample run"
    )
    samples_cmd.add_argument("raw", type=Path)
    args = parser.parse_args()

    questions = load_questions(args.questions)
    if args.command == "samples":
        print(samples_report(args.raw, questions))
        return
    if args.command == "rescore":
        corrected = load_corrected_gold(args.corrected_gold) if args.corrected_gold else None
        results = rescore(args.raw, questions, args.db_dir, corrected)
        output = args.raw.with_name(f"analysis_{args.raw.stem}.json")
        output.write_text(json.dumps(results, indent=1) + "\n")
        print(rescore_report(args.raw, results))
        print(f"Per-row results: {output}")
    else:
        print(
            flips_report(
                args.old,
                args.new,
                questions,
                args.db_dir,
                allow=set(args.allow),
                force=args.force,
                pilot=args.pilot,
                min_gain=args.min_gain,
            )
        )


if __name__ == "__main__":
    main()
