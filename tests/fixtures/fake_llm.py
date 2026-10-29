"""Stand-ins for Ollama: never call a real model in tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from types import SimpleNamespace
from typing import Any, TypeVar

from ollama import ResponseError
from pydantic import BaseModel

from fitbit_app.ai.schemas import AnomalyNote, DailyBrief, Tip, WeeklyReview

T = TypeVar("T", bound=BaseModel)

SAMPLES: dict[type[BaseModel], BaseModel] = {
    DailyBrief: DailyBrief(
        headline="Recovery is solid today.",
        summary="Your recovery is 62 with HRV near normal.",
        tips=[Tip(title="Train moderately", detail="Aim for strain 10-14.", category="training")],
    ),
    WeeklyReview: WeeklyReview(
        headline="A steady week.",
        summary="Recovery averaged in the 50s.",
        wins=["Consistent bedtimes"],
        watch=["Resting heart rate crept up"],
        focus="Keep bedtime within 30 minutes.",
    ),
    AnomalyNote: AnomalyNote(
        headline="Several signals are off today.",
        explanation="Temperature and resting heart rate are both above normal.",
        suggestions=["Take it easy today"],
        see_doctor_if="You feel unwell or it lasts more than a few days.",
    ),
}


class FakeLLM:
    """Replaces fitbit_app.ai.client.LLM in service/API tests."""

    model = "fake-model"

    def __init__(
        self,
        chunks: Sequence[str] = ("You ", "slept ", "well."),
        tool_call: tuple[str, dict[str, Any]] | None = None,
    ) -> None:
        self.generate_calls: list[tuple[list[dict[str, Any]], type[BaseModel]]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []
        self.tool_results: list[str] = []
        self._chunks = list(chunks)
        self._tool_call = tool_call

    async def generate(self, messages: Sequence[dict[str, str]], schema: type[T]) -> T:
        self.generate_calls.append((list(messages), schema))
        return schema.model_validate(SAMPLES[schema].model_dump())

    async def stream(self, messages: Sequence[dict[str, Any]]) -> AsyncIterator[str]:
        self.stream_calls.append(list(messages))
        for chunk in self._chunks:
            yield chunk

    async def stream_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: list[dict[str, Any]],
        run_tool: Callable[[str, dict[str, Any]], Awaitable[str]],
    ) -> AsyncIterator[str]:
        self.stream_calls.append(list(messages))
        if self._tool_call is not None:
            self.tool_results.append(await run_tool(*self._tool_call))
        for chunk in self._chunks:
            yield chunk


def _reply(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))


class FakeOllamaClient:
    """Replaces ollama.AsyncClient inside LLM (client-level tests)."""

    def __init__(
        self,
        models: Sequence[str] = ("qwen3.5:9b",),
        replies: Sequence[str] = (),
        list_error: Exception | None = None,
        reject_think: bool = False,
        tool_calls: Sequence[tuple[str, dict[str, Any]]] = (),
    ) -> None:
        self.models = list(models)
        self.replies = list(replies)
        self.list_error = list_error
        self.reject_think = reject_think
        self.pending_tool_calls = list(tool_calls)
        self.chat_calls: list[dict[str, Any]] = []

    async def list(self) -> SimpleNamespace:
        if self.list_error is not None:
            raise self.list_error
        return SimpleNamespace(models=[SimpleNamespace(model=m) for m in self.models])

    async def chat(self, **kwargs: Any) -> Any:
        self.chat_calls.append(kwargs)
        if self.reject_think and "think" in kwargs:
            raise ResponseError('"qwen3.5:9b" does not support thinking')
        if kwargs.get("stream"):
            if kwargs.get("tools") and self.pending_tool_calls:
                calls, self.pending_tool_calls = self.pending_tool_calls, []
                return self._tool_stream(calls)
            return self._stream()
        return _reply(self.replies.pop(0))

    async def _stream(self) -> AsyncIterator[SimpleNamespace]:
        for chunk in ("Hel", "lo", ""):
            yield _reply(chunk)

    async def _tool_stream(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> AsyncIterator[SimpleNamespace]:
        tool_calls = [
            SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
            for name, args in calls
        ]
        yield SimpleNamespace(message=SimpleNamespace(content="", tool_calls=tool_calls))
