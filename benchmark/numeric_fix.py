"""Deterministic rewrite for numbers stored as text (review P05, narrow shadow prototype).

Two rules, driven by the database profile's per-column text format (never by the answer key):

- ``strip_cast``: a CAST of a money / thousands / percent column that does not remove its
  symbols first (SQLite reads '31,867' as 31 and '$4.99' as 0) gets the symbols removed
  inside the cast.
- ``cast_text_number``: a numeric-text column compared with a number, ordered, used in
  arithmetic or in SUM/AVG/MIN/MAX without any cast gets ``CAST(<symbols removed> AS REAL)``
  (INTEGER for integer text). Text comparison and ordering of such columns is lexicographic.

The query is left untouched when no rule fires. Nothing here runs in the live path; it is
measured offline for rescues versus damage first (``python -m benchmark.numeric_fix``).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

from benchmark.sql_checks import (
    NUMERIC_TEXT,
    SYMBOLIC_TEXT,
    _key,
    _profile,
    _resolved_columns,
    _schema,
)

SYMBOLS = {"money": ("$", ","), "thousands": (",",), "percent": ("%", ",")}
NUMERIC_PARENTS = (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between, exp.Add, exp.Sub, exp.Mul,
                   exp.Div, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Ordered)


def _strip(node: exp.Expression, fmt: str) -> exp.Expression:
    for symbol in SYMBOLS.get(fmt, ()):
        node = exp.Anonymous(this="REPLACE", expressions=[node, exp.Literal.string(symbol), exp.Literal.string("")])
    return node


def _has_replace(cast: exp.Cast, col: exp.Column) -> bool:
    return any(isinstance(a, exp.Anonymous) and str(a.this).upper() == "REPLACE" or a.key == "replace"
               for a in cast.walk() if a is not cast and a is not col)


def rewrite(sql: str, db_path: str | Path) -> tuple[str, list[str]]:
    db = str(db_path)
    try:
        tree: Any = qualify(parse_one(sql, read="sqlite"), schema=dict(_schema(db)), dialect="sqlite",
                            validate_qualify_columns=False, quote_identifiers=False, identify=False)
    except (SqlglotError, ValueError, KeyError, AttributeError):
        return sql, []
    formats = {_key(c.table, c.column): c.text_format for c in _profile(db).columns
               if c.text_format and c.storage.get("text", 0) >= 0.5}
    cols = _resolved_columns(tree)
    rules: list[str] = []
    for col in list(tree.find_all(exp.Column)):
        key = cols.get(id(col))
        fmt = formats.get(key) if key else None
        if not fmt or fmt not in NUMERIC_TEXT:
            continue
        cast = col.find_ancestor(exp.Cast)
        inside_cast = cast is not None and cast.find_ancestor(exp.Select) is col.find_ancestor(exp.Select)
        if inside_cast:
            assert cast is not None
            if fmt in SYMBOLIC_TEXT and not _has_replace(cast, col):
                col.replace(_strip(col.copy(), fmt))
                rules.append("strip_cast")
            continue
        parent = col.parent
        if not isinstance(parent, NUMERIC_PARENTS):
            continue
        if isinstance(parent, (exp.GT, exp.GTE, exp.LT, exp.LTE)):
            other = parent.expression if parent.this is col else parent.this
            if isinstance(other, exp.Literal) and not other.is_number:
                continue  # compared with a string literal: leave the author's text comparison
        target = "INTEGER" if fmt == "integer-text" else "REAL"
        col.replace(exp.Cast(this=_strip(col.copy(), fmt), to=exp.DataType.build(target)))
        rules.append("cast_text_number")
    if not rules:
        return sql, []
    return tree.sql(dialect="sqlite"), sorted(set(rules))


def measure(questions_path: Path, db_dir: Path, run: str, labels: Path | None, label_rows: Path | None,
            prefix: str) -> dict[str, Any]:
    """Rescue vs damage of the rewrite on one saved run (official keys; corrected keys too
    when adjudicated labels are given). Training sets only."""
    import benchmark.bank_report as br
    from benchmark.analyze import delivered_sql, load_runs
    from benchmark.bird import db_path_for, load_questions
    from benchmark.evaluate import official_ex
    from src.db import connect_readonly, execute_candidate, timeout_for_database

    questions = load_questions(questions_path)
    by_row = {q.row_index: q for q in questions}
    runs = load_runs(Path(f"benchmark/results/bird_raw_{run}.jsonl"), questions)
    refs = (br.reference_signatures(questions, db_dir, json.loads(labels.read_text()),
                                    json.loads(label_rows.read_text())["source_rows"], prefix)
            if labels and label_rows else {})
    out: dict[str, Any] = {"answers": 0, "fired": 0, "rules": {}, "official": [0, 0], "corrected": [0, 0]}
    for row, recs in runs.items():
        rec, q = recs[0], by_row[row]
        sql = delivered_sql(rec)
        out["answers"] += 1
        if not sql:
            continue
        path = db_path_for(q.db_id, db_dir=db_dir)
        new, rules = rewrite(sql, path)
        if not rules:
            continue
        out["fired"] += 1
        for rule in rules:
            out["rules"][rule] = out["rules"].get(rule, 0) + 1
        conn = connect_readonly(path, timeout_seconds=timeout_for_database(path, default=30.0))
        try:
            before, after = bool(rec.get("official_ex")), official_ex(conn, q.gold_sql, new)
            out["official"][0] += after and not before
            out["official"][1] += before and not after
            ref = refs.get(row)
            if ref:
                old_sig, new_res = execute_candidate(conn, sql, db_path=path), execute_candidate(conn, new, db_path=path)
                was, now = old_sig.signature in ref, new_res.signature in ref
                out["corrected"][0] += now and not was
                out["corrected"][1] += was and not now
        finally:
            conn.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, default=Path("data/bird/train/train_databases"))
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--label-rows", type=Path)
    parser.add_argument("--label-prefix", default="train_dev2")
    parser.add_argument("run")
    args = parser.parse_args()
    result = measure(args.questions, args.db_dir, args.run, args.labels, args.label_rows, args.label_prefix)
    print(json.dumps(result) + "  (official/corrected = [rescues, damages])")


if __name__ == "__main__":
    main()
