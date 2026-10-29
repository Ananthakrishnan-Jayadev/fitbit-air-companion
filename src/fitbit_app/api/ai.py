"""/api/ai/*: status, stored insights, regeneration and the streaming coach chat."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fitbit_app.ai import context as ctx
from fitbit_app.ai.service import AIService, Insight
from fitbit_app.ai.status import check_ollama
from fitbit_app.config import Settings
from fitbit_app.errors import FitbitAppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

InsightKind = Literal["daily_brief", "weekly_review", "anomaly"]


def get_ai_service(request: Request) -> AIService:
    return request.app.state.ai_service


AIDep = Annotated[AIService, Depends(get_ai_service)]


class AIStatus(BaseModel):
    enabled: bool
    reachable: bool
    model: str
    model_present: bool
    busy: bool
    detail: str | None = None


class InsightOut(BaseModel):
    kind: str
    date: dt.date
    model: str
    created_at: dt.datetime
    content: dict[str, Any]


class InsightsResponse(BaseModel):
    date: dt.date | None
    busy: bool
    daily_brief: InsightOut | None = None
    anomaly: InsightOut | None = None
    weekly_review: InsightOut | None = None


class GenerateRequest(BaseModel):
    kind: InsightKind = "daily_brief"
    date: dt.date | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: dt.datetime


@router.get("/status", response_model=AIStatus)
async def status(request: Request, ai: AIDep) -> AIStatus:
    settings: Settings = request.app.state.settings
    if not settings.ai_enabled:
        return AIStatus(
            enabled=False,
            reachable=False,
            model=settings.ollama_model,
            model_present=False,
            busy=False,
            detail="AI is disabled (AI_ENABLED=false)",
        )
    ollama = await check_ollama(settings.ollama_host, settings.ollama_model)
    return AIStatus(enabled=True, busy=ai.busy, **ollama.model_dump())


@router.get("/insights", response_model=InsightsResponse)
def insights(request: Request, ai: AIDep, date: dt.date | None = None) -> InsightsResponse:
    day = date or _latest_day(request)
    if day is None:
        return InsightsResponse(date=None, busy=ai.busy)
    found = ai.insights(day)
    return InsightsResponse(
        date=day,
        busy=ai.busy,
        daily_brief=_out(found["daily_brief"]),
        anomaly=_out(found["anomaly"]),
        weekly_review=_out(found["weekly_review"]),
    )


@router.post("/generate", status_code=202)
async def generate(request: Request, body: GenerateRequest, ai: AIDep) -> dict[str, bool]:
    if not ai.enabled:
        raise HTTPException(503, "AI is disabled (AI_ENABLED=false)")
    day = body.date or await asyncio.to_thread(_latest_day, request)
    if day is None:
        raise HTTPException(404, "No scored days yet")
    if not ai.start_generate(body.kind, day):
        raise HTTPException(409, "The coach is busy with another request")
    return {"started": True}


@router.post("/chat")
async def chat(body: ChatRequest, ai: AIDep) -> StreamingResponse:
    """Server-sent events: `{"delta": "..."}` chunks, then `{"done": true}` or `{"error": ...}`."""
    if not ai.enabled:
        raise HTTPException(503, "AI is disabled (AI_ENABLED=false)")
    conversation_id = body.conversation_id or ai.new_conversation_id()

    async def events() -> AsyncIterator[str]:
        yield _sse({"conversation_id": conversation_id})
        try:
            async for chunk in ai.chat(conversation_id, body.message):
                yield _sse({"delta": chunk})
        except FitbitAppError as exc:
            logger.warning("Chat failed: %s", exc)
            yield _sse({"error": str(exc)})
            return
        yield _sse({"done": True})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/{conversation_id}", response_model=list[ChatMessageOut])
def chat_history(conversation_id: str, ai: AIDep) -> list[ChatMessageOut]:
    return [ChatMessageOut(**m) for m in ai.history(conversation_id)]


def _latest_day(request: Request) -> dt.date | None:
    with request.app.state.session_factory() as session:
        return ctx.latest_scored_day(session)


def _out(insight: Insight | None) -> InsightOut | None:
    if insight is None:
        return None
    return InsightOut(
        kind=insight.kind,
        date=insight.date,
        model=insight.model,
        created_at=insight.created_at,
        content=insight.content,
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
