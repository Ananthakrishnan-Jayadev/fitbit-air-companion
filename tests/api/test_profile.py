import pytest
from fastapi.testclient import TestClient


def test_empty_profile(client: TestClient) -> None:
    assert client.get("/api/profile").json() == {
        "age": None,
        "max_hr": None,
        "sleep_need_min": None,
    }


def test_save_and_reload(client: TestClient) -> None:
    profile = {"age": 30, "max_hr": None, "sleep_need_min": 480}
    assert client.put("/api/profile", json=profile).json() == profile
    assert client.get("/api/profile").json() == profile


@pytest.mark.parametrize(
    "profile",
    [{"age": 5}, {"max_hr": 300}, {"sleep_need_min": 60}],
)
def test_rejects_out_of_range(client: TestClient, profile: dict) -> None:
    assert client.put("/api/profile", json=profile).status_code == 422
