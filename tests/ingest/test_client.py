import datetime as dt
import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from fitbit_app.errors import GoogleApiError, ReauthRequiredError
from fitbit_app.ingest.client import GoogleHealthClient, RateLimiter
from fitbit_app.ingest.endpoints import API_BASE_URL
from fitbit_app.ingest.registry import REGISTRY, DataTypeSpec
from fixtures.google_api import api_error, heart_rate, page, rollup_page, rollup_steps

HR = next(s for s in REGISTRY if s.key == "heart-rate")
IRN = next(s for s in REGISTRY if s.key == "irregular-rhythm-notification")
STEPS_DAILY = next(s for s in REGISTRY if s.key == "steps:daily")

HR_URL = f"{API_BASE_URL}/v4/users/me/dataTypes/heart-rate/dataPoints:reconcile"


class FakeTokens:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def access_token(self, *, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        return "token-refreshed" if force_refresh else "token-1"


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        yield client


def _client(http: httpx.AsyncClient, tokens: FakeTokens, sleeps: Sleeps) -> GoogleHealthClient:
    return GoogleHealthClient(http, tokens, requests_per_s=1000, max_retries=3, sleep=sleeps)


async def _collect(client: GoogleHealthClient, spec: DataTypeSpec = HR) -> list[list[dict]]:
    return [p async for p in client.iter_pages(spec, "f")]


@respx.mock
async def test_pagination_and_request_shape(http: httpx.AsyncClient) -> None:
    route = respx.get(HR_URL).mock(
        side_effect=[
            httpx.Response(200, json=page([heart_rate("2026-10-01T00:00:00Z", 60)], "next-1")),
            httpx.Response(200, json=page([heart_rate("2026-10-01T00:00:01Z", 61)])),
        ]
    )
    pages = await _collect(_client(http, FakeTokens(), Sleeps()))

    assert [len(p) for p in pages] == [1, 1]
    first, second = (call.request for call in route.calls)
    assert first.headers["Authorization"] == "Bearer token-1"
    assert first.url.params["filter"] == "f"
    assert first.url.params["pageSize"] == "10000"
    assert first.url.params["dataSourceFamily"] == "users/me/dataSourceFamilies/google-wearables"
    assert "pageToken" not in first.url.params
    assert second.url.params["pageToken"] == "next-1"


@respx.mock
async def test_list_method_path(http: httpx.AsyncClient) -> None:
    url = f"{API_BASE_URL}/v4/users/me/dataTypes/irregular-rhythm-notification/dataPoints"
    route = respx.get(url).mock(return_value=httpx.Response(200, json=page([])))
    assert await _collect(_client(http, FakeTokens(), Sleeps()), IRN) == [[]]
    assert route.called


@respx.mock
async def test_daily_rollup_request(http: httpx.AsyncClient) -> None:
    url = f"{API_BASE_URL}/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp"
    body = rollup_page([rollup_steps(dt.date(2026, 10, 1), 9000)])
    route = respx.post(url).mock(return_value=httpx.Response(200, json=body))
    client = _client(http, FakeTokens(), Sleeps())
    first, end = dt.date(2026, 10, 1), dt.date(2026, 10, 3)
    pages = [p async for p in client.daily_rollup_pages(STEPS_DAILY, first, end)]
    assert len(pages[0]) == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent["range"] == {
        "start": {"date": {"year": 2026, "month": 10, "day": 1}},
        "end": {"date": {"year": 2026, "month": 10, "day": 3}},
    }
    assert sent["windowSizeDays"] == 1


@respx.mock
async def test_retries_429_honouring_retry_after(http: httpx.AsyncClient) -> None:
    respx.get(HR_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=page([])),
        ]
    )
    sleeps = Sleeps()
    await _collect(_client(http, FakeTokens(), sleeps))
    assert 7.0 in sleeps.delays


@respx.mock
async def test_retries_server_errors_then_gives_up(http: httpx.AsyncClient) -> None:
    respx.get(HR_URL).mock(
        return_value=httpx.Response(503, json=api_error(503, "UNAVAILABLE", "try later"))
    )
    with pytest.raises(GoogleApiError) as info:
        await _collect(_client(http, FakeTokens(), Sleeps()))
    assert info.value.status_code == 503
    assert respx.calls.call_count == 4  # first try + 3 retries


@respx.mock
async def test_401_refreshes_once_then_succeeds(http: httpx.AsyncClient) -> None:
    route = respx.get(HR_URL).mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json=page([]))]
    )
    tokens = FakeTokens()
    await _collect(_client(http, tokens, Sleeps()))
    assert tokens.calls == [False, True]
    assert route.calls.last.request.headers["Authorization"] == "Bearer token-refreshed"


@respx.mock
async def test_repeated_401_requires_reauth(http: httpx.AsyncClient) -> None:
    respx.get(HR_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ReauthRequiredError):
        await _collect(_client(http, FakeTokens(), Sleeps()))


@respx.mock
async def test_error_reason_is_extracted(http: httpx.AsyncClient) -> None:
    respx.get(f"{API_BASE_URL}/v4/users/me/identity").mock(
        return_value=httpx.Response(
            400, json=api_error(400, "FAILED_PRECONDITION", "Not linked", "ACCOUNT_NOT_LINKED")
        )
    )
    with pytest.raises(GoogleApiError) as info:
        await _client(http, FakeTokens(), Sleeps()).get_identity()
    assert info.value.reason == "ACCOUNT_NOT_LINKED"
    assert info.value.status_code == 400


@respx.mock
async def test_get_identity(http: httpx.AsyncClient) -> None:
    respx.get(f"{API_BASE_URL}/v4/users/me/identity").mock(
        return_value=httpx.Response(
            200, json={"name": "users/me/identity", "healthUserId": "abc-123"}
        )
    )
    identity = await _client(http, FakeTokens(), Sleeps()).get_identity()
    assert identity["healthUserId"] == "abc-123"


async def test_rate_limiter_spaces_requests() -> None:
    now = [100.0]
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    limiter = RateLimiter(2.0, clock=lambda: now[0], sleep=fake_sleep)
    for _ in range(3):
        await limiter.wait()
    assert sleeps == [pytest.approx(0.5), pytest.approx(0.5)]
