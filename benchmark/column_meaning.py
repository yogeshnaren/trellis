"""BIRD's supplied column meanings, added selectively per question (SOTA plan rank 1c).

BIRD ships a ``column_meaning.json`` with its test set (and ``train_column_meaning.json``
with the filtered train set): one summarized description per ``db|table|column``. Dumping
every description into the prompt already failed as `--dictionary` (+53% prompt, no gain),
so only the few columns whose names or descriptions overlap the question and evidence are
added, in the user message so the per-database system prompt stays cacheable.

Selection uses only the question, evidence and the description file: no gold.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

DEFAULT_PATH = Path("data/bird/train_filtered/train_column_meaning.json")
MEANING_CHARS = 220
_BOILERPLATE = re.compile(
    r"^\s*The\s+'[^']*'\s+column\s+in\s+the\s+'[^']*'\s+table\s+of\s+the\s+'[^']*'\s+"
    r"database\s+",
    re.IGNORECASE,
)
_STOP = frozenset(
    (
        "a", "an", "and", "are", "as", "at", "be", "by", "column", "database", "did", "do", "does",
        "for", "from", "how", "in", "is", "it", "its", "many", "much", "of", "on", "or", "stores",
        "table", "that", "the", "their", "there", "these", "this", "those", "to", "was", "were",
        "what", "when", "where", "which", "who", "with", "refers", "refer",
    )
)


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _terms(text: str) -> set[str]:
    """Words, naively singularised, plus adjacent pairs joined ("screen time" also yields
    "screentime"), so natural phrasing can match compound column names."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)  # camelCase -> camel Case
    words = [w for w in re.findall(r"[a-z0-9]+", spaced.casefold()) if len(w) > 1]
    joined = {_stem(a + b) for a, b in pairwise(words)}
    return {_stem(w) for w in words if w not in _STOP} | joined


def clean(meaning: str) -> str:
    """Drop the "The 'x' column in the 'y' table of the 'z' database" preamble and clip."""
    text = " ".join(_BOILERPLATE.sub("", meaning).split())
    text = text[:1].upper() + text[1:]
    return text if len(text) <= MEANING_CHARS else text[: MEANING_CHARS - 1].rstrip() + "…"


class ColumnMeanings:
    def __init__(self, entries: dict[str, str]):
        self.by_db: dict[str, list[tuple[str, str, str, set[str], set[str]]]] = defaultdict(list)
        for key, meaning in entries.items():
            db_id, table, column = key.split("|", 2)
            text = clean(meaning)
            self.by_db[db_id].append(
                (table, column, text, _terms(f"{table} {column}"), _terms(text))
            )

    @classmethod
    def from_file(cls, path: Path) -> ColumnMeanings:
        return cls(json.loads(Path(path).read_text()))

    def select(self, db_id: str, question: str, evidence: str, n: int) -> list[tuple[str, str, str]]:
        """Top-n (table, column, meaning): name overlap with the question counts most,
        description overlap less (normalised by description length)."""
        wanted = _terms(f"{question} {evidence}")
        scored = []
        for table, column, text, name_terms, meaning_terms in self.by_db.get(db_id, []):
            name_hits = len(wanted & name_terms)
            meaning_hits = len(wanted & meaning_terms)
            if not name_hits and meaning_hits < 2:
                continue
            score = 2.0 * name_hits + meaning_hits / math.sqrt(len(meaning_terms) or 1)
            scored.append((-score, table, column, text))
        return [(table, column, text) for _, table, column, text in sorted(scored)[:n]]


def render(selected: list[tuple[str, str, str]]) -> str:
    """Notes block placed before the question in the user message."""
    if not selected:
        return ""
    lines = "\n".join(f"- {table}.{column}: {text}" for table, column, text in selected)
    return f"Notes on possibly relevant columns (from the database documentation):\n{lines}\n\n"
