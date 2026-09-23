"""Cheap compatibility gate to run before the paid model bake-off."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from src.costs import MODEL_GPT_OSS, MODELS, get_shared_budget
from src.llm import complete
from src.prompts import SQL_SCHEMA, SQLResponse


def assert_exact_sql_response(text: str) -> str:
    """Require a valid ``SQLResponse`` with non-empty ``sql`` (the live agent's own contract)."""
    if not text.strip():
        raise ValueError("Empty response content (model likely spent max_tokens on reasoning)")
    try:
        payload = SQLResponse.model_validate_json(text)
    except ValidationError as exc:
        raise ValueError(f"Response did not match SQLResponse: {exc}") from exc
    if not payload.sql or not payload.sql.strip():
        raise ValueError(f"Expected non-empty sql for a query response, got: {text!r}")
    return payload.sql


async def _probe(
    mode: str,
    messages: list[dict[str, str]],
    model: str,
    guard: Any,
    *,
    max_tokens: int = 150,
    request_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one preflight completion; never raise, always return a diagnostic record."""
    try:
        result = await complete(
            messages,
            model,
            response_format=SQL_SCHEMA,
            max_tokens=max_tokens,
            budget=guard,
            request_options=request_options,
        )
    except Exception as exc:  # noqa: BLE001 - preflight must survive any single failure
        return {"mode": mode, "model": model, "conforms": False, "error": str(exc)}

    record = {"mode": mode, "conforms": True, **asdict(result)}
    try:
        assert_exact_sql_response(result.text)
    except ValueError as exc:
        record["conforms"] = False
        record["error"] = str(exc)
    return record


async def run_preflight(models: list[str], budget_usd: float) -> list[dict[str, Any]]:
    if not os.getenv("FIREWORKS_API_KEY"):
        raise SystemExit(
            "BLOCKED: FIREWORKS_API_KEY is absent. Run:\n"
            "export FIREWORKS_API_KEY=<your-key>\n"
            "uv run python -m benchmark.preflight --budget 0.05"
        )
    guard = get_shared_budget(budget_usd)
    messages = [{"role": "user", "content": "Return SQLite SQL that selects the integer 1."}]
    records: list[dict[str, Any]] = []
    for model in models:
        records.append(await _probe("configured", messages, model, guard))
        if model == MODEL_GPT_OSS:
            records.append(
                await _probe(
                    "medium-control",
                    messages,
                    model,
                    guard,
                    request_options={"reasoning_effort": "medium"},
                )
            )
    return records


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--budget", type=float, default=0.05)
    args = parser.parse_args()
    records = asyncio.run(run_preflight(args.models, args.budget))
    output = Path("benchmark/results/preflight.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2) + "\n")
    print(f"Wrote {output}\n")

    for record in records:
        status = "OK" if record.get("conforms") else "FAIL"
        model = record.get("model", "?")
        mode = record.get("mode", "?")
        if record.get("conforms"):
            print(
                f"[{status}] {model} ({mode}): "
                f"{record.get('output_tokens', '?')} output tokens, "
                f"{record.get('latency_ms', 0):.0f}ms"
            )
        else:
            print(f"[{status}] {model} ({mode}): {record.get('error')}")


if __name__ == "__main__":
    main()
