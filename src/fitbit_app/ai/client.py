"""Thin wrapper around the Ollama client: model selection, structured output, streaming."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, TypeVar

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel, ValidationError

from fitbit_app.ai.status import model_matches
from fitbit_app.config import Settings
from fitbit_app.errors import AIResponseError, AIUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Message = dict[str, str]

TEMPERATURE = 0.3
_UNREACHABLE = (httpx.HTTPError, ConnectionError)


class LLM:
    """One local model behind a small async API. Holds no health data itself."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or AsyncClient(
            host=settings.ollama_host, timeout=settings.ollama_timeout_s
        )
        self._model: str | None = None
        self._think: bool | None = settings.ollama_think

    @property
    def model(self) -> str | None:
        return self._model

    async def resolve_model(self) -> str:
        """The configured model, or the fallback if only that one is installed."""
        if not self._settings.ai_enabled:
            raise AIUnavailableError("AI is disabled (AI_ENABLED=false)")
        if self._model is not None:
            return self._model
        try:
            listing = await self._client.list()
        except _UNREACHABLE as exc:
            host = self._settings.ollama_host
            raise AIUnavailableError(f"Ollama is not reachable at {host}") from exc
        installed = {m.model for m in listing.models if m.model}
        for candidate in (self._settings.ollama_model, self._settings.ollama_fallback_model):
            if candidate and model_matches(candidate, installed):
                self._model = candidate
                return candidate
        wanted = self._settings.ollama_model
        raise AIUnavailableError(f"Model not installed. Run: ollama pull {wanted}")

    async def generate(self, messages: Sequence[Message], schema: type[T]) -> T:
        """Structured output validated against `schema`; one corrective retry."""
        attempt_messages = list(messages)
        last_error: Exception | None = None
        for _ in range(2):
            content = await self._chat(attempt_messages, format_=schema.model_json_schema())
            try:
                return schema.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                logger.warning("Model output failed validation (%d errors)", exc.error_count())
                attempt_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "That did not match the required JSON schema. "
                        "Reply again with only valid JSON matching the schema.",
                    },
                ]
        raise AIResponseError("The model did not return valid structured output") from last_error

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Yield text chunks of a chat reply."""
        model = await self.resolve_model()
        try:
            parts = await self._call(model, list(messages), stream=True)
            async for part in parts:
                text = part.message.content or ""
                if text:
                    yield text
        except _UNREACHABLE as exc:
            raise AIUnavailableError("Lost connection to Ollama") from exc
        except ResponseError as exc:
            raise AIResponseError(f"Ollama error: {exc}") from exc

    async def _chat(self, messages: list[Message], format_: dict[str, Any]) -> str:
        model = await self.resolve_model()
        try:
            response = await self._call(model, messages, stream=False, format_=format_)
        except _UNREACHABLE as exc:
            raise AIUnavailableError("Lost connection to Ollama") from exc
        return response.message.content or ""

    async def _call(
        self,
        model: str,
        messages: list[Message],
        *,
        stream: bool,
        format_: dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {"num_ctx": self._settings.ollama_num_ctx, "temperature": TEMPERATURE},
        }
        if format_ is not None:
            kwargs["format"] = format_
        if self._think is not None:
            kwargs["think"] = self._think
        try:
            return await self._client.chat(**kwargs)
        except ResponseError as exc:
            if self._think is not None and "think" in str(exc).lower():
                # Model has no thinking mode: stop sending the flag and retry once.
                logger.info("Model %s does not support `think`; disabling it", model)
                self._think = None
                kwargs.pop("think", None)
                return await self._client.chat(**kwargs)
            raise AIResponseError(f"Ollama error: {exc}") from exc
