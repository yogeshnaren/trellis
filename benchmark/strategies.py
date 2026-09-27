"""Prompting strategies for building a diverse candidate bank (SOTA plan rank 4).

Each strategy is a short instruction placed before the question in the user message, so
the per-database system prompt (and its prompt cache) is unchanged. They exist to produce
*different* candidates for pass@K and selection, not to replace the direct strategy.
Strategies that plan first need thinking room: run them with reasoning enabled.
"""

STRATEGIES: dict[str, str] = {
    "direct": "",
    "decompose": (
        "Approach: split the question into its sub-questions. For each, decide which table, "
        "column and filter answers it, then combine them into one final query. Keep the "
        "final query as simple as the combined answer allows.\n\n"
    ),
    "plan": (
        "Approach: before writing SQL, plan it step by step: (1) exactly which columns the "
        "question asks to return, (2) the tables and join path, (3) every filter stated in "
        "the question and the hint, (4) grouping and aggregation, (5) ordering and limit. "
        "Then write one query that follows the plan exactly.\n\n"
    ),
}
