import datetime as dt
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.errors import NotConnectedError, ReauthRequiredError
from fitbit_app.ingest.client import GoogleHealthClient
from fitbit_app.ingest.endpoints import API_BASE_URL
from fitbit_app.ingest.registry import REGISTRY, DataTypeSpec
from fitbit_app.ingest.sync import Cursor, SyncEngine, Window, plan_windows
from fitbit_app.storage.models import ActivityMinute, DailyMetric, SyncState
from fixtures import google_api as g

NOW = dt.datetime(2026, 10, 29, 12, 0, tzinfo=dt.UTC)
DAY = dt.timedelta(days=1)

STEPS_URL = f"{API_BASE_URL}/v4/users/me/dataTypes/steps/dataPoints:reconcile"
RHR_URL = f"{API_BASE_URL}/v4/users/me/dataTypes/daily-resting-heart-rate/dataPoints:reconcile"


def _spec(key: str) -> DataTypeSpec:
    return next(s for s in REGISTRY if s.key == key)


# --- plan_windows ------------------------------------------------------------------------


def test_first_run_backfills_newest_first() -> None:
    windows = plan_windows(_spec("steps"), Cursor(None, None), NOW, NOW - 20 * DAY)
    assert windows == [
        Window(NOW - 7 * DAY, NOW, "backfill"),
        Window(NOW - 14 * DAY, NOW - 7 * DAY, "backfill"),
        Window(NOW - 20 * DAY, NOW - 14 * DAY, "backfill"),
    ]


def test_incremental_run_overlaps_and_skips_done_backfill() -> None:
    state = Cursor(cursor=NOW - dt.timedelta(hours=1), synced_from=NOW - 30 * DAY)
    windows = plan_windows(_spec("steps"), state, NOW, NOW - 30 * DAY)
    assert windows == [Window(NOW - dt.timedelta(hours=3), NOW, "incremental")]


def test_interrupted_backfill_resumes() -> None:
    state = Cursor(cursor=NOW - dt.timedelta(hours=1), synced_from=NOW - 7 * DAY)
    windows = plan_windows(_spec("steps"), state, NOW, NOW - 10 * DAY)
    assert windows[-1] == Window(NOW - 10 * DAY, NOW - 7 * DAY, "backfill")


def test_daily_types_reread_three_days() -> None:
    state = Cursor(cursor=NOW, synced_from=NOW - 90 * DAY)
    windows = plan_windows(_spec("daily-resting-heart-rate"), state, NOW, NOW - 90 * DAY)
    assert windows == [Window(NOW - 3 * DAY, NOW, "incremental")]


def test_earlier_since_extends_backfill() -> None:
    state = Cursor(cursor=NOW, synced_from=NOW - 7 * DAY)
    windows = plan_windows(_spec("steps"), state, NOW, NOW - 14 * DAY)
    assert Window(NOW - 14 * DAY, NOW - 7 * DAY, "backfill") in windows


# --- SyncEngine --------------------------------------------------------------------------


class FakeTokens:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def access_token(self, *, force_refresh: bool = False) -> str:
        if self.error is not None:
            raise self.error
        return "token"


async def _no_sleep(_: float) -> None:
    return None


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        yield client


def _engine(
    http: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    tokens: FakeTokens | None = None,
) -> SyncEngine:
    client = GoogleHealthClient(http, tokens or FakeTokens(), requests_per_s=1000, sleep=_no_sleep)
    return SyncEngine(client, session_factory, backfill_days=14, clock=lambda: NOW)


def _steps_page(request: httpx.Request) -> httpx.Response:
    # One 1-minute steps interval at the start of whichever window was requested.
    lower = request.url.params["filter"].split('"')[1]
    end = lower.replace(":00Z", ":59Z")
    return httpx.Response(200, json=g.page([g.steps(lower, end, 100)]))


@respx.mock
async def test_backfill_then_incremental(
    http: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    respx.get(STEPS_URL).mock(side_effect=_steps_page)
    engine = _engine(http, session_factory)

    report = await engine.run([_spec("steps")])
    assert report.ok == ["steps"]
    assert respx.calls.call_count == 2  # 14 days in 7-day chunks
    with session_factory() as session:
        state = session.get(SyncState, "steps")
        assert state is not None
        assert state.cursor == NOW
        assert state.synced_from == NOW - 14 * DAY
        assert state.last_success_at == NOW
        assert session.scalar(select(func.count()).select_from(ActivityMinute)) == 2

    # Second run: only the overlapping incremental window, no duplicate rows.
    await engine.run([_spec("steps")])
    assert respx.calls.call_count == 3
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActivityMinute)) == 3


@respx.mock
async def test_one_failing_type_does_not_stop_others(
    http: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    respx.get(STEPS_URL).mock(
        return_value=httpx.Response(400, json=g.api_error(400, "INVALID_ARGUMENT", "bad filter"))
    )
    day = NOW.date()
    respx.get(RHR_URL).mock(
        return_value=httpx.Response(
            200, json=g.page([g.daily("dailyRestingHeartRate", day, beatsPerMinute="58")])
        )
    )
    report = await _engine(http, session_factory).run(
        [_spec("steps"), _spec("daily-resting-heart-rate")]
    )
    assert report.ok == ["daily-resting-heart-rate"]
    assert "INVALID_ARGUMENT" in report.failed["steps"]
    with session_factory() as session:
        failed = session.get(SyncState, "steps")
        assert failed is not None
        assert failed.last_error is not None
        assert failed.cursor is None  # nothing was marked as synced
        assert session.get(DailyMetric, day).resting_hr == 58  # type: ignore[union-attr]


@pytest.mark.parametrize("error", [ReauthRequiredError("expired"), NotConnectedError("none")])
async def test_auth_problems_abort_the_run(
    http: httpx.AsyncClient, session_factory: sessionmaker[Session], error: Exception
) -> None:
    engine = _engine(http, session_factory, FakeTokens(error))
    with pytest.raises(type(error)):
        await engine.run([_spec("steps"), _spec("sleep")])


async def test_since_sets_backfill_target(
    http: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    with respx.mock:
        respx.get(STEPS_URL).mock(return_value=httpx.Response(200, json=g.page([])))
        await _engine(http, session_factory).run([_spec("steps")], since=dt.date(2026, 10, 25))
    with session_factory() as session:
        state = session.get(SyncState, "steps")
        assert state is not None
        assert state.synced_from == dt.datetime(2026, 10, 25, tzinfo=dt.UTC)
