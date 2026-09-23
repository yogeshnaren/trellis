import json
from pathlib import Path
from typing import Any

import pytest

from src.agent import Agent
from src.conversation import ConversationContext
from src.costs import MODEL_GPT_OSS, BudgetGuard
from src.db import connect_readonly
from src.llm import LLMResult
from src.schema import get_schema


def llm(text: str) -> LLMResult:
    return LLMResult(text, 20, 2, 8, 10.0, 0.0, MODEL_GPT_OSS, 0.00001)


def test_agent_repairs_invalid_sql(tmp_path: Path) -> None:
    responses = iter(
        [
            llm(
                json.dumps(
                    {
                        "response_type": "query",
                        "sql": "SELECT ArtistId FROM Artist JOIN Album ON Artist.ArtistId = Album.ArtistId",
                        "message": None,
                    }
                )
            ),
            llm(
                json.dumps(
                    {
                        "response_type": "query",
                        "sql": "SELECT Name FROM Artist LIMIT 1",
                        "message": None,
                    }
                )
            ),
        ]
    )

    async def fake_complete(*args: Any, **kwargs: Any) -> LLMResult:
        return next(responses)

    async def scenario() -> None:
        conn = connect_readonly()
        try:
            agent = Agent(
                MODEL_GPT_OSS,
                conn,
                BudgetGuard(1.0, tmp_path / "spend.json"),
                complete_fn=fake_complete,
            )
            ctx = ConversationContext(get_schema())
            result = await agent.ask("Name an artist", ctx)
            assert result.ok and result.repaired
            assert result.rows
            assert len(ctx.turns) == 1
            history = ctx.build_messages("Another one")
            assert "SELECT Name FROM Artist" in history[2]["content"]
            assert all("AC/DC" not in message["content"] for message in history)
        finally:
            conn.close()

    import asyncio

    asyncio.run(scenario())


def test_structured_output_failure(tmp_path: Path) -> None:
    async def fake_complete(*args: Any, **kwargs: Any) -> LLMResult:
        return llm(
            '{"response_type":"query","sql":"SELECT 1","message":null,"explanation":"extra"}'
        )

    async def scenario() -> None:
        conn = connect_readonly()
        try:
            result = await Agent(
                MODEL_GPT_OSS,
                conn,
                BudgetGuard(1.0, tmp_path / "spend.json"),
                complete_fn=fake_complete,
            ).ask("one", ConversationContext(get_schema()))
            assert result.error_category == "structured-output-failed"
        finally:
            conn.close()

    import asyncio

    asyncio.run(scenario())


@pytest.mark.parametrize("response_type", ["unsupported", "clarify"])
def test_non_query_response_never_reaches_sql_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response_type: str
) -> None:
    async def fake_complete(*args: Any, **kwargs: Any) -> LLMResult:
        return llm(
            json.dumps(
                {
                    "response_type": response_type,
                    "sql": None,
                    "message": "Please ask about the music database.",
                }
            )
        )

    def fail_if_called(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        pytest.fail("SQL safety, validation, and execution pipeline must not be called")

    monkeypatch.setattr("src.agent.is_safe", fail_if_called)

    async def scenario() -> None:
        conn = connect_readonly()
        try:
            ctx = ConversationContext(get_schema())
            result = await Agent(
                MODEL_GPT_OSS,
                conn,
                BudgetGuard(1.0, tmp_path / f"{response_type}-spend.json"),
                complete_fn=fake_complete,
            ).ask("How is the weather?", ctx)
            assert result.ok
            assert result.response_type == response_type
            assert result.sql is None and result.rows is None
            assert result.message
            assert not ctx.turns
        finally:
            conn.close()

    import asyncio

    asyncio.run(scenario())
