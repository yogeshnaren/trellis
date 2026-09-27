"""Small, question-relevant facts from a database profile (plan rank 1b).

These observations come only from the database and the question. They deliberately
describe stored values without telling the model to cast or reinterpret BIRD labels.
"""

from __future__ import annotations

import re
from collections import defaultdict

from src.db_profile import DatabaseProfile, retrieve_values

_GENERIC = {"id", "name", "date", "time", "type", "status", "code", "value"}


def _norm(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _mentioned(name: str, text: str) -> bool:
    key = _norm(name)
    return len(key) >= 4 and key not in _GENERIC and key in _norm(text)


def render_profile_facts(
    profile: DatabaseProfile,
    question: str,
    evidence: str,
    *,
    max_facts: int = 4,
    include_values: bool = True,
) -> str:
    """Render at most four relevant physical facts; return nothing when none match."""
    text = f"{question} {evidence}"
    facts: list[str] = []

    # Name matches avoid dumping every formatted column in a wide database.
    matches = [
        c
        for c in profile.columns
        if c.text_format
        and (
            _mentioned(c.column, text)
            or (_mentioned(c.table, text) and _norm(c.column) in {"date", "time"})
        )
    ]
    for column in sorted(matches, key=lambda c: (c.table, c.column))[:2]:
        example = f"; example {column.examples[0]!r}" if column.examples else ""
        facts.append(
            f"- {column.table}.{column.column}: stored as text with "
            f"{column.text_format} formatting{example}."
        )

    if include_values:
        # An exact value location can distinguish look-alike columns. Show all matching
        # locations (up to three) rather than asserting one is canonical.
        quoted = {
            left or right
            for left, right in re.findall(
                r"(?<![A-Za-z0-9])'([^']{4,})'|(?<![A-Za-z0-9])\"([^\"]{4,})\"", text
            )
        }
        value_locations: dict[str, set[str]] = defaultdict(set)
        for table, colname, value in retrieve_values(profile, text, k=20):
            if value in quoted:
                value_locations[value].add(f"{table}.{colname}")
        for value, locations in list(value_locations.items())[:2]:
            if len(locations) == 1:
                facts.append(f"- Stored value {value!r} occurs in {', '.join(sorted(locations))}.")

    for join in profile.joins:
        if not join.parent_unique and (
            _mentioned(join.table, text) or _mentioned(join.parent_table, text)
        ):
            facts.append(
                f"- {join.table}.{join.column} joins {join.parent_table}."
                f"{join.parent_column}; the parent key is not unique."
            )
            break

    if not facts:
        return ""
    return "Database observations (from sampled data; use only if relevant):\n" + (
        "\n".join(facts[:max_facts]) + "\n\n"
    )
