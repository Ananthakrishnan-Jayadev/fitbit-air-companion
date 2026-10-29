from types import SimpleNamespace

import httpx
import pytest

from fitbit_app.ai import status as status_module
from fitbit_app.ai.status import check_ollama, model_matches


def _fake_client(models: list[str] | None = None, error: Exception | None = None) -> type:
    class FakeAsyncClient:
        def __init__(self, host: str, timeout: float) -> None:
            self.host = host

        async def list(self) -> SimpleNamespace:
            if error is not None:
                raise error
            return SimpleNamespace(models=[SimpleNamespace(model=m) for m in models or []])

    return FakeAsyncClient


@pytest.mark.parametrize(
    ("model", "installed", "expected"),
    [
        ("gemma4:31b", {"gemma4:31b"}, True),
        ("gemma4:31b", {"gemma4:latest"}, False),
        ("gemma4", {"gemma4:latest"}, True),
        ("gemma4", {"gemma4:31b"}, False),
        ("gemma4:31b", set(), False),
    ],
)
def test_model_matches(model: str, installed: set[str], expected: bool) -> None:
    assert model_matches(model, installed) is expected


async def test_model_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(status_module, "AsyncClient", _fake_client(["gemma4:31b", "llama3.1:8b"]))
    status = await check_ollama("http://ollama.test", "gemma4:31b")
    assert status.reachable is True
    assert status.model_present is True
    assert status.detail is None


async def test_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(status_module, "AsyncClient", _fake_client(["llama3.1:8b"]))
    status = await check_ollama("http://ollama.test", "gemma4:31b")
    assert status.reachable is True
    assert status.model_present is False
    assert status.detail is not None
    assert "ollama pull gemma4:31b" in status.detail


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("refused"), ConnectionError("refused"), httpx.ReadTimeout("slow")]
)
async def test_unreachable(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.setattr(status_module, "AsyncClient", _fake_client(error=error))
    status = await check_ollama("http://ollama.test", "gemma4:31b")
    assert status.reachable is False
    assert status.model_present is False
