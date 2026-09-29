"""Deterministic pattern tags for BIRD questions and answers (accuracy review).

Every tag is computed from the question, its evidence, the gold SQL, the saved answer
record or the database schema: no model calls. Tags describe *associations* with
correctness, never causes. Gold-SQL features follow the v2 postmortem tagger
(docs/postmortem_v2/analysis/pm3_features.py).
"""

from __future__ import annotations

import re
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

# Tag families shown in the report, with plain-language names.
FAMILIES = {
    "sql": "Gold SQL feature",
    "intent": "Question intent",
    "evidence": "Evidence (hint) type",
    "shape": "Answer-key result shape",
    "outcome": "Our answer: outcome",
    "signal": "Pipeline signal",
    "size": "Schema size",
}

_SUPERLATIVE = re.compile(
    r"\b(highest|lowest|most|least|top|maximum|minimum|best|worst|oldest|youngest|largest|"
    r"smallest|longest|shortest|first|latest|earliest)\b"
)
_TEMPORAL = re.compile(
    r"\b(year|month|date|day|between|before|after|since|during)\b|\b(19|20)\d{2}\b"
)
_RATIO_Q = re.compile(r"percent|ratio|proportion|\brate\b|average|\bavg\b")
_MULTI_ASK = re.compile(
    r"\band\b.*\b(also|list|give|show|indicate|provide|state)\b|\bhow (much|many).*\band\b"
)
_LIST_Q = re.compile(r"^(list|name|give|show|provide|what are|which)\b")
_YESNO_Q = re.compile(r"^(is|are|does|do|did|was|were|has|have)\b")
_COMPARE_Q = re.compile(r"\b(more than|less than|greater|fewer|compare|difference|higher than|lower than)\b")
_FORMULA_EV = re.compile(r"divide|/|\*|sum\(|count\(|avg\(|max\(|min\(|percent|ratio|subtract|minus")
_VALUE_EV = re.compile(r"=\s*'|refers to\s+\w+\s*=|\bis\s+'")
_SYNONYM_EV = re.compile(r"\brefers? to\b|\bmeans?\b|\bstands? for\b")
_DATE_FN = re.compile(r"strftime|substr\(|julianday|date\(|year\(")


def _tree(sql: str) -> Any:
    try:
        return parse_one(sql, read="sqlite")
    except (SqlglotError, ValueError):
        return None


def gold_sql_tags(gold_sql: str) -> list[str]:
    """Structural features of the answer key's SQL."""
    tree = _tree(gold_sql)
    lowered = gold_sql.lower()
    if tree is None:
        return ["sql: unparsed"]
    tags: list[str] = []
    joins = len(list(tree.find_all(exp.Join)))
    tags.append(f"sql: joins {min(joins, 3)}{'+' if joins >= 3 else ''}")
    checks = {
        "sql: subquery": len(list(tree.find_all(exp.Select))) > 1,
        "sql: GROUP BY": tree.find(exp.Group) is not None,
        "sql: HAVING": tree.find(exp.Having) is not None,
        "sql: ORDER BY + LIMIT": tree.find(exp.Limit) is not None and tree.find(exp.Order) is not None,
        "sql: window function": tree.find(exp.Window) is not None,
        "sql: CASE / IIF": tree.find(exp.Case) is not None or "iif(" in lowered,
        "sql: CAST": tree.find(exp.Cast) is not None,
        "sql: DISTINCT": tree.find(exp.Distinct) is not None,
        "sql: aggregate": tree.find(exp.AggFunc) is not None,
        "sql: LIKE": tree.find(exp.Like) is not None,
        "sql: set operator": tree.find(exp.Union, exp.Intersect, exp.Except) is not None,
        "sql: date function": bool(_DATE_FN.search(lowered)),
        "sql: division": tree.find(exp.Div) is not None,
    }
    tags += [name for name, present in checks.items() if present]
    return tags


def question_tags(question: str, evidence: str) -> list[str]:
    """What the question asks for, and what kind of hint it carries."""
    q = question.lower().strip()
    ev = (evidence or "").lower()
    tags: list[str] = []
    intents = {
        "intent: count": "how many" in q or "number of" in q,
        "intent: superlative": bool(_SUPERLATIVE.search(q)),
        "intent: ratio / percent / average": bool(_RATIO_Q.search(q)),
        "intent: temporal": bool(_TEMPORAL.search(q)),
        "intent: list / name": bool(_LIST_Q.search(q)),
        "intent: yes / no": bool(_YESNO_Q.search(q)),
        "intent: comparison": bool(_COMPARE_Q.search(q)),
        "intent: several asks": bool(_MULTI_ASK.search(q)),
    }
    tags += [name for name, present in intents.items() if present]
    if not ev.strip():
        tags.append("evidence: none")
    else:
        if _FORMULA_EV.search(ev):
            tags.append("evidence: formula")
        if _VALUE_EV.search(ev):
            tags.append("evidence: value mapping")
        if _SYNONYM_EV.search(ev):
            tags.append("evidence: definition / synonym")
        if len(ev) > 150:
            tags.append("evidence: long (>150 chars)")
    return tags


def gold_shape_tags(gold_rows: list[tuple[Any, ...]] | None) -> list[str]:
    """Shape of the answer key's own result (needs one local gold execution)."""
    if gold_rows is None:
        return ["shape: answer key fails or times out locally"]
    if not gold_rows:
        return ["shape: answer key returns nothing"]
    tags = []
    if all(value is None for row in gold_rows for value in row):
        tags.append("shape: answer key is all NULL")
    tags.append("shape: single value" if len(gold_rows) == 1 and len(gold_rows[0]) == 1
                else "shape: one row, several columns" if len(gold_rows) == 1
                else "shape: several rows")
    return tags


def outcome_tag(record: dict[str, Any], gold_rows: list[tuple[Any, ...]] | None, correct: bool) -> str:
    """How our saved answer relates to the answer key (a *review signal*, not a cause)."""
    if correct:
        return "outcome: correct"
    if record.get("error") is not None or record.get("response_type") not in (None, "query"):
        return "outcome: no SQL delivered"
    if gold_rows is None:
        return "outcome: answer key fails locally"
    ours = int(record.get("result_row_count") or 0)
    if gold_rows and ours == 0:
        return "outcome: we return nothing"
    ours_cols = len(record.get("columns") or [])
    gold_cols = len(gold_rows[0]) if gold_rows else ours_cols
    if ours_cols > gold_cols:
        return "outcome: extra columns"
    if ours_cols < gold_cols:
        return "outcome: fewer columns"
    if ours != len(set(gold_rows)) and ours != len(gold_rows):
        return "outcome: different row count"
    return "outcome: same shape, different values"


def signal_tags(record: dict[str, Any], facts_delivered: bool | None) -> list[str]:
    """Pipeline events recorded on the answer."""
    tags = []
    if record.get("repaired"):
        tags.append("signal: repair fired")
    if record.get("truncation_retried"):
        tags.append("signal: truncation retry fired")
    if record.get("empty_retried"):
        tags.append("signal: empty-result retry fired")
    if record.get("truncated"):
        tags.append("signal: output truncated")
    if facts_delivered is True:
        tags.append("signal: database facts in prompt")
    elif facts_delivered is False:
        tags.append("signal: no database facts in prompt")
    seconds = float(record.get("t_total_ms") or 0) / 1000
    if seconds > 5:
        tags.append("signal: latency >5s")
    return tags


def size_tag(n_tables: int, n_columns: int) -> str:
    if n_columns <= 30:
        return "size: small schema (≤30 columns)"
    if n_columns <= 80:
        return "size: medium schema (31–80 columns)"
    return "size: large schema (>80 columns)"


def family(tag: str) -> str:
    """Family key of a tag, from its prefix."""
    prefix = tag.split(":", 1)[0]
    return {"sql": "sql", "intent": "intent", "evidence": "evidence", "shape": "shape",
            "outcome": "outcome", "signal": "signal", "size": "size"}.get(prefix, "other")
