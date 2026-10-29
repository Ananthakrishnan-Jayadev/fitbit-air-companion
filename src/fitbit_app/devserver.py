"""Runs the Vite dev server as a child process for `fitbit serve --dev`."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import threading
from pathlib import Path

from fitbit_app.errors import ConfigError

logger = logging.getLogger("vite")

VITE_URL = "http://127.0.0.1:5173"


def start_vite(frontend_dir: Path, api_port: int) -> subprocess.Popen[str]:
    npm = shutil.which("npm")
    if npm is None:
        raise ConfigError("npm not found on PATH; install Node.js to use --dev")
    if not (frontend_dir / "node_modules").is_dir():
        raise ConfigError(f"Frontend dependencies missing. Run: npm --prefix {frontend_dir} install")

    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=frontend_dir,
        env={**os.environ, "FITBIT_API_PORT": str(api_port)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        # Own process group: Ctrl+C reaches only us, and we stop npm + vite together.
        start_new_session=True,
    )
    threading.Thread(target=_forward_output, args=(proc,), daemon=True).start()
    return proc


def stop_vite(proc: subprocess.Popen[str], timeout_s: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def _forward_output(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        logger.info(line.rstrip())
