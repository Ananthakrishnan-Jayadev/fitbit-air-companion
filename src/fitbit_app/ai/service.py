"""AIService: daily brief, weekly review, anomaly note and coach chat on the local model.

Generations run one at a time (a local model handles one request well). Results are
stored in `ai_insights`, deduplicated by a hash of model + prompt.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import hashlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.ai import context as ctx
from fitbit_app.ai import templates
from fitbit_app.ai.client import LLM
from fitbit_app.ai.schemas import INSIGHT_SCHEMAS
from fitbit_app.config import Settings
from fitbit_app.errors import FitbitAppError
from fitbit_app.storage.models import AIInsight, ChatMessage, Score
from fitbit_app.storage.types import utcnow
from fitbit_app.storage.upsert import upsert

logger = logging.getLogger(__name__)

DAILY_BRIEF = "daily_brief"
WEEKLY_REVIEW = "weekly_review"
ANOMALY = "anomaly"
KINDS = (DAILY_BRIEF, WEEKLY_REVIEW, ANOMALY)
CHAT_HISTORY_MESSAGES = 12
MAX_CHAT_MESSAGE_CHARS = 2000


@dataclass(frozen=True)
class Insight:
    kind: str
    date: dt.date
    model: str
    content: dict[str, Any]
    created_at: dt.datetime


@dataclass(frozen=True)
class _Prompt:
    messages: list[dict[str, str]]
    schema: type[BaseModel]
    prompt_hash: str


class AIService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        llm: LLM | None = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self.llm = llm or LLM(settings)
        self._clock = clock
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def enabled(self) -> bool:
        return self._settings.ai_enabled

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    # --- Structured insights -------------------------------------------------------------

    async def generate(self, kind: str, day: dt.date, *, force: bool = False) -> Insight | None:
        """Generate (or reuse) an insight. None if there is no data for `day`."""
        if kind not in INSIGHT_SCHEMAS:
            raise ValueError(f"Unknown insight kind: {kind}")
        prompt = await asyncio.to_thread(self._build_prompt, kind, day)
        if prompt is None:
            return None
        if not force:
            existing = await asyncio.to_thread(self._find, kind, day, prompt.prompt_hash)
            if existing is not None:
                return existing
        async with self._lock:
            logger.info("Generating %s for %s", kind, day)
            result = await self.llm.generate(prompt.messages, prompt.schema)
            model = self.llm.model or self._settings.ollama_model
        return await asyncio.to_thread(
            self._store, kind, day, model, prompt.prompt_hash, result.model_dump()
        )

    async def after_sync(self) -> None:
        """Called after each sync: fill in today's brief/anomaly note and the weekly review."""
        if not self.enabled:
            return
        day, flags = await asyncio.to_thread(self._latest_day)
        if day is None:
            return
        try:
            if not await asyncio.to_thread(self._has, DAILY_BRIEF, day):
                await self.generate(DAILY_BRIEF, day)
            if flags and not await asyncio.to_thread(self._has, ANOMALY, day):
                await self.generate(ANOMALY, day)
            # On Mondays, review the week that ended yesterday.
            if day.weekday() == 0:
                week_end = day - dt.timedelta(days=1)
                if not await asyncio.to_thread(self._has, WEEKLY_REVIEW, week_end):
                    await self.generate(WEEKLY_REVIEW, week_end)
        except FitbitAppError as exc:
            logger.warning("Automatic AI insight skipped: %s", exc)

    def start_after_sync(self) -> None:
        """Fire-and-forget `after_sync` (never blocks syncing). Skipped while busy."""
        if self.enabled and not self.busy:
            self._spawn(self.after_sync())

    def start_generate(self, kind: str, day: dt.date) -> bool:
        """Regenerate in the background. False if a generation is already running."""
        if self.busy:
            return False
        self._spawn(self._generate_logged(kind, day))
        return True

    def insights(self, day: dt.date) -> dict[str, Insight | None]:
        """Latest brief and anomaly note for `day`, and the latest weekly review in 7 days."""
        week_start = day - dt.timedelta(days=7)
        with self._session_factory() as session:
            return {
                DAILY_BRIEF: self._latest(session, DAILY_BRIEF, day, day),
                ANOMALY: self._latest(session, ANOMALY, day, day),
                WEEKLY_REVIEW: self._latest(session, WEEKLY_REVIEW, week_start, day),
            }

    # --- Chat ----------------------------------------------------------------------------

    async def chat(self, conversation_id: str, message: str) -> AsyncIterator[str]:
        """Stream the coach's reply. The exchange is stored once the reply finishes."""
        message = message.strip()[:MAX_CHAT_MESSAGE_CHARS]
        messages = await asyncio.to_thread(self._chat_messages, conversation_id, message)
        await asyncio.to_thread(self._save_message, conversation_id, "user", message)
        reply: list[str] = []
        try:
            async with self._lock:
                async for chunk in self.llm.stream(messages):
                    reply.append(chunk)
                    yield chunk
        finally:
            if reply:
                text = "".join(reply)
                await asyncio.to_thread(self._save_message, conversation_id, "assistant", text)

    def history(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.id)
            ).all()
            return [
                {"role": r.role, "content": r.content, "created_at": r.created_at} for r in rows
            ]

    @staticmethod
    def new_conversation_id() -> str:
        return uuid.uuid4().hex

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # --- Internals -----------------------------------------------------------------------

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _generate_logged(self, kind: str, day: dt.date) -> None:
        try:
            await self.generate(kind, day, force=True)
        except FitbitAppError as exc:
            logger.warning("AI generation failed: %s", exc)

    def _build_prompt(self, kind: str, day: dt.date) -> _Prompt | None:
        with self._session_factory() as session:
            if kind == WEEKLY_REVIEW:
                data = ctx.week_context(session, day)
                flags: list[str] = []
            else:
                data = ctx.day_context(session, day)
                flags = list((data or {}).get("flags", []))
        if data is None or (kind == ANOMALY and not flags):
            return None
        template = {DAILY_BRIEF: "daily_brief", WEEKLY_REVIEW: "weekly_review", ANOMALY: "anomaly"}
        user = templates.render(
            template[kind], day=day.isoformat(), data=data, flags=", ".join(flags) or "none"
        )
        messages = [
            {"role": "system", "content": templates.system_prompt()},
            {"role": "user", "content": user},
        ]
        fingerprint = f"{self._settings.ollama_model}\n{kind}\n{user}"
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()
        return _Prompt(messages, INSIGHT_SCHEMAS[kind], digest)

    def _chat_messages(self, conversation_id: str, message: str) -> list[dict[str, str]]:
        with self._session_factory() as session:
            day = ctx.latest_scored_day(session)
            data = ctx.day_context(session, day) if day else None
            recent = ctx.recent_days(session, day) if day else []
            history = session.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.id.desc())
                .limit(CHAT_HISTORY_MESSAGES)
            ).all()
        coach = templates.render(
            "chat",
            day=day.isoformat() if day else "today",
            data=data or {"note": "No data has been synced yet."},
            recent=recent,
        )
        return [
            {"role": "system", "content": templates.system_prompt() + "\n\n" + coach},
            *({"role": m.role, "content": m.content} for m in reversed(history)),
            {"role": "user", "content": message},
        ]

    def _latest_day(self) -> tuple[dt.date | None, list[str]]:
        with self._session_factory() as session:
            day = ctx.latest_scored_day(session)
            if day is None:
                return None, []
            score = session.get(Score, day)
            if score is None or score.sleep_perf is None:
                # Wait for last night's sleep before writing the morning brief.
                return None, []
            return day, list((score.components_json or {}).get("flags") or [])

    def _has(self, kind: str, day: dt.date) -> bool:
        with self._session_factory() as session:
            return self._latest(session, kind, day, day) is not None

    def _find(self, kind: str, day: dt.date, prompt_hash: str) -> Insight | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(AIInsight).where(
                    AIInsight.kind == kind,
                    AIInsight.date == day,
                    AIInsight.prompt_hash == prompt_hash,
                )
            )
            return _insight(row) if row else None

    def _store(
        self, kind: str, day: dt.date, model: str, prompt_hash: str, content: dict[str, Any]
    ) -> Insight:
        now = self._clock()
        with self._session_factory() as session:
            upsert(
                session,
                AIInsight,
                [
                    {
                        "date": day,
                        "kind": kind,
                        "model": model,
                        "prompt_hash": prompt_hash,
                        "content_json": content,
                        "created_at": now,
                    }
                ],
                index_elements=["date", "kind", "prompt_hash"],
            )
            session.commit()
        return Insight(kind, day, model, content, now)

    def _save_message(self, conversation_id: str, role: str, content: str) -> None:
        with self._session_factory() as session:
            session.add(
                ChatMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    created_at=self._clock(),
                )
            )
            session.commit()

    @staticmethod
    def _latest(session: Session, kind: str, start: dt.date, end: dt.date) -> Insight | None:
        row = session.scalar(
            select(AIInsight)
            .where(AIInsight.kind == kind, AIInsight.date >= start, AIInsight.date <= end)
            .order_by(AIInsight.created_at.desc())
            .limit(1)
        )
        return _insight(row) if row else None


def _insight(row: AIInsight) -> Insight:
    return Insight(row.kind, row.date, row.model, dict(row.content_json), row.created_at)
