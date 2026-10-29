import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.ai.schemas import AnomalyNote, DailyBrief, WeeklyReview
from fitbit_app.ai.service import ANOMALY, DAILY_BRIEF, WEEKLY_REVIEW, AIService
from fitbit_app.config import Settings
from fitbit_app.storage.models import AIInsight
from fixtures.fake_llm import FakeLLM
from fixtures.scenario import LAST, NOW, SICK, START, build_scored_db


@pytest.fixture
def scored(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    build_scored_db(session_factory)
    return session_factory


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def service(settings: Settings, scored: sessionmaker[Session], llm: FakeLLM) -> AIService:
    enabled = settings.model_copy(update={"ai_enabled": True})
    return AIService(enabled, scored, llm=llm, clock=lambda: NOW)  # type: ignore[arg-type]


def _count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(AIInsight)) or 0


async def test_daily_brief_is_generated_and_stored(service: AIService, llm: FakeLLM) -> None:
    insight = await service.generate(DAILY_BRIEF, LAST)
    assert insight is not None
    assert insight.model == "fake-model"
    assert insight.content["headline"] == "Recovery is solid today."
    messages, schema = llm.generate_calls[0]
    assert schema is DailyBrief
    assert messages[0]["role"] == "system"
    assert LAST.isoformat() in messages[1]["content"]
    assert service.insights(LAST)[DAILY_BRIEF] is not None


async def test_unchanged_data_is_not_regenerated(service: AIService, llm: FakeLLM) -> None:
    await service.generate(DAILY_BRIEF, LAST)
    await service.generate(DAILY_BRIEF, LAST)
    assert len(llm.generate_calls) == 1
    await service.generate(DAILY_BRIEF, LAST, force=True)
    assert len(llm.generate_calls) == 2


async def test_no_data_means_no_insight(service: AIService, llm: FakeLLM) -> None:
    assert await service.generate(DAILY_BRIEF, START - dt.timedelta(days=30)) is None
    assert llm.generate_calls == []


async def test_anomaly_note_only_when_flagged(service: AIService, llm: FakeLLM) -> None:
    # Day 2 has no baselines yet, so nothing can be flagged.
    assert await service.generate(ANOMALY, START + dt.timedelta(days=1)) is None
    note = await service.generate(ANOMALY, SICK)
    assert note is not None
    assert llm.generate_calls[-1][1] is AnomalyNote
    assert "illness_watch" in llm.generate_calls[-1][0][1]["content"]


async def test_weekly_review(service: AIService, llm: FakeLLM) -> None:
    review = await service.generate(WEEKLY_REVIEW, LAST)
    assert review is not None
    assert llm.generate_calls[-1][1] is WeeklyReview


async def test_unknown_kind(service: AIService) -> None:
    with pytest.raises(ValueError):
        await service.generate("poem", LAST)


async def test_after_sync_fills_brief_and_weekly_once(
    service: AIService, llm: FakeLLM, scored: sessionmaker[Session]
) -> None:
    await service.after_sync()
    kinds = [schema for _, schema in llm.generate_calls]
    assert DailyBrief in kinds
    assert WeeklyReview in kinds  # LAST is a Monday
    stored = _count(scored)
    await service.after_sync()
    assert _count(scored) == stored  # nothing new the second time


async def test_after_sync_does_nothing_when_disabled(
    settings: Settings, scored: sessionmaker[Session], llm: FakeLLM
) -> None:
    disabled = AIService(settings, scored, llm=llm)  # type: ignore[arg-type]
    await disabled.after_sync()
    assert llm.generate_calls == []


async def test_chat_streams_and_keeps_history(service: AIService, llm: FakeLLM) -> None:
    conversation = service.new_conversation_id()
    chunks = [c async for c in service.chat(conversation, "How did I sleep?")]
    assert "".join(chunks) == "You slept well."

    system, *_, user = llm.stream_calls[0]
    assert system["role"] == "system"
    assert LAST.isoformat() in system["content"]
    assert user == {"role": "user", "content": "How did I sleep?"}

    history = service.history(conversation)
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "How did I sleep?"),
        ("assistant", "You slept well."),
    ]

    [c async for c in service.chat(conversation, "And yesterday?")]
    second = llm.stream_calls[1]
    assert {"role": "assistant", "content": "You slept well."} in second
    assert second[-1] == {"role": "user", "content": "And yesterday?"}
