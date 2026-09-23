import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.costs import MODEL_GPT_OSS, BudgetExceeded, BudgetGuard, cost_usd
from src.prompts import SQL_SCHEMA, SYSTEM_PROMPT, SQLResponse


def test_schema_supports_guardrail_responses_without_unsupported_constraints() -> None:
    schema = SQL_SCHEMA["json_schema"]["schema"]
    assert schema["required"] == ["response_type", "sql", "message"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"response_type", "sql", "message"}
    rendered = json.dumps(schema)
    for unsupported in ("minLength", "maxLength", "minItems", "maxItems", "pattern"):
        assert unsupported not in rendered
    response = SQLResponse.model_validate_json(
        '{"response_type":"query","sql":"SELECT 1","message":null}'
    )
    assert response.sql == "SELECT 1"
    with pytest.raises(ValidationError):
        SQLResponse.model_validate_json(
            '{"response_type":"query","sql":"SELECT 1","message":null,"extra":true}'
        )


def test_system_prompt_encodes_live_failure_guardrails() -> None:
    assert "illustrative examples only" in SYSTEM_PROMPT
    assert "Never equate unrelated identifier" in SYSTEM_PROMPT
    assert "Missing sample values must never cause unsupported" in SYSTEM_PROMPT
    # Threshold / above-average projection invariant (011/016 class).
    assert 'which X have more than N' in SYSTEM_PROMPT
    assert "above average" in SYSTEM_PROMPT
    assert "both the entity label and that measure" in SYSTEM_PROMPT
    assert "Existence/absence questions with no aggregate measure" in SYSTEM_PROMPT
    # Deterministic ranking + top-N secondary order (010 class).
    assert "deterministic secondary order" in SYSTEM_PROMPT
    assert "top-N, LIMIT, or" in SYSTEM_PROMPT and "ROW_NUMBER" in SYSTEM_PROMPT
    assert "Order those results by the measure first" in SYSTEM_PROMPT
    # Temporal: MoM uses YYYY-MM; month-of-year categories keep %m (006 class).
    assert "strftime('%Y-%m'" in SYSTEM_PROMPT
    assert "MoM/YoY" in SYSTEM_PROMPT
    assert "Month-of-year categories" in SYSTEM_PROMPT
    assert "strftime('%m'" in SYSTEM_PROMPT
    # Derived measure / MoM projection + rounding.
    assert "growth/change of a base measure" in SYSTEM_PROMPT
    assert "NULL growth for the first period" in SYSTEM_PROMPT
    assert "Round user-facing percentages" in SYSTEM_PROMPT
    assert "Never SELECT primary-key, foreign-key, or join-key columns" in SYSTEM_PROMPT
    assert "full measure-ordered breakdown" in SYSTEM_PROMPT
    assert "for each" in SYSTEM_PROMPT


def test_three_tier_cost() -> None:
    actual = cost_usd(MODEL_GPT_OSS, 1_000_000, 200_000, 100_000)
    # 800k uncached @ $0.15/1M + 200k cached @ $0.015/1M + 100k output @ $0.60/1M.
    assert actual == pytest.approx(0.183)


def test_reserve_then_settle(tmp_path: Path) -> None:
    async def scenario() -> None:
        guard = BudgetGuard(0.0001, tmp_path / "spend.json")
        reservation = await guard.reserve(MODEL_GPT_OSS, 100, 100)
        assert guard.reserved == reservation.amount_usd
        await guard.settle(reservation, 0.00001)
        assert guard.spent == pytest.approx(0.00001)
        with pytest.raises(BudgetExceeded):
            await guard.reserve(MODEL_GPT_OSS, 1_000_000, 1_000_000)

    asyncio.run(scenario())
