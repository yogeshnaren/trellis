"""Jev's typed-response and provider-budget safeguards; no external calls."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from src.costs import MODEL_GPT_OSS, BudgetExceeded, BudgetGuard
from src.jev import JevClient, JevConfig, JevError


def _question() -> dict[str, dict[str, Any]]:
    return {
        "has_constraint": {
            "type": "noul",
            "instructions": "Is the city filter represented?",
            "criteria": {"true": "SQL filters the requested city", "false": "It does not"},
        }
    }


def test_openrouter_caps_are_independent_of_fireworks_and_shared(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        a, b = BudgetGuard(0.05, ledger), BudgetGuard(0.05, ledger)
        first = await a.reserve_openrouter_usd(
            0.01, provider_ceiling_usd=0.02, session_ceiling_usd=0.01, session_id="one"
        )
        assert b.remaining_for("openrouter", 0.02) == pytest.approx(0.01)
        with pytest.raises(BudgetExceeded, match="session"):
            await b.reserve_openrouter_usd(
                0.01, provider_ceiling_usd=0.02, session_ceiling_usd=0.01, session_id="one"
            )
        second = await b.reserve_openrouter_usd(
            0.01, provider_ceiling_usd=0.02, session_ceiling_usd=0.01, session_id="two"
        )
        with pytest.raises(BudgetExceeded, match="total"):
            await b.reserve_openrouter_usd(
                0.01, provider_ceiling_usd=0.02, session_ceiling_usd=0.01, session_id="three"
            )
        await a.settle(first, 0.005, source="openrouter")
        await b.settle(second, 0.005, source="openrouter")
        assert a.spend_by_source()["openrouter"] == pytest.approx(0.01)
        # Fireworks reserves against its own $0.05 cap, not OpenRouter's spend.
        fireworks = await a.reserve(MODEL_GPT_OSS, 1_000, 100)
        await a.settle(fireworks, 0.001, source="fireworks")
        assert a.remaining_for("fireworks", 0.05) == pytest.approx(0.049)

    asyncio.run(scenario())


def test_openrouter_unknown_cost_stays_within_its_cap(tmp_path: Path) -> None:
    async def scenario() -> None:
        guard = BudgetGuard(1, tmp_path / "spend.sqlite")
        held = await guard.reserve_openrouter_usd(
            0.01, provider_ceiling_usd=0.01, session_ceiling_usd=0.01, session_id="s"
        )
        await guard.settle(held, None, source="openrouter")
        assert guard.remaining_for("openrouter", 0.01) == 0
        with pytest.raises(BudgetExceeded):
            await guard.reserve_openrouter_usd(
                0.01, provider_ceiling_usd=0.01, session_ceiling_usd=0.01, session_id="s"
            )
        await guard.settle(held, 0.002, source="openrouter")
        assert guard.remaining_for("openrouter", 0.01) == pytest.approx(0.008)

    asyncio.run(scenario())


def test_typed_jev_call_settles_actual_usage(tmp_path: Path) -> None:
    async def scenario() -> None:
        guard = BudgetGuard(0.01, tmp_path / "spend.sqlite")
        config = JevConfig("secret", "typesafe/jev-1.13", 0.02, 0.01)
        seen: dict[str, Any] = {}

        def transport(payload: bytes, key: str, timeout: float) -> dict[str, Any]:
            seen.update(json.loads(payload))
            assert key == "secret" and timeout == 30
            return {
                "id": "call-1",
                "model": "typesafe/jev-1.13-20260917",
                "answers": {"has_constraint": {"type": "noul", "noul": 0.91}},
                "usage": {"cost": 0.00008, "input_tokens": 1900, "output_tokens": 20},
            }

        result = await JevClient(config, guard, session_id="pilot", transport=transport).decide(
            {"question": "Which city?", "sql": "SELECT city FROM t"}, _question()
        )
        assert seen["model"] == config.model
        assert result.answers["has_constraint"]["noul"] == pytest.approx(0.91)
        assert result.cost_usd == pytest.approx(0.00008)
        assert guard.spend_by_source()["openrouter"] == pytest.approx(0.00008)
        assert guard.reserved == 0

    asyncio.run(scenario())


def test_jev_error_keeps_a_provisional_charge_and_falls_back(tmp_path: Path) -> None:
    async def scenario() -> None:
        guard = BudgetGuard(0.01, tmp_path / "spend.sqlite")
        config = JevConfig("secret", "typesafe/jev-1.13", 0.02, 0.02)

        def fails(_payload: bytes, _key: str, _timeout: float) -> dict[str, Any]:
            raise TimeoutError("network ambiguity")

        with pytest.raises(JevError, match="deterministic fallback"):
            await JevClient(config, guard, session_id="pilot", transport=fails).decide(
                {"question": "Question"}, _question()
            )
        assert guard.spend_by_source()["unsettled"] == pytest.approx(0.01)
        assert guard.remaining_for("openrouter", 0.02) == pytest.approx(0.01)

    asyncio.run(scenario())


def test_new_openrouter_session_variable_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.setenv("OPENROUTER_MODEL", "typesafe/jev-1.13")
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "5")
    monkeypatch.delenv("OPENROUTER_SESSION_BUDGET_USD", raising=False)
    monkeypatch.setenv("SESSION_BUDGET_USD", "1")
    with pytest.raises(ValueError, match="OpenRouter total and session budgets"):
        JevConfig.from_env()
    monkeypatch.setenv("OPENROUTER_SESSION_BUDGET_USD", "1")
    assert JevConfig.from_env().session_cap_usd == 1


def test_selector_state_has_verified_schema_and_no_gold(tmp_path: Path) -> None:
    import sqlite3

    from benchmark.bird import BirdQuestion
    from benchmark.jev_selector_shadow import make_request

    db_dir = tmp_path / "train_databases"
    db_path = db_dir / "sample" / "sample.sqlite"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, city TEXT)")
    question = BirdQuestion(1, "sample", "Which city?", "", "SELECT secret_gold", "unknown", 0)
    records = {
        "direct": {"sql": "SELECT city FROM items", "rows": [["A"]], "official_ex": False},
        "plan": {"sql": "SELECT id FROM items", "rows": [[1]], "official_ex": True},
    }
    state, spec, mapping = make_request(
        question, records, {"direct": "sig-a", "plan": "sig-b"}, db_dir
    )
    encoded = json.dumps(state)
    assert "secret_gold" not in encoded
    assert "official_ex" not in encoded
    assert state["schema_shortlist"] == {"items": ["id", "city"]}
    assert mapping == {"A": "direct", "B": "plan"}
    assert spec["best"]["type"] == "choice"


def test_hint_and_intent_requests_keep_gold_out() -> None:
    from benchmark.bird import BirdQuestion
    from benchmark.jev_hint_shadow import request as hint_request
    from benchmark.jev_intent_shadow import request as intent_request

    question = BirdQuestion(
        1,
        "sample",
        "Which row has the highest score?",
        "highest refers to max(score)",
        "SELECT secret_gold",
        "unknown",
        0,
    )
    hint_state, hint_spec = hint_request(question, "highest refers to max(score)")
    intent_state, intent_spec = intent_request(question)
    assert "secret_gold" not in json.dumps(hint_state)
    assert "secret_gold" not in json.dumps(intent_state)
    assert hint_spec["role"]["type"] == "choice"
    assert all(spec["type"] == "noul" for spec in intent_spec.values())


def test_table_request_includes_verified_join_edges_without_gold(tmp_path: Path) -> None:
    import sqlite3

    from benchmark.bird import BirdQuestion
    from benchmark.jev_table_shadow import request

    db_path = tmp_path / "sample.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE country (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute(
            "CREATE TABLE player (id INTEGER PRIMARY KEY, country_id INTEGER "
            "REFERENCES country(id))"
        )
    question = BirdQuestion(1, "sample", "Which country?", "", "SELECT secret_gold", "unknown", 0)
    state, specs = request(question, ["player", "country"], db_path, with_fk=True)
    assert state["verified_foreign_keys"] == ["player.country_id -> country.id"]
    assert "secret_gold" not in json.dumps(state)
    assert set(specs) == {"table_0", "table_1"}
