"""Minimal SQL-only conversation memory."""

import json
from collections import deque
from dataclasses import dataclass

from src.prompts import SYSTEM_PROMPT


@dataclass(frozen=True)
class Turn:
    question: str
    sql: str
    row_count: int
    truncated: bool


class ConversationContext:
    def __init__(self, schema: str, max_turns: int = 4):
        self.schema = schema
        self.turns: deque[Turn] = deque(maxlen=max_turns)

    def build_messages(self, question: str) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(schema=self.schema)}]
        for turn in self.turns:
            note = f"at least {turn.row_count}" if turn.truncated else str(turn.row_count)
            messages.extend(
                [
                    {"role": "user", "content": turn.question},
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "response_type": "query",
                                "sql": turn.sql,
                                "message": None,
                            }
                        )
                        + f"\nRows returned: {note}.",
                    },
                ]
            )
        messages.append({"role": "user", "content": question})
        return messages

    def record(self, turn: Turn) -> None:
        self.turns.append(turn)

    def clear(self) -> None:
        self.turns.clear()
