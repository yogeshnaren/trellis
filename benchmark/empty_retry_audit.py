"""Rescue vs damage of the empty-result retry (P08), measured offline from saved runs.

For every answer where the retry fired, the original SQL (before the retry) is recovered
from the saved model calls and re-scored against the answer key alongside the delivered
SQL. Net effect follows  Δ = t × [h × r − (1 − h) × d]  where t is the trigger rate,
h the share of triggers whose original answer was wrong, r the rescue rate among those,
and d the damage rate among triggers whose (empty) original was correct.

No model calls. Evaluation sets are reported as aggregates only.

    uv run python -m benchmark.empty_retry_audit RUN_ID [RUN_ID ...]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from benchmark.analyze import load_runs, run_query
from benchmark.bird import db_path_for, load_questions

RESULTS = Path("benchmark/results")


def call_sql(call: dict[str, Any]) -> str | None:
    try:
        sql = json.loads(call["text"]).get("sql")
        return str(sql) if sql else None
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None


def literal_only_change(original: str | None, delivered: str | None) -> bool | None:
    """True when the two queries differ only in literal values (case, spelling, numbers):
    same tables, columns, joins, predicates and shape. None when either fails to parse."""
    if not original or not delivered:
        return None

    def skeleton(sql: str) -> str:
        tree = parse_one(sql, read="sqlite")
        for lit in list(tree.find_all(exp.Literal)):
            lit.replace(exp.Literal.string("?"))
        return tree.sql(dialect="sqlite").casefold()

    try:
        return skeleton(original) == skeleton(delivered)
    except (SqlglotError, ValueError):
        return None


def audit_run(run: str, *, list_cases: bool) -> dict[str, Any]:
    meta = json.loads((RESULTS / f"bird_meta_{run}.json").read_text())
    questions = load_questions(meta["questions"])
    by_row = {q.row_index: q for q in questions}
    runs = load_runs(RESULTS / f"bird_raw_{run}.jsonl", questions)
    db_dir = Path(meta["db_dir"])
    answers = sum(len(v) for v in runs.values())
    counts: Counter[str] = Counter()
    cases = []
    for row, records in runs.items():
        q = by_row[row]
        db_path = db_path_for(q.db_id, db_dir=db_dir)
        gold = None
        for rec in records:
            if not rec.get("empty_retried"):
                continue
            calls = rec.get("llm_calls") or []
            if len(calls) < 2:
                counts["unrecoverable"] += 1
                continue
            original, retry = call_sql(calls[-2]), call_sql(calls[-1])
            if gold is None:
                gold = run_query(db_path, q.gold_sql)
            orig_rows = run_query(db_path, original) if original else None
            orig_ok = gold is not None and orig_rows is not None and set(orig_rows) == set(gold)
            final_ok = bool(rec.get("official_ex"))
            replaced = rec.get("sql") != original
            counts["triggers"] += 1
            counts["replaced" if replaced else "kept"] += 1
            counts["orig_correct" if orig_ok else "orig_wrong"] += 1
            if replaced:
                kind = {True: "literal_only", False: "structural", None: "unparsed"}[
                    literal_only_change(original, rec.get("sql"))]
                counts[f"replaced_{kind}"] += 1
                counts[f"replaced_{kind}_{'correct' if final_ok else 'wrong'}"] += 1
            if orig_ok and not final_ok:
                counts["damage"] += 1
            if not orig_ok and final_ok:
                counts["rescue"] += 1
            if gold is not None and not gold:
                counts["gold_empty"] += 1
            if list_cases:
                cases.append({"row": row, "db": q.db_id, "orig_ok": orig_ok, "final_ok": final_ok,
                              "replaced": replaced, "original": original, "delivered": rec.get("sql"),
                              "retry": retry})
    t = counts["triggers"] / answers if answers else 0.0
    h = counts["orig_wrong"] / counts["triggers"] if counts["triggers"] else 0.0
    r = counts["rescue"] / counts["orig_wrong"] if counts["orig_wrong"] else 0.0
    d = counts["damage"] / counts["orig_correct"] if counts["orig_correct"] else 0.0
    return {
        "run": run, "questions_file": Path(meta["questions"]).name, "answers": answers, **counts,
        "t": round(t, 4), "h": round(h, 3), "r": round(r, 3), "d": round(d, 3),
        "net_points": round(100 * (counts["rescue"] - counts["damage"]) / answers, 2) if answers else 0.0,
        "breakeven_d": round(h * r / (1 - h), 3) if h < 1 else None,
        **({"cases": cases} if list_cases else {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--cases", action="store_true", help="list per-case detail (training sets only)")
    args = parser.parse_args()
    for run in args.runs:
        print(json.dumps(audit_run(run, list_cases=args.cases), default=str))


if __name__ == "__main__":
    main()
