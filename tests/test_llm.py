"""The one function that spends money: reserve, call, retry, settle. No network calls."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from src import llm
from src.costs import MODEL_GPT_OSS, BudgetExceeded, BudgetGuard, cost_usd

OPENROUTER_MODEL = "openrouter/qwen/qwen3-coder-next"


def _response(usage: Any) -> Any:
    message = SimpleNamespace(content='{"ok": true}', reasoning_content=None)
    return SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _usage(prompt: int = 1_000, cached: int = 200, completion: int = 50) -> Any:
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                           prompt_tokens_details=SimpleNamespace(cached_tokens=cached))


def _status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.invalid"))
    return cls(f"status {status}", response=response, body=None)


class FakeClient:
    """Stands in for AsyncOpenAI: each call takes the next outcome (a response or an error)."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Provider:
    """Serves a FakeClient for every provider and records which providers were asked for."""

    def __init__(self) -> None:
        self.client: FakeClient | None = None
        self.used: list[str] = []

    def serve(self, *outcomes: Any) -> FakeClient:
        self.client = FakeClient(*outcomes)
        return self.client

    def shared_client(self, provider: str = "fireworks") -> FakeClient:
        self.used.append(provider)
        assert self.client is not None
        return self.client


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> Provider:
    fake = Provider()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(llm, "shared_client", fake.shared_client)
    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    return fake


def _complete(guard: BudgetGuard, model: str = MODEL_GPT_OSS) -> llm.LLMResult:
    messages = [{"role": "user", "content": "q" * 300}]
    return asyncio.run(llm.complete(messages, model, budget=guard, max_tokens=400, timeout_s=7.0))


@pytest.mark.parametrize("usage", [
    _usage(),
    # Some OpenAI-compatible servers return cached tokens only as an unknown extra field.
    SimpleNamespace(prompt_tokens=1_000, completion_tokens=50, prompt_tokens_details=None,
                    model_extra={"prompt_tokens_details": {"cached_tokens": 200}}),
])
def test_success_settles_the_actual_three_tier_cost(tmp_path: Path, provider: Provider, usage: Any) -> None:
    fake = provider.serve(_response(usage))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    result = _complete(guard)
    expected = cost_usd(MODEL_GPT_OSS, 1_000, 200, 50)
    assert (result.input_tokens, result.cached_tokens, result.output_tokens) == (1_000, 200, 50)
    assert result.cost_usd == pytest.approx(expected) and result.retry_ms == 0.0
    assert guard.spend_by_source() == pytest.approx({"fireworks": expected})
    assert guard.reserved == 0.0
    sent = fake.calls[0]
    assert sent["model"] == MODEL_GPT_OSS and sent["max_tokens"] == 400 and sent["timeout"] == 7.0
    assert sent["reasoning_effort"] == "low"


@pytest.mark.parametrize("error", [
    _status_error(openai.RateLimitError, 429),
    _status_error(openai.InternalServerError, 500),
])
def test_one_transient_failure_is_retried(tmp_path: Path, provider: Provider, error: Exception) -> None:
    fake = provider.serve(error, _response(_usage()))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    result = _complete(guard)
    assert len(fake.calls) == 2 and result.text == '{"ok": true}'
    assert guard.spend_by_source() == pytest.approx({"fireworks": result.cost_usd})


def test_a_second_transient_failure_raises_and_charges_provisionally(tmp_path: Path, provider: Provider) -> None:
    fake = provider.serve(_status_error(openai.RateLimitError, 429), _status_error(openai.RateLimitError, 429))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    with pytest.raises(openai.RateLimitError):
        _complete(guard)
    assert len(fake.calls) == 2
    # Outcome unknown: the reservation is kept as a provisional charge, not dropped.
    spend = guard.spend_by_source()
    assert set(spend) == {"unsettled"} and spend["unsettled"] > 0 and guard.reserved == 0.0


def test_other_errors_are_not_retried(tmp_path: Path, provider: Provider) -> None:
    fake = provider.serve(_status_error(openai.BadRequestError, 400), _response(_usage()))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    with pytest.raises(openai.BadRequestError):
        _complete(guard)
    assert len(fake.calls) == 1 and set(guard.spend_by_source()) == {"unsettled"}


def test_openrouter_calls_charge_the_openrouter_cap(
    tmp_path: Path, provider: Provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "1")
    monkeypatch.setenv("OPENROUTER_SESSION_BUDGET_USD", "1")
    fake = provider.serve(_response(_usage(cached=0)))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    result = _complete(guard, OPENROUTER_MODEL)
    assert provider.used == ["openrouter"]
    assert fake.calls[0]["model"] == "qwen/qwen3-coder-next"
    assert fake.calls[0]["extra_body"]["provider"]["require_parameters"] is True
    assert result.cost_usd > 0
    assert guard.spend_by_source() == pytest.approx({"openrouter": result.cost_usd})


def test_local_models_are_free_and_unreserved(tmp_path: Path, provider: Provider) -> None:
    provider.serve(_response(_usage()))
    guard = BudgetGuard(1.0, tmp_path / "spend.sqlite")
    result = _complete(guard, "local/arctic-7b")
    assert provider.used == ["local"] and result.cost_usd == 0.0
    assert guard.spend_by_source() == {} and guard.spent == 0.0


def test_an_exhausted_budget_stops_before_the_provider_is_called(tmp_path: Path, provider: Provider) -> None:
    fake = provider.serve(_response(_usage()))
    guard = BudgetGuard(1e-9, tmp_path / "spend.sqlite")
    with pytest.raises(BudgetExceeded):
        _complete(guard)
    assert fake.calls == [] and guard.spent == 0.0
