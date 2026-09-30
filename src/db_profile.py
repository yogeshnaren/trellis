"""Deterministic per-database profile: value formats, join cardinality, and a value index.

SOTA plan rank 1a. Built offline from the database alone (never from gold answers) and
cached by the database's content hash, so it can also run on unseen (hidden-test)
databases before their questions are answered:

- **Column profiles:** storage classes, NULL rate, distinct count and the dominant text
  format, from a bounded sample. Text-encoded numbers, money, dates and durations are the
  failures the postmortem found (e.g. ``screentime`` '0:17:30', ``NetWorth``
  '$20,000,000.00').
- **Join facts:** each declared foreign key's cardinality (1:1 vs 1:N), so fan-out from a
  join can be seen before it inflates a COUNT or SUM.
- **Value index:** an FTS5 index of distinct text values, for retrieving the literal a
  question refers to ('Godzilla', 'american') with its table and column.

Every query here is bounded (row sample, distinct cap), because BIRD's test set includes
some giant databases.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROFILE_VERSION = 3  # 3: numbers with separators only on large values are "thousands"
DEFAULT_CACHE_DIR = Path("data/profiles")
SAMPLE_ROWS = 20_000
MAX_INDEXED_DISTINCT = 50_000
MAX_VALUE_CHARS = 120
FORMAT_SHARE = 0.9  # a text column "is" a format when this share of sampled values match

# Checked in order; the first match wins for each value.
TEXT_FORMATS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("money", re.compile(r"^\s*[-+]?\$\s?\d[\d,]*(\.\d+)?\s*$")),
    ("percent", re.compile(r"^\s*[-+]?\d+(\.\d+)?\s?%\s*$")),
    ("datetime", re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")),
    ("date", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("date-slash", re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")),
    ("duration", re.compile(r"^\d{1,3}:\d{2}(:\d{2})?$")),
    ("thousands", re.compile(r"^[-+]?\d{1,3}(,\d{3})+(\.\d+)?$")),
    ("integer-text", re.compile(r"^[-+]?\d+$")),
    ("decimal-text", re.compile(r"^[-+]?\d*\.\d+$")),
)


@dataclass(frozen=True)
class ColumnProfile:
    table: str
    column: str
    declared: str
    storage: dict[str, float]  # typeof() share in the sample, e.g. {"text": 0.97, "null": 0.03}
    null_rate: float
    distinct: int  # in the sample, capped
    text_format: str | None  # dominant TEXT format, e.g. "money"; None if plain text/mixed
    examples: tuple[str, ...]


@dataclass(frozen=True)
class JoinFact:
    table: str
    column: str
    parent_table: str
    parent_column: str
    parent_unique: bool
    max_children: int  # most child rows sharing one parent value
    cardinality: str  # "1:1" or "1:N" (child side), "N:M" when the parent key isn't unique


@dataclass
class DatabaseProfile:
    fingerprint: str
    version: int
    columns: list[ColumnProfile]
    joins: list[JoinFact]
    build_seconds: float
    index_path: str
    indexed_values: int = 0
    notes: list[str] = field(default_factory=list)

    def text_formatted(self) -> list[ColumnProfile]:
        """Columns whose values are text but mean numbers, money, dates or durations."""
        return [c for c in self.columns if c.text_format is not None]


def content_fingerprint(db_path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(db_path).open("rb") as handle:
        while chunk := handle.read(1 << 22):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _connect(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]


def text_format(values: list[str]) -> str | None:
    """The format most values share, if at least ``FORMAT_SHARE`` of them match it."""
    if not values:
        return None
    counts: Counter[str] = Counter()
    for value in values:
        for name, pattern in TEXT_FORMATS:
            if pattern.match(value):
                counts[name] += 1
                break
    if not counts:
        return None
    name, count = counts.most_common(1)[0]
    if count / len(values) >= FORMAT_SHARE:
        return name
    # Numbers where only the large values carry separators ('1,963.10' next to '781.22') are
    # one format: casting them without removing the commas silently truncates the large ones.
    numeric = counts["thousands"] + counts["integer-text"] + counts["decimal-text"]
    if counts["thousands"] and numeric / len(values) >= FORMAT_SHARE:
        return "thousands"
    return None


def _profile_column(
    conn: sqlite3.Connection, table: str, column: str, declared: str
) -> ColumnProfile:
    rows = conn.execute(
        f"SELECT typeof({_q(column)}), {_q(column)} FROM {_q(table)} LIMIT {SAMPLE_ROWS}"
    ).fetchall()
    total = len(rows) or 1
    storage = Counter(str(kind) for kind, _ in rows)
    texts = [str(value) for kind, value in rows if kind == "text"]
    distinct = len({value for _, value in rows if value is not None})
    examples = tuple(
        sorted({value[:40] for value in texts if value.strip()})[:3]
    ) if texts else tuple(sorted({str(v) for _, v in rows if v is not None})[:3])
    return ColumnProfile(
        table=table,
        column=column,
        declared=declared or "ANY",
        storage={kind: round(count / total, 3) for kind, count in storage.most_common()},
        null_rate=round(storage.get("null", 0) / total, 3),
        distinct=distinct,
        # Judge format over non-NULL values: a mostly-NULL column ('screentime', 8 of
        # 4,312 filled) still stores its few values as text-encoded durations.
        text_format=(
            text_format(texts)
            if len(texts) >= 3 and len(texts) >= 0.5 * (total - storage.get("null", 0))
            else None
        ),
        examples=examples,
    )


def _foreign_keys(conn: sqlite3.Connection, tables: list[str]) -> list[tuple[str, str, str, str]]:
    folded = {name.casefold(): name for name in tables}
    edges: set[tuple[str, str, str, str]] = set()
    for table in tables:
        for row in conn.execute(f"PRAGMA foreign_key_list({_q(table)})").fetchall():
            parent = folded.get(str(row[2]).casefold())
            if parent is None:
                continue
            parent_column = row[4]
            if parent_column is None:  # REFERENCES parent -> its primary key
                pk = [
                    str(info[1])
                    for info in sorted(
                        conn.execute(f"PRAGMA table_info({_q(parent)})").fetchall(),
                        key=lambda info: info[5],
                    )
                    if info[5]
                ]
                if row[1] >= len(pk):
                    continue
                parent_column = pk[row[1]]
            edges.add((table, str(row[3]), parent, str(parent_column)))
    return sorted(edges)


def _join_fact(conn: sqlite3.Connection, edge: tuple[str, str, str, str]) -> JoinFact | None:
    table, column, parent, parent_column = edge
    try:
        (parent_dupes,) = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT {_q(parent_column)} FROM {_q(parent)} "
            f"WHERE {_q(parent_column)} IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 1)"
        ).fetchone()
        (max_children,) = conn.execute(
            f"SELECT COALESCE(MAX(n), 0) FROM (SELECT COUNT(*) AS n FROM {_q(table)} "
            f"WHERE {_q(column)} IS NOT NULL GROUP BY {_q(column)})"
        ).fetchone()
    except sqlite3.Error:
        return None  # e.g. a declared FK naming a column that doesn't exist
    unique = parent_dupes == 0
    cardinality = "N:M" if not unique else ("1:1" if max_children <= 1 else "1:N")
    return JoinFact(table, column, parent, parent_column, unique, int(max_children), cardinality)


def _build_index(conn: sqlite3.Connection, columns: list[ColumnProfile], path: Path) -> int:
    path.unlink(missing_ok=True)
    index = sqlite3.connect(path)
    try:
        index.execute(
            "CREATE VIRTUAL TABLE value_index USING fts5("
            "value, tbl UNINDEXED, col UNINDEXED, tokenize='unicode61 remove_diacritics 2')"
        )
        count = 0
        for profile in columns:
            if profile.storage.get("text", 0) < 0.5 or profile.text_format is not None:
                continue  # numeric-like columns are profiled, not indexed as words
            rows = conn.execute(
                f"SELECT DISTINCT {_q(profile.column)} FROM {_q(profile.table)} "
                f"WHERE typeof({_q(profile.column)}) = 'text' "
                f"AND length({_q(profile.column)}) BETWEEN 1 AND {MAX_VALUE_CHARS} "
                f"LIMIT {MAX_INDEXED_DISTINCT}"
            ).fetchall()
            index.executemany(
                "INSERT INTO value_index (value, tbl, col) VALUES (?, ?, ?)",
                [(str(value), profile.table, profile.column) for (value,) in rows],
            )
            count += len(rows)
        index.commit()
        return count
    finally:
        index.close()


def build_profile(
    db_path: str | Path, cache_dir: Path = DEFAULT_CACHE_DIR, *, refresh: bool = False
) -> DatabaseProfile:
    """Profile a database, reusing the cached profile for identical content."""
    fingerprint = content_fingerprint(db_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    json_path = cache_dir / f"{fingerprint}.profile.json"
    index_path = cache_dir / f"{fingerprint}.values.sqlite"
    if not refresh and json_path.exists() and index_path.exists():
        cached = load_profile(json_path)
        if cached.version == PROFILE_VERSION:
            return cached
    started = time.perf_counter()
    conn = _connect(db_path)
    try:
        tables = _tables(conn)
        columns = [
            _profile_column(conn, table, str(info[1]), str(info[2] or ""))
            for table in tables
            for info in conn.execute(f"PRAGMA table_info({_q(table)})").fetchall()
        ]
        joins = [
            fact
            for edge in _foreign_keys(conn, tables)
            if (fact := _join_fact(conn, edge)) is not None
        ]
        indexed = _build_index(conn, columns, index_path)
    finally:
        conn.close()
    profile = DatabaseProfile(
        fingerprint=fingerprint,
        version=PROFILE_VERSION,
        columns=columns,
        joins=joins,
        build_seconds=round(time.perf_counter() - started, 3),
        index_path=str(index_path),
        indexed_values=indexed,
    )
    json_path.write_text(json.dumps(asdict(profile), indent=1) + "\n")
    return profile


def load_profile(path: Path) -> DatabaseProfile:
    data: dict[str, Any] = json.loads(path.read_text())
    data["columns"] = [
        ColumnProfile(**{**c, "examples": tuple(c["examples"])}) for c in data["columns"]
    ]
    data["joins"] = [JoinFact(**j) for j in data["joins"]]
    return DatabaseProfile(**data)


_STOP = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for", "from", "how", "in", "is", "it", "its", "many", "much", "of", "on", "or", "the", "their", "there", "these", "this", "those", "to", "was", "were", "what", "when", "where", "which", "who", "whom", "whose", "with", "refers", "refer", "list", "name", "names", "give", "show", "find", "among"]
)


def _terms(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[^\W_]+", text.casefold())
        if len(word) >= 2 and word not in _STOP
    ]


def retrieve_values(
    profile: DatabaseProfile, text: str, k: int = 10
) -> list[tuple[str, str, str]]:
    """Top-k (table, column, value) whose value text best matches the question words.

    Quoted strings in the question or evidence ('Godzilla') are searched as exact phrases
    first; remaining words are matched with BM25 over the value index.
    """
    phrases = [a or b for a, b in re.findall(r"'([^']{2,})'|\"([^\"]{2,})\"", text)]
    queries = ['"' + p.replace('"', '""') + '"' for p in phrases]
    terms = _terms(text)
    if terms:
        queries.append(" OR ".join('"' + t.replace('"', '""') + '"' for t in terms))
    if not queries:
        return []
    index = sqlite3.connect(f"file:{profile.index_path}?mode=ro", uri=True)
    try:
        seen: dict[tuple[str, str, str], float] = {}
        for rank, query in enumerate(queries):
            try:
                rows = index.execute(
                    "SELECT tbl, col, value, bm25(value_index) FROM value_index "
                    "WHERE value_index MATCH ? ORDER BY bm25(value_index) LIMIT ?",
                    (query, k),
                ).fetchall()
            except sqlite3.OperationalError:
                continue  # a malformed FTS query from odd punctuation; skip it
            for table, column, value, score in rows:
                # Exact-phrase hits (earlier queries) outrank word matches.
                key = (str(table), str(column), str(value))
                seen.setdefault(key, rank * 1_000 + float(score))
        return [key for key, _ in sorted(seen.items(), key=lambda item: item[1])[:k]]
    finally:
        index.close()
