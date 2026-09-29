"""Offline detectors for the audit's top model-side error mechanisms (P05–P07 prototypes).

Each detector flags a *risk* in one delivered SQL query using only the query, the schema
and the database profile. Nothing here edits SQL or runs in the live path: the detectors
are measured first on training sets for how often they fire on wrong answers (rescue
opportunity) versus correct answers (damage risk), following Δ = t × [h × r − (1−h) × d].

- ``text_number``: a text-stored numeric column (money, thousands, integer/decimal text,
  percent) compared, sorted, aggregated or used in arithmetic without a CAST.
- ``lossy_cast``: CAST of a money/thousands/percent column without removing its
  symbols first (SQLite reads '31,867' as 31 and '$4.99' as 0).
- ``integer_division``: a division whose operands are both integer-valued (COUNT, SUM of
  integer columns, integer columns) with no REAL cast or float factor.
- ``fanout_count``: a non-DISTINCT COUNT in a query that joins across a one-to-many edge,
  so a parent entity can be counted once per child row.
- ``ranked_extra_column``: ORDER BY … LIMIT query that also projects its ranking
  expression (e.g. ``SELECT name, MAX(x) … LIMIT 1``) — a likely unrequested column.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

from src.db_profile import DatabaseProfile, build_profile

NUMERIC_TEXT = {"money", "thousands", "integer-text", "decimal-text", "percent"}
SYMBOLIC_TEXT = {"money", "thousands", "percent"}
DETECTORS = ("text_number", "lossy_cast", "integer_division", "fanout_count", "ranked_extra_column")


@lru_cache(maxsize=64)
def _schema(db_path: str) -> dict[str, dict[str, str]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: {str(c[1]): str(c[2] or "TEXT") for c in conn.execute(f'PRAGMA table_info("{t}")')}
                for t in tables}
    finally:
        conn.close()


@lru_cache(maxsize=64)
def _profile(db_path: str) -> DatabaseProfile:
    return build_profile(db_path)


def _key(table: str, column: str) -> tuple[str, str]:
    return table.casefold(), column.casefold()


def _resolved_columns(tree: exp.Expression) -> dict[int, tuple[str, str]]:
    """Map each Column node (by id) to its (table, column) via table aliases."""
    aliases: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        aliases[(table.alias_or_name or table.name).casefold()] = table.name
    out: dict[int, tuple[str, str]] = {}
    for col in tree.find_all(exp.Column):
        if col.table and col.table.casefold() in aliases:
            out[id(col)] = _key(aliases[col.table.casefold()], col.name)
    return out


def _under_cast(node: exp.Expression) -> bool:
    parent = node.parent
    while parent is not None and not isinstance(parent, (exp.Select, exp.Where, exp.Order)):
        if isinstance(parent, exp.Cast):
            return True
        parent = parent.parent
    return False


def _has_real(node: exp.Expression) -> bool:
    for cast in node.find_all(exp.Cast):
        if cast.to.this in (exp.DataType.Type.FLOAT, exp.DataType.Type.DOUBLE, exp.DataType.Type.DECIMAL):
            return True
        if "REAL" in cast.to.sql().upper():
            return True
    return any(lit.is_number and "." in lit.this for lit in node.find_all(exp.Literal))


def check_sql(sql: str, db_path: str | Path) -> list[str]:
    """Names of the detectors that fire on one query (empty when none, or unparsable)."""
    db = str(db_path)
    schema = _schema(db)
    try:
        tree: Any = parse_one(sql, read="sqlite")
        tree = qualify(tree, schema=dict(schema), dialect="sqlite", validate_qualify_columns=False,
                       quote_identifiers=False, identify=False)
    except (SqlglotError, ValueError, KeyError, AttributeError):
        return []
    profile = _profile(db)
    formats = {_key(c.table, c.column): c.text_format for c in profile.columns
               if c.text_format and c.storage.get("text", 0) >= 0.5}
    declared = {_key(t, c): ty.upper() for t, cols in schema.items() for c, ty in cols.items()}
    cols = _resolved_columns(tree)
    fired: set[str] = set()

    for col in tree.find_all(exp.Column):
        key = cols.get(id(col))
        fmt = formats.get(key) if key else None
        if not fmt:
            continue
        if fmt in NUMERIC_TEXT and not _under_cast(col):
            parent = col.parent
            numeric_use = isinstance(parent, (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between,
                                              exp.Add, exp.Sub, exp.Mul, exp.Div, exp.AggFunc)) \
                or isinstance(parent, exp.Ordered)
            if isinstance(parent, (exp.GT, exp.GTE, exp.LT, exp.LTE)):
                other = parent.expression if parent.this is col else parent.this
                numeric_use = isinstance(other, exp.Literal) and other.is_number or not isinstance(other, exp.Literal)
            if numeric_use and not isinstance(parent, (exp.Count,)):
                fired.add("text_number")
        if fmt in SYMBOLIC_TEXT and _under_cast(col):
            cast = col.find_ancestor(exp.Cast)
            if cast is not None and not any(isinstance(a, exp.Anonymous) or a.key == "replace"
                                            for a in cast.walk() if a is not cast and a is not col):
                fired.add("lossy_cast")

    def integer_valued(node: exp.Expression) -> bool:
        if isinstance(node, exp.Paren):
            return integer_valued(node.this)
        if isinstance(node, exp.Count):
            return True
        if isinstance(node, (exp.Sum, exp.Max, exp.Min)):
            return integer_valued(node.this)
        if isinstance(node, exp.Column):
            key = cols.get(id(node))
            return key is not None and "INT" in declared.get(key, "") and formats.get(key) is None
        if isinstance(node, exp.Literal):
            return node.is_int
        if isinstance(node, (exp.Add, exp.Sub, exp.Mul)):
            return integer_valued(node.this) and integer_valued(node.expression)
        return False

    for div in tree.find_all(exp.Div):
        scope = div.parent if isinstance(div.parent, exp.Mul) else div
        if integer_valued(div.this) and integer_valued(div.expression) and not _has_real(scope):
            fired.add("integer_division")

    one_to_many = {(_key(j.table, j.column)[0], j.parent_table.casefold()) for j in profile.joins
                   if j.max_children > 1}
    tables = {t.name.casefold() for t in tree.find_all(exp.Table)}
    if tree.find(exp.Join) and any(child in tables and parent in tables for child, parent in one_to_many):
        for count in tree.find_all(exp.Count):
            if not isinstance(count.this, exp.Distinct):
                fired.add("fanout_count")

    for select in tree.find_all(exp.Select):
        order = select.args.get("order")
        if order is None or select.args.get("limit") is None or len(select.expressions) < 2:
            continue
        ranked = {o.this.sql().casefold() for o in order.expressions}
        for proj in select.expressions:
            inner = proj.this if isinstance(proj, exp.Alias) else proj
            if inner.sql().casefold() in ranked or (isinstance(proj, exp.Alias) and proj.alias.casefold() in ranked):
                fired.add("ranked_extra_column")
    return sorted(fired)


def check_many(items: list[tuple[str, str | Path]]) -> list[list[str]]:
    return [check_sql(sql, db) if sql else [] for sql, db in items]


def detector_table(flags: list[list[str]], correct: list[bool], extra: list[Any] | None = None) -> list[dict[str, Any]]:
    """Per detector: fires, fires on wrong answers (h), fires on correct answers (damage exposure)."""
    rows = []
    for name in DETECTORS:
        hit = [i for i, f in enumerate(flags) if name in f]
        wrong = sum(1 for i in hit if not correct[i])
        rows.append({"detector": name, "fires": len(hit), "on_wrong": wrong, "on_correct": len(hit) - wrong,
                     "h": round(wrong / len(hit), 3) if hit else None,
                     "recall_of_wrong": round(wrong / max(1, correct.count(False)), 3)})
    return rows
