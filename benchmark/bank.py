"""Candidate-bank diagnostics (SOTA plan rank 4): how much could selection add?

Each input run contributes one candidate per question (its first repeat). Every candidate's
delivered SQL is **re-executed locally** through ``execute_candidate`` so all result
signatures come from the same code (the 2026-09-26 signature normalisation), then:

- **per-candidate EX** (official, as stored by the run);
- **oracle pass@k** over every k-subset of candidates: the ceiling a perfect selector gets;
- **majority vote** by result signature (ties: the first-listed candidate wins);
- **consensus**: how often all candidates agree, and how often they agree on a wrong answer
  (the part of the gap no selector can close).

Gold is used only through each run's stored official EX, never for selection.

    python -m benchmark.bank --questions data/bird/splits/train_dev.json \\
        --db-dir data/bird/train/train_databases direct=RUN.jsonl decompose=RUN.jsonl ...
"""

from __future__ import annotations

import argparse
import itertools
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark.analyze import delivered_sql, load_run, macro_ex
from benchmark.bird import BirdQuestion, db_path_for, load_questions
from src.db import connect_readonly, execute_candidate, timeout_for_database

Candidate = tuple[str | None, bool]  # (result signature or None if no result, correct)


def majority_correct(candidates: list[Candidate]) -> bool:
    """Most common signature among candidates that produced a result; ties go to the
    earliest-listed candidate. No result at all counts as wrong."""
    votes = Counter(sig for sig, _ in candidates if sig is not None)
    if not votes:
        return False
    best = max(votes.values())
    for sig, correct in candidates:
        if sig is not None and votes[sig] == best:
            return correct
    return False


def pass_at_k(candidates: list[Candidate], k: int) -> float:
    """Share of k-subsets containing at least one correct candidate."""
    subsets = list(itertools.combinations(candidates, k))
    return sum(any(ok for _, ok in subset) for subset in subsets) / len(subsets)


def rescore_signatures(
    runs: dict[str, dict[int, dict[str, Any]]], by_row: dict[int, BirdQuestion], db_dir: Path
) -> dict[str, dict[int, str | None]]:
    """Fresh signatures for every delivered candidate, executed locally, one DB at a time."""
    out: dict[str, dict[int, str | None]] = defaultdict(dict)
    rows_by_db: dict[str, list[int]] = defaultdict(list)
    for row in sorted(set.intersection(*(set(r) for r in runs.values()))):
        rows_by_db[by_row[row].db_id].append(row)
    for db_id, rows in rows_by_db.items():
        path = db_path_for(db_id, db_dir=db_dir)
        conn = connect_readonly(path, timeout_seconds=timeout_for_database(path, default=30.0))
        try:
            for label, run in runs.items():
                for row in rows:
                    sql = delivered_sql(run[row])
                    out[label][row] = (
                        execute_candidate(conn, sql, db_path=path).signature if sql else None
                    )
        finally:
            conn.close()
    return out


def report(
    runs: dict[str, dict[int, dict[str, Any]]], by_row: dict[int, BirdQuestion], db_dir: Path
) -> str:
    labels = list(runs)
    signatures = rescore_signatures(runs, by_row, db_dir)
    rows = sorted(signatures[labels[0]])
    bank = {
        row: [(signatures[label][row], bool(runs[label][row].get("official_ex"))) for label in labels]
        for row in rows
    }
    by_db: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    lines = [f"# Candidate bank: {len(rows)} questions, candidates {', '.join(labels)}", ""]
    lines += ["| Candidate | EX | Macro |", "|---|---:|---:|"]
    for index, label in enumerate(labels):
        per_db: dict[str, list[bool]] = defaultdict(list)
        for row in rows:
            per_db[by_row[row].db_id].append(bank[row][index][1])
        ok = sum(bank[row][index][1] for row in rows)
        lines.append(f"| `{label}` | {ok / len(rows):.1%} | {macro_ex(per_db)} |")
    lines += ["", "| Selector over the bank | EX | Macro |", "|---|---:|---:|"]
    policies = {
        f"oracle pass@{len(labels)} (perfect selector)": lambda c: any(ok for _, ok in c),
        "majority vote by result": majority_correct,
    }
    for name, policy in policies.items():
        for row in rows:
            by_db[name][by_row[row].db_id].append(policy(bank[row]))
        total = sum(sum(v) for v in by_db[name].values())
        lines.append(f"| {name} | {total / len(rows):.1%} | {macro_ex(by_db[name])} |")
    lines += ["", "| k | mean oracle pass@k over subsets |", "|---:|---:|"]
    for k in range(1, len(labels) + 1):
        lines.append(f"| {k} | {sum(pass_at_k(bank[r], k) for r in rows) / len(rows):.1%} |")
    unanimous = [r for r in rows if len({s for s, _ in bank[r]}) == 1 and bank[r][0][0]]
    unanimous_wrong = [r for r in unanimous if not bank[r][0][1]]
    never = [r for r in rows if not any(ok for _, ok in bank[r])]
    lines += [
        "",
        (
            f"- All candidates return the same result on {len(unanimous)} questions "
            f"({len(unanimous) / len(rows):.1%}); **{len(unanimous_wrong)} of those are "
            f"wrong** ({len(unanimous_wrong) / len(rows):.1%} of all): no selector can fix them."
        ),
        f"- No candidate is correct on {len(never)} questions ({len(never) / len(rows):.1%}).",
        (
            f"- Disagreement (≥ 2 distinct results) on {len(rows) - len(unanimous)} "
            "questions: the only place a selector acts."
        ),
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, required=True)
    parser.add_argument("runs", nargs="+", help="label=path/to/bird_raw_*.jsonl, in tie order")
    args = parser.parse_args()
    questions = load_questions(args.questions)
    by_row = {q.row_index: q for q in questions}
    runs = {}
    for spec in args.runs:
        label, _, path = spec.partition("=")
        runs[label] = load_run(Path(path), questions)
    print(report(runs, by_row, args.db_dir))


if __name__ == "__main__":
    main()
