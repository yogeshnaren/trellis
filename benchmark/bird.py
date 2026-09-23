"""Loader for BIRD-SQL Mini-Dev (500 questions / 11 SQLite databases).

Dataset: https://github.com/bird-bench/mini_dev (fetch with scripts/setup_bird_minidev.sh).
Official metrics are execution accuracy (EX), soft-F1, and R-VES; this project implements EX
only, via the same gold-result-set comparison used for the original Chinook dev questions
(``benchmark/evaluate.py:evaluate_sql``) — soft-F1/R-VES are not implemented (see README).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BIRD_DIR = Path("data/bird")
Difficulty = str  # "simple" | "moderate" | "challenging"


@dataclass(frozen=True)
class BirdQuestion:
    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: Difficulty


def db_path_for(db_id: str, *, bird_dir: str | Path = DEFAULT_BIRD_DIR) -> Path:
    """Resolve a Mini-Dev ``db_id`` to its SQLite file."""
    return Path(bird_dir) / "dev_databases" / db_id / f"{db_id}.sqlite"


def load_questions(
    path: str | Path = DEFAULT_BIRD_DIR / "mini_dev_sqlite.json",
) -> list[BirdQuestion]:
    """Load and parse the Mini-Dev SQLite question set."""
    raw = json.loads(Path(path).read_text())
    return [
        BirdQuestion(
            question_id=item["question_id"],
            db_id=item["db_id"],
            question=item["question"],
            evidence=item.get("evidence") or "",
            gold_sql=item["SQL"],
            difficulty=item["difficulty"],
        )
        for item in raw
    ]


def with_evidence(question: str, evidence: str) -> str:
    """Append BIRD's expert-annotated evidence hint, when present, to the question text."""
    return f"{question}\n\nHint: {evidence}" if evidence.strip() else question
