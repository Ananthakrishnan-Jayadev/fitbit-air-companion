import datetime as dt
import json

import pytest
from jinja2 import UndefinedError
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.ai import templates
from fitbit_app.ai.context import (
    day_context,
    fit_budget,
    latest_scored_day,
    recent_days,
    week_context,
)
from fixtures.scenario import LAST, SICK, START, build_scored_db


@pytest.fixture
def scored(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    build_scored_db(session_factory)
    return session_factory


# --- Templates ---------------------------------------------------------------------------


def test_system_prompt_has_grounding_rules() -> None:
    prompt = templates.system_prompt()
    assert "ONLY numbers that appear in the DATA" in prompt
    assert "Never diagnose" in prompt


def test_render_embeds_data_as_json() -> None:
    text = templates.render("daily_brief", day="2026-10-01", data={"scores": {"recovery": 61}})
    assert '"recovery": 61' in text
    assert "2026-10-01" in text


def test_missing_template_variable_fails_loudly() -> None:
    with pytest.raises(UndefinedError):
        templates.render("daily_brief", day="2026-10-01")


# --- Context -----------------------------------------------------------------------------


def test_day_context(scored: sessionmaker[Session]) -> None:
    with scored() as session:
        assert latest_scored_day(session) == LAST
        pack = day_context(session, LAST)
    assert pack is not None
    assert pack["date"] == LAST.isoformat()
    assert {"scores", "metrics", "vs_baseline_z", "trend_7d", "sleep", "flags"} <= set(pack)
    assert 0 <= pack["scores"]["recovery"] <= 100
    assert pack["sleep"]["asleep_min"] > 0
    assert "bedtime_local" in pack["sleep"]
    # Only summaries: nothing like a raw intraday series.
    assert len(json.dumps(pack)) < 6000


def test_sick_day_context_carries_flags(scored: sessionmaker[Session]) -> None:
    with scored() as session:
        pack = day_context(session, SICK)
    assert pack is not None
    assert "illness_watch" in pack["flags"]


def test_no_context_without_data(scored: sessionmaker[Session]) -> None:
    with scored() as session:
        assert day_context(session, START - dt.timedelta(days=30)) is None
        assert week_context(session, START - dt.timedelta(days=30)) is None


def test_week_context(scored: sessionmaker[Session]) -> None:
    with scored() as session:
        pack = week_context(session, LAST)
    assert pack is not None
    assert len(pack["days"]) == 7
    assert pack["this_week"]["recovery"] is not None
    assert pack["previous_week"]["steps"] is not None


def test_recent_days(scored: sessionmaker[Session]) -> None:
    with scored() as session:
        rows = recent_days(session, LAST, days=5)
    assert [r["date"] for r in rows] == [
        (LAST - dt.timedelta(days=i)).isoformat() for i in range(4, -1, -1)
    ]


def test_fit_budget_drops_optional_sections_first() -> None:
    pack = {
        "date": "2026-10-01",
        "scores": {"recovery": 50},
        "workouts": ["x" * 500],
        "recovery_drivers": {"hrv": 50},
        "trend_7d": {"hrv": "up"},
        "sleep": {"asleep_min": 400},
    }
    trimmed = fit_budget(pack, max_chars=150)
    assert "workouts" not in trimmed
    assert trimmed["scores"] == {"recovery": 50}
    assert fit_budget(pack, max_chars=10_000) == pack
