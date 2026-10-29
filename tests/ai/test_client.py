import json

import httpx
import pytest

from fitbit_app.ai.client import LLM
from fitbit_app.ai.schemas import DailyBrief
from fitbit_app.config import Settings
from fitbit_app.errors import AIResponseError, AIUnavailableError
from fixtures.fake_llm import SAMPLES, FakeOllamaClient

VALID = SAMPLES[DailyBrief].model_dump_json()
MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture
def ai_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_enabled": True, "ollama_model": "qwen3.5:9b"})


async def test_uses_configured_model(ai_settings: Settings) -> None:
    llm = LLM(ai_settings, FakeOllamaClient())
    assert await llm.resolve_model() == "qwen3.5:9b"


async def test_falls_back_when_main_model_missing(ai_settings: Settings) -> None:
    settings = ai_settings.model_copy(update={"ollama_fallback_model": "llama3.1:8b"})
    llm = LLM(settings, FakeOllamaClient(models=["llama3.1:8b"]))
    assert await llm.resolve_model() == "llama3.1:8b"


@pytest.mark.parametrize(
    "client",
    [FakeOllamaClient(models=[]), FakeOllamaClient(list_error=httpx.ConnectError("refused"))],
)
async def test_unavailable(ai_settings: Settings, client: FakeOllamaClient) -> None:
    with pytest.raises(AIUnavailableError):
        await LLM(ai_settings, client).resolve_model()


async def test_disabled(settings: Settings) -> None:
    with pytest.raises(AIUnavailableError, match="disabled"):
        await LLM(settings, FakeOllamaClient()).resolve_model()


async def test_structured_output(ai_settings: Settings) -> None:
    client = FakeOllamaClient(replies=[VALID])
    result = await LLM(ai_settings, client).generate(MESSAGES, DailyBrief)
    assert result == SAMPLES[DailyBrief]
    call = client.chat_calls[0]
    assert call["format"] == DailyBrief.model_json_schema()
    assert call["stream"] is False
    assert call["think"] is False
    assert call["options"]["num_ctx"] == ai_settings.ollama_num_ctx


async def test_accepts_fenced_output(ai_settings: Settings) -> None:
    client = FakeOllamaClient(replies=[f"```json\n{VALID}\n```"])
    result = await LLM(ai_settings, client).generate(MESSAGES, DailyBrief)
    assert result == SAMPLES[DailyBrief]
    assert len(client.chat_calls) == 1


async def test_retries_once_on_invalid_output(ai_settings: Settings) -> None:
    client = FakeOllamaClient(replies=['{"headline": "x"}', VALID])
    result = await LLM(ai_settings, client).generate(MESSAGES, DailyBrief)
    assert result.headline == SAMPLES[DailyBrief].headline  # type: ignore[attr-defined]
    retry_messages = client.chat_calls[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": '{"headline": "x"}'}
    assert "JSON schema" in retry_messages[-1]["content"]


async def test_gives_up_after_second_invalid_output(ai_settings: Settings) -> None:
    client = FakeOllamaClient(replies=["not json", json.dumps({"tips": []})])
    with pytest.raises(AIResponseError):
        await LLM(ai_settings, client).generate(MESSAGES, DailyBrief)


async def test_drops_think_flag_for_models_without_it(ai_settings: Settings) -> None:
    client = FakeOllamaClient(replies=[VALID, VALID], reject_think=True)
    llm = LLM(ai_settings, client)
    await llm.generate(MESSAGES, DailyBrief)
    await llm.generate(MESSAGES, DailyBrief)
    assert "think" in client.chat_calls[0]
    assert all("think" not in call for call in client.chat_calls[1:])


async def test_stream(ai_settings: Settings) -> None:
    llm = LLM(ai_settings, FakeOllamaClient())
    assert [chunk async for chunk in llm.stream(MESSAGES)] == ["Hel", "lo"]
