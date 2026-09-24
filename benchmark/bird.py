"""Loader for BIRD-SQL question sets: Mini-Dev (500 rows / 11 SQLite databases) and splits.

Dataset: https://github.com/bird-bench/mini_dev (fetch with scripts/setup_bird_minidev.sh).
Official metrics are execution accuracy (EX), soft-F1, and R-VES; this project implements EX
(``benchmark/evaluate.py:official_ex``) — soft-F1/R-VES are not implemented (see README).

Every question carries ``row_index``, its position in the source file. Mini-Dev ships two
exact duplicate items (question_id 137 and 138 each appear twice), and BIRD's official
evaluator scores all 500 rows, so rows — not question ids — are the unit of scoring.
Question files without ids or difficulty (BIRD train) get ``question_id = row_index`` and
difficulty ``"unknown"``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BIRD_DIR = Path("data/bird")
DEFAULT_QUESTIONS = DEFAULT_BIRD_DIR / "mini_dev_sqlite.json"
DEFAULT_DB_DIR = DEFAULT_BIRD_DIR / "dev_databases"
Difficulty = str  # "simple" | "moderate" | "challenging" | "unknown"


@dataclass(frozen=True)
class BirdQuestion:
    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: Difficulty
    row_index: int = 0


def db_path_for(db_id: str, *, db_dir: str | Path = DEFAULT_DB_DIR) -> Path:
    """Resolve a ``db_id`` to its SQLite file under a BIRD ``*_databases`` directory."""
    return Path(db_dir) / db_id / f"{db_id}.sqlite"


def load_questions(path: str | Path = DEFAULT_QUESTIONS) -> list[BirdQuestion]:
    """Load a BIRD-format question file, keeping every row (duplicates included)."""
    raw = json.loads(Path(path).read_text())
    return [
        BirdQuestion(
            question_id=int(item.get("question_id", index)),
            db_id=item["db_id"],
            question=item["question"],
            evidence=item.get("evidence") or "",
            gold_sql=item["SQL"],
            difficulty=item.get("difficulty") or "unknown",
            row_index=index,
        )
        for index, item in enumerate(raw)
    ]


def dataset_fingerprint(path: str | Path) -> str:
    """Short content hash so every run records exactly which dataset version it scored."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


DB_HASH_CACHE = DEFAULT_BIRD_DIR / ".db_hash_cache.json"


def database_fingerprint(path: str | Path, cache_path: Path = DB_HASH_CACHE) -> str:
    """Content hash of a database file, cached by (size, mtime) so large files hash once.

    Pins the *contents* a run scored against: a database edited in place (or BIRD dev's copy
    vs Mini-Dev's, which differ for 5 of 11 databases) gets a different fingerprint.
    """
    resolved = Path(path).resolve()
    stat = resolved.stat()
    stamp = f"{stat.st_size}:{stat.st_mtime_ns}"
    try:
        cache = json.loads(cache_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    entry = cache.get(str(resolved))
    if entry and entry["stamp"] == stamp:
        return str(entry["sha256_16"])
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        while chunk := handle.read(1 << 22):
            digest.update(chunk)
    cache[str(resolved)] = {"stamp": stamp, "sha256_16": digest.hexdigest()[:16]}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return str(cache[str(resolved)]["sha256_16"])


def with_evidence(question: str, evidence: str) -> str:
    """Append BIRD's expert-annotated evidence hint, when present, to the question text."""
    return f"{question}\n\nHint: {evidence}" if evidence.strip() else question
