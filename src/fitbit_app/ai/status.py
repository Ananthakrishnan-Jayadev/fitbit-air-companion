"""Ollama reachability and model-presence check (used by /api/health and `fitbit doctor`)."""

from __future__ import annotations

import logging

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OllamaStatus(BaseModel):
    reachable: bool
    model: str
    model_present: bool
    detail: str | None = None


async def check_ollama(host: str, model: str, timeout_s: float = 3.0) -> OllamaStatus:
    client = AsyncClient(host=host, timeout=timeout_s)
    try:
        response = await client.list()
    except (httpx.HTTPError, ConnectionError, ResponseError) as exc:
        logger.warning("Ollama not reachable at %s: %s", host, type(exc).__name__)
        return OllamaStatus(
            reachable=False,
            model=model,
            model_present=False,
            detail=f"Cannot reach Ollama at {host}",
        )

    installed = {m.model for m in response.models if m.model}
    present = model_matches(model, installed)
    return OllamaStatus(
        reachable=True,
        model=model,
        model_present=present,
        detail=None if present else f"Model not pulled. Run: ollama pull {model}",
    )


def model_matches(model: str, installed: set[str]) -> bool:
    # Ollama reports untagged models as "<name>:latest".
    wanted = model if ":" in model else f"{model}:latest"
    return wanted in installed
