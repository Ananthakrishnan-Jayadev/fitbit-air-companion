from pathlib import Path

import pytest

from fitbit_app import devserver
from fitbit_app.errors import ConfigError


def test_requires_npm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(devserver.shutil, "which", lambda _name: None)
    with pytest.raises(ConfigError, match="npm not found"):
        devserver.start_vite(tmp_path, api_port=8000)


def test_requires_node_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(devserver.shutil, "which", lambda _name: "/usr/bin/npm")
    with pytest.raises(ConfigError, match="npm --prefix"):
        devserver.start_vite(tmp_path, api_port=8000)


def test_stop_is_noop_for_exited_process(monkeypatch: pytest.MonkeyPatch) -> None:
    class Exited:
        pid = 12345

        def poll(self) -> int:
            return 0

    def fail_killpg(pid: int, sig: int) -> None:
        raise AssertionError("must not signal an exited process")

    monkeypatch.setattr(devserver.os, "killpg", fail_killpg)
    devserver.stop_vite(Exited())  # type: ignore[arg-type]
