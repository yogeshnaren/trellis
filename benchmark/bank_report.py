"""Fresh candidate bank report (P03/P16): coverage per route, under official and corrected keys.

Routes are saved runs on the same question file. Every candidate is re-executed locally so
signatures come from one code state. Correctness is judged two ways:

- **official**: the run's recorded official EX (BIRD's key);
- **corrected**: adjudicated labels (P02/P38). Sound keys keep the official result; defective
  keys are replaced by the reviewer's executed corrected SQL; ambiguous keys accept the
  official result or any listed alternative; unresolved keys are excluded from this view.

Reports per-route EX, marginal coverage over the incumbent route, the repeat control,
oracle coverage of *fixed* route sets (the deployable policy, not a subset average),
result-majority voting and correct additions per dollar. No model calls.

    uv run python -m benchmark.bank_report --questions data/bird/splits/train_dev2_bank.json \\
        --db-dir data/bird/train/train_databases --labels labels.json \\
        --label-rows data/bird/splits/train_dev2_bank_rows.json \\
        direct=RUN direct_repeat=RUN:1 gptoss=RUN qwen=RUN arctic=RUN
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark.analyze import _bootstrap, answer_uncached_cost, delivered_sql, load_runs
from benchmark.bank import majority_correct
from benchmark.bird import db_path_for, load_questions
from benchmark.sql_checks import check_sql
from src.db import connect_readonly, execute_candidate, timeout_for_database

RESULTS = Path("benchmark/results")
# Selection rules fixed on 2026-09-29 BEFORE any bank result was seen (Experiment C). Only
# independent families vote; repeats of the incumbent never count as agreement.
POLICIES = ("S0 incumbent", "S1 family majority", "S2 fallback on empty/error",
            "S3 detector switch", "S4 other families agree")
TRUSTED_DETECTORS = {"ranked_extra_column", "lossy_cast", "text_number"}


def load_route(spec: str, questions: list[Any]) -> tuple[str, dict[int, dict[str, Any]]]:
    """``label=RUN`` (first repeat) or ``label=RUN:k`` (repeat k)."""
    label, _, ref = spec.partition("=")
    run, _, rep = ref.partition(":")
    runs = load_runs(RESULTS / f"bird_raw_{run}.jsonl", questions)
    k = int(rep or 0)
    return label, {row: recs[k] for row, recs in runs.items() if len(recs) > k}


def reference_signatures(questions: list[Any], db_dir: Path, labels: dict[str, Any],
                         label_rows: list[int], prefix: str = "train_dev2") -> dict[int, set[str] | None]:
    """Accepted result signatures per bank row under corrected keys (None = excluded)."""
    out: dict[int, set[str] | None] = {}
    for q in questions:
        entry = labels.get(f"{prefix}:{label_rows[q.row_index]}")
        path = db_path_for(q.db_id, db_dir=db_dir)
        conn = connect_readonly(path, timeout_seconds=timeout_for_database(path, default=30.0))
        try:
            def sig(sql: str | None) -> str | None:
                if not sql:
                    return None
                res = execute_candidate(conn, sql, db_path=path)
                return res.signature if res.ok else None

            if entry is None or entry.get("status") == "disputed" or entry.get("label") == "uncertain":
                out[q.row_index] = None
            elif entry["label"] == "sound":
                out[q.row_index] = {s for s in [sig(q.gold_sql)] if s}
            elif entry["label"] == "defect":
                s = sig(entry.get("corrected_sql"))
                out[q.row_index] = {s} if s else None
            else:  # ambiguous: official or any executed alternative
                alts = [a.get("sql") if isinstance(a, dict) else a for a in entry.get("alternatives") or []]
                out[q.row_index] = {s for s in [sig(q.gold_sql), *map(sig, alts)] if s}
        finally:
            conn.close()
    return out


def candidate_signatures(routes: dict[str, dict[int, dict[str, Any]]], questions: list[Any],
                         db_dir: Path) -> dict[str, dict[int, str | None]]:
    by_row = {q.row_index: q for q in questions}
    out: dict[str, dict[int, str | None]] = {label: {} for label in routes}
    for label, recs in routes.items():
        for row, rec in recs.items():
            sql = delivered_sql(rec)
            q = by_row[row]
            if not sql:
                out[label][row] = None
                continue
            path = db_path_for(q.db_id, db_dir=db_dir)
            conn = connect_readonly(path, timeout_seconds=timeout_for_database(path, default=30.0))
            try:
                res = execute_candidate(conn, sql, db_path=path)
                out[label][row] = res.signature if res.ok else None
            finally:
                conn.close()
    return out


def report(args: argparse.Namespace) -> str:
    questions = load_questions(args.questions)
    routes = dict(load_route(spec, questions) for spec in args.routes)
    labels = json.loads(Path(args.labels).read_text()) if args.labels else {}
    label_rows = json.loads(Path(args.label_rows).read_text())["source_rows"] if args.label_rows else []
    rows = sorted(set.intersection(*(set(r) for r in routes.values())))
    sigs = candidate_signatures(routes, questions, Path(args.db_dir))
    refs = reference_signatures([q for q in questions if q.row_index in rows], Path(args.db_dir),
                                labels, label_rows, args.label_prefix) if labels else {}
    names = list(routes)
    incumbent = names[0]

    def ok(label: str, row: int, view: str) -> bool | None:
        if view == "official":
            return bool(routes[label][row].get("official_ex"))
        ref = refs.get(row)
        if ref is None:
            return None
        return sigs[label][row] in ref

    lines = [f"# Candidate bank on {len(rows)} questions ({Path(args.questions).name})", ""]
    views = ["official"] + (["corrected"] if labels else [])
    for view in views:
        scored = [r for r in rows if all(ok(n, r, view) is not None for n in names)]
        lines += [f"## {view.title()} keys ({len(scored)} questions scored)", "",
                  "| Route | EX | Adds over incumbent | $ / answer (uncached) |", "|---|---:|---:|---:|"]
        base = {r for r in scored if ok(incumbent, r, view)}
        for n in names:
            correct = {r for r in scored if ok(n, r, view)}
            cost = sum(answer_uncached_cost(routes[n][r]) for r in scored) / len(scored)
            lines.append(f"| `{n}` | {len(correct) / len(scored):.1%} ({len(correct)}) | "
                         f"{len(correct - base) if n != incumbent else '—'} | {cost:.5f} |")
        lines += ["", "| Fixed route set | Oracle coverage | Majority vote | $ / question |", "|---|---:|---:|---:|"]
        for k in range(1, len(names) + 1):
            for combo in itertools.combinations(names, k):
                if incumbent not in combo:
                    continue
                cover = sum(any(ok(n, r, view) for n in combo) for r in scored)
                vote = sum(majority_correct([(sigs[n][r], bool(ok(n, r, view))) for n in combo]) for r in scored)
                cost = sum(answer_uncached_cost(routes[n][r]) for n in combo for r in scored) / len(scored)
                lines.append(f"| {' + '.join(combo)} | {cover / len(scored):.1%} | {vote / len(scored):.1%} | {cost:.5f} |")
        lines.append("")
    families = [n for n in names if not n.endswith("_repeat")]
    by_row = {q.row_index: q for q in questions}
    flags = {n: {r: set(check_sql(delivered_sql(routes[n][r]) or "", db_path_for(by_row[r].db_id, db_dir=Path(args.db_dir))))
                 if delivered_sql(routes[n][r]) else set() for r in rows} for n in families}

    def empty(n: str, r: int) -> bool:
        return sigs[n][r] is None or int(routes[n][r].get("result_row_count") or 0) == 0

    def choose(policy: str, r: int) -> str:
        inc = incumbent
        others = [n for n in families if n != inc]
        if policy.startswith("S1"):
            votes = Counter(sigs[n][r] for n in families if sigs[n][r] and not empty(n, r))
            if votes:
                best = max(votes.values())
                winners = [s for s, v in votes.items() if v == best]
                if sigs[inc][r] in winners:
                    return inc
                return next(n for n in others if sigs[n][r] == winners[0])
            return inc
        if policy.startswith("S2"):
            if empty(inc, r):
                return next((n for n in others if not empty(n, r)), inc)
            return inc
        if policy.startswith("S3"):
            if flags[inc][r] & TRUSTED_DETECTORS:
                return next((n for n in others if not empty(n, r) and not flags[n][r] & TRUSTED_DETECTORS), inc)
            return inc
        if policy.startswith("S4"):
            other_sigs = {sigs[n][r] for n in others}
            if len(others) >= 2 and len(other_sigs) == 1 and None not in other_sigs \
                    and not any(empty(n, r) for n in others) and sigs[inc][r] not in other_sigs:
                return others[0]
            return inc
        return inc

    lines += ["## Pre-registered selection rules (Experiment C)", "",
              "| Rule | Official EX | Corrected EX | Corrected Δ, 95% CI | Switched away from incumbent | Switches: fix / break (corrected) |",
              "|---|---:|---:|---:|---:|---:|"]
    corr_rows = [r for r in rows if all(ok(n, r, "corrected") is not None for n in names)] if labels else []
    for policy in POLICIES:
        picks = {r: choose(policy, r) for r in rows}
        off = sum(bool(ok(picks[r], r, "official")) for r in rows) / len(rows)
        cor = (sum(bool(ok(picks[r], r, "corrected")) for r in corr_rows) / len(corr_rows)) if corr_rows else None
        switched = [r for r in rows if picks[r] != incumbent]
        fix = sum(1 for r in switched if r in corr_rows and ok(picks[r], r, "corrected") and not ok(incumbent, r, "corrected"))
        brk = sum(1 for r in switched if r in corr_rows and not ok(picks[r], r, "corrected") and ok(incumbent, r, "corrected"))
        deltas: dict[str, list[float]] = {}
        for r in corr_rows:
            deltas.setdefault(by_row[r].db_id, []).append(
                float(bool(ok(picks[r], r, "corrected"))) - float(bool(ok(incumbent, r, "corrected"))))
        ci = "—"
        if deltas and policy[:2] != "S0":
            (lo, hi), _ = _bootstrap(deltas, 2000, 0)
            ci = f"[{lo * 100:+.1f}, {hi * 100:+.1f}]"
        lines.append(f"| {policy} | {off:.1%} | {'—' if cor is None else f'{cor:.1%}'} | {ci} | {len(switched)} | {fix} / {brk} |")
    lines.append("")
    agree = Counter(len({sigs[n][r] for n in names if sigs[n][r]}) for r in rows)
    lines += ["## Diversity", "", "Distinct non-empty result signatures per question: "
              + ", ".join(f"{k}: {v}" for k, v in sorted(agree.items())), ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, help="adjudicated labels keyed train_dev2:<row>")
    parser.add_argument("--label-rows", type=Path, help="bank row → source row mapping")
    parser.add_argument("--label-prefix", default="train_dev2", help="label id prefix, e.g. train_design")
    parser.add_argument("routes", nargs="+", help="label=RUN or label=RUN:repeat; first is the incumbent")
    args = parser.parse_args()
    print(report(args))


if __name__ == "__main__":
    main()
