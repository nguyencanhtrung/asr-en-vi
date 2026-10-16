"""Idle worker process with an observable liveness marker and no task schema."""

from __future__ import annotations

import argparse
import os
import signal
import tempfile
import threading
import time
from contextlib import suppress
from pathlib import Path

from asr_en_vi.config import Settings
from asr_en_vi.storage import initialize

HEARTBEAT_INTERVAL_SECONDS = 5
HEARTBEAT_MAX_AGE_SECONDS = 20


def heartbeat_path(data_dir: Path) -> Path:
    return Path(data_dir) / "worker.liveness"


def write_heartbeat(data_dir: Path) -> None:
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = heartbeat_path(directory)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".worker-", dir=directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as temporary_file:
            temporary_file.write(f"idle {time.time_ns()}\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except OSError:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def is_healthy(data_dir: Path, *, now: float | None = None) -> bool:
    path = heartbeat_path(data_dir)
    try:
        status = path.read_text(encoding="ascii").strip()
        age = (time.time() if now is None else now) - path.stat().st_mtime
    except OSError:
        return False
    return status.startswith("idle ") and -1 <= age <= HEARTBEAT_MAX_AGE_SECONDS


def run_worker(settings: Settings) -> None:
    previous_umask = os.umask(0o077)
    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    try:
        initialize(settings.data_dir)
        write_heartbeat(settings.data_dir)
        print("Worker ready; idle mode is active.", flush=True)
        while not stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
            write_heartbeat(settings.data_dir)
    finally:
        os.umask(previous_umask)


def main() -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-worker")
    parser.add_argument("--health-check", action="store_true")
    arguments = parser.parse_args()
    settings = Settings.from_env()
    if arguments.health_check:
        return 0 if is_healthy(settings.data_dir) else 1
    run_worker(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
