import datetime as dt
import json

import pytest
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.ai.client import LLM
from fitbit_app.ai.service import AIService
from fitbit_app.ai.tools import TOOL_DEFINITIONS, run_tool
from fitbit_app.config import Settings
from fitbit_app.storage.models import JournalEntry
from fitbit_app.storage.types import utcnow
from fixtures.fake_llm import FakeLLM, FakeOllamaClient
from fixtures.scenario import LAST, NOW, START, build_scored_db


@pytest.fixture
def scored(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    build_scored_db(session_factory)
    with session_factory() as session:
        session.add(JournalEntry(date=START, tags=["alcohol"], updated_at=utcnow()))
        session.commit()
    return session_factory


def _run(scored: sessionmaker[Session], name: str, args: dict) -> dict:
    with scored() as session:
        return json.loads(run_tool(session, name, args, LAST))


def test_definitions_are_well_formed() -> None:
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert names == ["get_metric_history", "get_day_summary", "get_journal", "get_tag_effects"]
    for tool in TOOL_DEFINITIONS:
        params = tool["function"]["parameters"]
        assert set(params["required"]) <= set(params["properties"])


def test_metric_history(scored: sessionmaker[Session]) -> None:
    end = START + dt.timedelta(days=6)
    result = _run(
        scored,
        "get_metric_history",
        {"metric": "resting_hr", "start_date": START.isoformat(), "end_date": end.isoformat()},
    )
    assert [d["date"] for d in result["days"]][0] == START.isoformat()
    assert len(result["days"]) == 7
    assert result["min"] <= result["mean"] <= result["max"]


def test_day_summary_and_journal(scored: sessionmaker[Session]) -> None:
    summary = _run(scored, "get_day_summary", {"date": LAST.isoformat()})
    assert summary["date"] == LAST.isoformat()
    journal = _run(
        scored, "get_journal", {"start_date": START.isoformat(), "end_date": LAST.isoformat()}
    )
    assert journal == {START.isoformat(): ["alcohol"]}


def test_tag_effects_tool(scored: sessionmaker[Session]) -> None:
    result = _run(scored, "get_tag_effects", {"outcome": "recovery"})
    assert result["logged_days"] == 1
    assert result["effects"] == []  # far too little journal data


@pytest.mark.parametrize(
    ("name", "args", "message"),
    [
        (
            "get_metric_history",
            {"metric": "mood", "start_date": "2026-09-01", "end_date": "2026-09-02"},
            "Unknown metric",
        ),
        ("get_day_summary", {"date": "yesterday"}, "Invalid date"),
        ("get_tag_effects", {"outcome": "mood"}, "Unknown outcome"),
        ("delete_everything", {}, "Unknown tool"),
    ],
)
def test_bad_arguments_are_reported_not_raised(
    scored: sessionmaker[Session], name: str, args: dict, message: str
) -> None:
    assert message in _run(scored, name, args)["error"]


def test_huge_ranges_are_capped(scored: sessionmaker[Session]) -> None:
    result = _run(
        scored,
        "get_metric_history",
        {"metric": "steps", "start_date": "2000-01-01", "end_date": LAST.isoformat()},
    )
    assert len(result["days"]) == 21  # only the synthetic days exist; no error


async def test_llm_runs_tool_calls_before_answering(settings: Settings) -> None:
    enabled = settings.model_copy(update={"ai_enabled": True})
    client = FakeOllamaClient(tool_calls=[("get_day_summary", {"date": "2026-09-21"})])
    calls: list[tuple[str, dict]] = []

    async def runner(name: str, args: dict) -> str:
        calls.append((name, args))
        return '{"ok": true}'

    llm = LLM(enabled, client)
    messages = [{"role": "user", "content": "hi"}]
    chunks = [c async for c in llm.stream_with_tools(messages, TOOL_DEFINITIONS, runner)]
    assert calls == [("get_day_summary", {"date": "2026-09-21"})]
    assert "".join(chunks) == "Hello"
    second = client.chat_calls[1]["messages"]
    assert second[-1] == {
        "role": "tool",
        "content": '{"ok": true}',
        "tool_name": "get_day_summary",
    }
    assert second[-2]["tool_calls"][0]["function"]["name"] == "get_day_summary"


async def test_chat_tools_read_the_database(
    settings: Settings, scored: sessionmaker[Session]
) -> None:
    week = {"metric": "recovery", "start_date": "2026-09-15", "end_date": "2026-09-21"}
    llm = FakeLLM(tool_call=("get_metric_history", week))
    enabled = settings.model_copy(update={"ai_enabled": True})
    service = AIService(enabled, scored, llm=llm, clock=lambda: NOW)  # type: ignore[arg-type]
    [c async for c in service.chat(service.new_conversation_id(), "How was my week?")]
    result = json.loads(llm.tool_results[0])
    assert result["metric"] == "recovery"
    assert len(result["days"]) == 7
