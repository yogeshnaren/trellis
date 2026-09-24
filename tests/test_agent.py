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
                BudgetGuard(1.0, tmp_path / "spend.sqlite"),
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
                BudgetGuard(1.0, tmp_path / "spend.sqlite"),
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
                BudgetGuard(1.0, tmp_path / f"{response_type}-spend.sqlite"),
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


def _query(sql: str | None, response_type: str = "query", message: str | None = None) -> LLMResult:
    return llm(json.dumps({"response_type": response_type, "sql": sql, "message": message}))


def _run(
    tmp_path: Path, responses: list[LLMResult], *, repairs: bool, question: str = "q"
) -> tuple[Any, list[list[dict[str, str]]]]:
    import asyncio

    queue = iter(responses)
    seen: list[list[dict[str, str]]] = []

    async def fake_complete(messages: list[dict[str, str]], *args: Any, **kwargs: Any) -> LLMResult:
        seen.append(list(messages))
        return next(queue)

    async def scenario() -> Any:
        conn = connect_readonly()
        try:
            agent = Agent(
                MODEL_GPT_OSS,
                conn,
                BudgetGuard(1.0, tmp_path / "spend.sqlite"),
                complete_fn=fake_complete,
                pipeline_repairs=repairs,
            )
            return await agent.ask(question, ConversationContext(get_schema()))
        finally:
            conn.close()

    return asyncio.run(scenario()), seen


def test_pipeline_repairs_are_off_by_default(tmp_path: Path) -> None:
    result, seen = _run(tmp_path, [_query("SELECT Nme FROM Artist")], repairs=False)
    assert result.error_category == "safety-rejected" and len(seen) == 1
    result, seen = _run(
        tmp_path, [_query(None, "unsupported", "not in schema")], repairs=False
    )
    assert result.response_type == "unsupported" and len(seen) == 1


def test_unknown_identifier_rejection_is_repaired_with_a_hint(tmp_path: Path) -> None:
    result, seen = _run(
        tmp_path,
        [_query("SELECT Nme FROM Artist"), _query("SELECT Name FROM Artist LIMIT 1")],
        repairs=True,
    )
    assert result.ok and result.repaired and result.rows
    assert "Did you mean: Name" in seen[1][-1]["content"]


def test_forbidden_sql_is_never_retried(tmp_path: Path) -> None:
    result, seen = _run(tmp_path, [_query("DELETE FROM Artist")], repairs=True)
    assert result.error_category == "safety-rejected" and len(seen) == 1


def test_refusal_is_retried_once_as_answerable(tmp_path: Path) -> None:
    result, seen = _run(
        tmp_path,
        [_query(None, "unsupported", "no such data"), _query("SELECT Name FROM Artist LIMIT 1")],
        repairs=True,
    )
    assert result.ok and result.refusal_retried and result.rows
    assert "answerable" in seen[1][-1]["content"]
    result, seen = _run(
        tmp_path,
        [_query(None, "unsupported", "no"), _query(None, "unsupported", "still no")],
        repairs=True,
    )
    assert result.response_type == "unsupported" and len(seen) == 2


def test_empty_result_retry_only_replaces_with_a_non_empty_answer(tmp_path: Path) -> None:
    empty = "SELECT Name FROM Artist WHERE Name = 'nobody'"
    fixed, _ = _run(
        tmp_path, [_query(empty), _query("SELECT Name FROM Artist WHERE Name LIKE 'AC%'")],
        repairs=True,
    )
    assert fixed.ok and fixed.empty_retried and fixed.rows and "LIKE" in (fixed.sql or "")
    for bad_retry in (_query("DELETE FROM Artist"), _query("SELECT Nope FROM Artist"),
                      _query(empty), _query("SELECT Name FROM Artist WHERE 0")):
        kept, _ = _run(tmp_path, [_query(empty), bad_retry], repairs=True)
        # Any unsafe, invalid, unchanged, or still-empty retry keeps the original answer.
        assert kept.ok and kept.sql == empty and kept.rows == []
