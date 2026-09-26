"""Retrieved few-shot examples from BIRD train, drawn only from *other* databases.

Phase 3 evidence showed that the remaining errors are shared by every model and that many
stem from BIRD's annotation conventions: a hint's formula is meant literally, and "X refers
to column" means return that column. Retrieved examples show those conventions without
extra LLM calls. The pool is the official BIRD train set (CC BY-SA 4.0): noisy, but it is
the same annotation style the benchmark scores against.

Leakage guard: every held-out database (``train_dev`` and ``train_lockbox``) is excluded
from the pool, so an example can never come from the database being evaluated.
Examples go in the *user* message, so the per-database system prompt stays cacheable.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_POOL = Path("data/bird/train/train.json")
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "how",
        "in", "is", "it", "its", "of", "on", "or", "refers", "refer", "the", "to", "was",
        "were", "what", "which", "who", "whom", "with",
    }
)
EXAMPLE_SQL_CHARS = 600


def _tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.casefold()) if word not in _STOPWORDS]


class FewShotIndex:
    """BM25 over question + hint text of the pool, excluding held-out databases."""

    def __init__(
        self,
        pool: list[dict[str, Any]],
        exclude_dbs: set[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.items = [item for item in pool if item["db_id"] not in exclude_dbs]
        self.excluded = frozenset(exclude_dbs)
        self.k1, self.b = k1, b
        docs = [_tokens(f"{item['question']} {item.get('evidence') or ''}") for item in self.items]
        self.lengths = [len(doc) for doc in docs]
        self.avg_length = sum(self.lengths) / max(len(docs), 1)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, doc in enumerate(docs):
            for term, count in Counter(doc).items():
                self.postings[term].append((index, count))
        total = len(docs)
        self.idf = {
            term: math.log(1 + (total - len(posts) + 0.5) / (len(posts) + 0.5))
            for term, posts in self.postings.items()
        }

    @classmethod
    def from_file(cls, path: Path, exclude_dbs: set[str]) -> FewShotIndex:
        return cls(json.loads(Path(path).read_text()), exclude_dbs)

    def examples(self, question: str, evidence: str, k: int) -> list[dict[str, Any]]:
        """Top-k pool items by BM25, at most one per pool database for variety."""
        scores: dict[int, float] = defaultdict(float)
        for term in set(_tokens(f"{question} {evidence}")):
            for index, count in self.postings.get(term, []):
                norm = count + self.k1 * (1 - self.b + self.b * self.lengths[index] / self.avg_length)
                scores[index] += self.idf[term] * count * (self.k1 + 1) / norm
        chosen: list[dict[str, Any]] = []
        seen_dbs: set[str] = set()
        for index in sorted(scores, key=lambda i: (-scores[i], i)):
            item = self.items[index]
            if item["db_id"] in seen_dbs:
                continue
            chosen.append(item)
            seen_dbs.add(item["db_id"])
            if len(chosen) == k:
                break
        return chosen


def render_examples(examples: list[dict[str, Any]]) -> str:
    """Examples block placed before the question in the user message."""
    if not examples:
        return ""
    blocks = []
    for item in examples:
        sql = " ".join(item["SQL"].split())
        if len(sql) > EXAMPLE_SQL_CHARS:
            sql = sql[: EXAMPLE_SQL_CHARS - 1] + "…"
        hint = (item.get("evidence") or "").strip()
        blocks.append(
            f"Question: {item['question'].strip()}\n"
            + (f"Hint: {hint}\n" if hint else "")
            + f"SQL: {sql}"
        )
    return (
        "Solved examples from OTHER databases. They show how questions and hints map to "
        "SQL (follow a hint's formula and column mappings literally); their tables are not "
        "in this database, so use only the schema above.\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\nNow answer this question:\n"
    )
