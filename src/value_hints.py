"""Stored-value hints for an empty or all-NULL answer (benchmark-mode empty retry only).

When a query returns nothing, a common cause is a filter literal that is not stored in that
column: 'Allen' where the database stores 'Allen County', a trailing space or period, another
spelling, or a date filter written as 2018-07 against text stored as M/D/YY. This module finds
each text literal the query compares with a column (=, IN, LIKE), checks with read-only queries
whether that value is stored, and if not lists up to three stored values that look like it.
It never edits SQL; the hints only enter the existing one-time empty-result retry, whose
replacement guard (safe, valid, returns rows) is unchanged.
"""

from __future__ import annotations

import difflib
import re
import sqlite3
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

DATE_SLASH = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
MAX_HINTS = 4
MAX_DISTINCT_FOR_FUZZY = 20_000


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _schema(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: {str(c[1]): str(c[2] or "TEXT") for c in conn.execute(f"PRAGMA table_info({_q(t)})")}
            for t in tables}


def _comparisons(sql: str, schema: dict[str, dict[str, str]]) -> list[tuple[str, str, str, str]]:
    """(table, column, literal, operator) for text literals compared with a column."""
    try:
        tree: Any = qualify(parse_one(sql, read="sqlite"), schema=dict(schema), dialect="sqlite",
                            validate_qualify_columns=False, quote_identifiers=False, identify=False)
    except (SqlglotError, ValueError, KeyError, AttributeError):
        return []
    aliases = {(t.alias_or_name or t.name).casefold(): t.name for t in tree.find_all(exp.Table)}
    real = {t.casefold(): t for t in schema}
    out: list[tuple[str, str, str, str]] = []

    def resolve(col: exp.Column) -> tuple[str, str] | None:
        table = aliases.get((col.table or "").casefold())
        table = real.get(table.casefold()) if table else None
        if table is None:
            return None
        column = next((c for c in schema[table] if c.casefold() == col.name.casefold()), None)
        return (table, column) if column else None

    for node in tree.find_all(exp.EQ, exp.Like, exp.ILike, exp.In):
        col = node.this
        if isinstance(col, exp.Lower | exp.Upper | exp.Trim):
            col = col.this
        if not isinstance(col, exp.Column):
            continue
        target = resolve(col)
        if target is None:
            continue
        literals = node.expressions if isinstance(node, exp.In) else [node.expression]
        op = "like" if isinstance(node, exp.Like | exp.ILike) else "eq"
        for lit in literals:
            if isinstance(lit, exp.Literal) and lit.is_string and lit.this.strip():
                out.append((*target, lit.this, op))
    return out


def _near(conn: sqlite3.Connection, table: str, column: str, literal: str) -> list[str]:
    t, c = _q(table), _q(column)
    core = literal.strip("% ").strip()
    if len(core) < 2:
        return []
    found: list[str] = []
    queries = [
        (f"SELECT DISTINCT {c} FROM {t} WHERE TRIM({c}, ' .') = TRIM(?, ' .') COLLATE NOCASE LIMIT 3", (core,)),
        (f"SELECT DISTINCT {c} FROM {t} WHERE {c} LIKE ? LIMIT 3", (f"%{core}%",)),
        (f"SELECT DISTINCT {c} FROM {t} WHERE length({c}) >= 3 AND ? LIKE '%' || {c} || '%' LIMIT 3", (core,)),
    ]
    for query, params in queries:
        for (value,) in conn.execute(query, params):
            if isinstance(value, str) and value not in found:
                found.append(value)
        if found:
            return found[:3]
    count = conn.execute(f"SELECT COUNT(DISTINCT {c}) FROM {t}").fetchone()[0]
    if count and count <= MAX_DISTINCT_FOR_FUZZY:
        values = [v for (v,) in conn.execute(f"SELECT DISTINCT {c} FROM {t} WHERE typeof({c}) = 'text'")]
        lowered = {v.casefold(): v for v in values}
        return [lowered[m] for m in difflib.get_close_matches(core.casefold(), list(lowered), n=3, cutoff=0.8)]
    return []


def value_hints(sql: str, db_path: str | Path) -> list[str]:
    """Hints for literals the database does not store as written, and for slash-stored dates."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    hints: list[str] = []
    try:
        schema = _schema(conn)
        for table, column, literal, op in _comparisons(sql, schema):
            t, c = _q(table), _q(column)
            stored = conn.execute(
                f"SELECT 1 FROM {t} WHERE {c} {'LIKE' if op == 'like' else '='} ? LIMIT 1", (literal,)
            ).fetchone()
            if stored:
                continue
            near = _near(conn, table, column, literal)
            if near:
                hints.append(f"{table}.{column} has no value {literal!r}; stored values that look "
                             f"similar: {', '.join(repr(v) for v in near)}.")
        upper = sql.upper()
        if any(f in upper for f in ("STRFTIME", "JULIANDAY", "DATE(", "BETWEEN '", "'20", "'19")):
            for table, cols in schema.items():
                for column in cols:
                    if column.casefold() not in sql.casefold():
                        continue
                    sample = conn.execute(f"SELECT {_q(column)} FROM {_q(table)} WHERE {_q(column)} IS NOT NULL "
                                          f"LIMIT 1").fetchone()
                    if sample and isinstance(sample[0], str) and DATE_SLASH.match(sample[0]):
                        hints.append(f"{table}.{column} stores dates as text month/day/year, e.g. "
                                     f"{sample[0]!r}; date functions cannot parse it.")
    except sqlite3.Error:
        return hints[:MAX_HINTS]
    finally:
        conn.close()
    return list(dict.fromkeys(hints))[:MAX_HINTS]
