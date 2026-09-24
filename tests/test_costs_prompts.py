import asyncio
import json
import sqlite3
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.costs import MODEL_GPT_OSS, BudgetExceeded, BudgetGuard, Reservation, cost_usd
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
        guard = BudgetGuard(0.0001, tmp_path / "spend.sqlite")
        reservation = await guard.reserve(MODEL_GPT_OSS, 100, 100)
        assert guard.reserved == reservation.amount_usd
        await guard.settle(reservation, 0.00001)
        assert guard.spent == pytest.approx(0.00001)
        with pytest.raises(BudgetExceeded):
            await guard.reserve(MODEL_GPT_OSS, 1_000_000, 1_000_000)

    asyncio.run(scenario())


def _spend_in_child(ledger: str, count: int) -> None:
    async def run() -> None:
        guard = BudgetGuard(100.0, Path(ledger))
        for _ in range(count):
            await guard.settle(await guard.reserve_usd(0.01, label="child"), 0.001)

    asyncio.run(run())


def _age_reservation(ledger: Path, token: str, seconds: float) -> None:
    with sqlite3.connect(ledger) as db:
        db.execute("UPDATE reservation SET at = at - ? WHERE token = ?", (seconds, token))


def test_ledger_is_shared_and_lossless_across_processes(tmp_path: Path) -> None:
    import multiprocessing

    ledger = tmp_path / "spend.sqlite"
    context = multiprocessing.get_context("spawn")
    workers = [context.Process(target=_spend_in_child, args=(str(ledger), 40)) for _ in range(3)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(60)
        assert worker.exitcode == 0
    guard = BudgetGuard(100.0, ledger)
    # The original JSON ledger recorded $0.04 of this $0.12 (each process overwrote the rest).
    assert guard.spent == pytest.approx(3 * 40 * 0.001)
    assert guard.reserved == 0.0


def test_reservations_are_visible_to_other_guards_and_sources_tracked(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        first, second = BudgetGuard(1.0, ledger), BudgetGuard(1.0, ledger)
        held = await first.reserve_usd(0.7, label="batch-estimate")
        assert second.remaining == pytest.approx(0.3)
        with pytest.raises(BudgetExceeded):
            await second.reserve_usd(0.5, label="jev")
        await first.settle(held, 0.2, source="fireworks-batch")
        jev = await second.reserve_usd(0.5, label="jev")
        await second.settle(jev, 0.01, source="openrouter")
        second.record_charge(0.05, source="fireworks-batch")
        assert first.spend_by_source() == pytest.approx(
            {"fireworks-batch": 0.25, "openrouter": 0.01}
        )

    asyncio.run(scenario())


def test_legacy_json_ledger_is_imported_once(tmp_path: Path) -> None:
    (tmp_path / "spend.json").write_text(
        json.dumps({"spent_usd": 0.35, "by_source": {"fireworks": 0.25, "openrouter": 0.1}})
    )
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    assert guard.spend_by_source() == pytest.approx({"fireworks": 0.25, "openrouter": 0.1})
    assert (tmp_path / "spend.json.migrated").exists()
    assert BudgetGuard(1.0, tmp_path / "spend.sqlite").spent == pytest.approx(0.35)


def test_dead_process_reservation_is_charged_provisionally(tmp_path: Path) -> None:
    ledger = tmp_path / "spend.sqlite"
    guard = BudgetGuard(1.0, ledger)
    with sqlite3.connect(ledger) as db:
        db.execute(
            "INSERT INTO reservation VALUES ('orphan', 0.1, ?, ?, 3600, '')",
            (2**22 + 12345, time.time()),
        )
    assert guard.reserved == 0.0
    assert guard.spend_by_source() == pytest.approx({"unsettled": 0.1})


def test_late_settle_reconciles_stale_charge_and_repeats_are_noops(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        guard = BudgetGuard(10.0, ledger)
        held = await guard.reserve_usd(0.20, label="long job")
        _age_reservation(ledger, held.token, 2 * 3600)  # outlived its 1h ttl
        assert guard.spent == pytest.approx(0.20)  # conservatively charged as provisional
        assert await guard.settle(held, 0.10, source="fireworks-batch") == pytest.approx(-0.10)
        assert guard.spent == pytest.approx(0.10)  # the JSON ledger recorded 0.30
        assert await guard.settle(held, 0.10, source="fireworks-batch") == 0.0
        assert guard.spent == pytest.approx(0.10)  # ...and then 0.40
        assert guard.spend_by_source() == pytest.approx({"fireworks-batch": 0.10})

    asyncio.run(scenario())


def test_unknown_outcome_stays_provisional_until_the_real_cost_arrives(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        guard = BudgetGuard(10.0, ledger)
        held = await guard.reserve_usd(0.20, label="lost reply")
        await guard.settle(held, None)  # outcome unknown: charged provisionally
        assert guard.spent == pytest.approx(0.20)
        await guard.settle(held, None)  # still unknown: no change
        assert guard.spent == pytest.approx(0.20)
        await guard.settle(held, 0.10, source="openrouter")  # v2.2 kept 0.20 here
        assert guard.spend_by_source() == pytest.approx({"openrouter": 0.10})

    asyncio.run(scenario())


def test_settlement_keys_are_durable_and_caller_keys_survive_restarts(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        submitter = BudgetGuard(10.0, ledger)
        batch = await submitter.reserve_usd(0.5, label="batch", key="batch-job-42", ttl_s=86400)
        again = await submitter.reserve_usd(0.5, label="batch", key="batch-job-42")
        assert again.token == batch.token and submitter.reserved == pytest.approx(0.5)
        # A different process (fresh guard) settles by key after a restart.
        collector = BudgetGuard(10.0, ledger)
        await collector.settle(collector.reservation("batch-job-42"), 0.3, source="fireworks-batch")
        # Much later, any repeat settle or re-reserve of the key changes nothing (v2.2 forgot
        # keys after 7 days and would have charged again).
        with sqlite3.connect(ledger) as db:
            db.execute("UPDATE settlement SET at = at - ?", (30 * 86400,))
        later = BudgetGuard(10.0, ledger)
        assert await later.settle(Reservation("batch-job-42", 0.0), 0.3) == 0.0
        assert (await later.reserve_usd(0.5, key="batch-job-42")).amount_usd == 0.0
        assert later.spent == pytest.approx(0.3) and later.reserved == 0.0

    asyncio.run(scenario())


def test_long_ttl_reservation_is_not_charged_early(tmp_path: Path) -> None:
    async def scenario() -> None:
        ledger = tmp_path / "spend.sqlite"
        guard = BudgetGuard(10.0, ledger)
        held = await guard.reserve_usd(0.5, label="batch", ttl_s=24 * 3600)
        _age_reservation(ledger, held.token, 2 * 3600)  # 2h old, well within 24h
        assert guard.spent == 0.0 and guard.reserved == pytest.approx(0.5)
        await guard.settle(held, 0.3, source="fireworks-batch")
        assert guard.spent == pytest.approx(0.3) and guard.reserved == 0.0

    asyncio.run(scenario())


def test_batch_pricing_is_half_of_serverless() -> None:
    serverless = cost_usd(MODEL_GPT_OSS, 1_000, 200, 500)
    assert cost_usd(MODEL_GPT_OSS, 1_000, 200, 500, batch=True) == pytest.approx(serverless / 2)
