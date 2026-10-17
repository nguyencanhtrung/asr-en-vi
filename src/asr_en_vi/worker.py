"""Exclusive durable task worker with process-group cancellation and restart recovery."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from asr_en_vi.config import Settings
from asr_en_vi.recordings import RecordingError, recording_path
from asr_en_vi.storage import initialize
from asr_en_vi.tasks import (
    TaskError,
    claim_next_task,
    fail_task,
    finish_canceled_task,
    finish_interrupted_task,
    publish_complete_generation,
    recover_abandoned_tasks,
    task_runtime_state,
    update_task_progress,
)

HEARTBEAT_INTERVAL_SECONDS = 5
HEARTBEAT_MAX_AGE_SECONDS = 20
TASK_POLL_INTERVAL_SECONDS = 0.5
TASK_PROGRESS_INTERVAL_SECONDS = 1.0
RUNNER_TERM_GRACE_SECONDS = 5.0
RUNNER_KILL_GRACE_SECONDS = 5.0
RUNNER_POST_EOF_GRACE_SECONDS = 2.0
WORKER_LOCK_NAME = ".worker.lock"
WORKER_LOCK_RETRY_SECONDS = 1.0
WORKER_LOCK_RETRY_INTERVAL_SECONDS = 0.05
_HEALTHY_STATES = frozenset({"idle", "running", "stopping"})


class WorkerAlreadyRunning(RuntimeError):
    """Another worker still owns the local processing lock."""


def heartbeat_path(data_dir: Path) -> Path:
    return Path(data_dir) / "worker.liveness"


def worker_lock_path(data_dir: Path) -> Path:
    return Path(data_dir) / WORKER_LOCK_NAME


def acquire_worker_lock(
    data_dir: Path, *, retry_seconds: float = WORKER_LOCK_RETRY_SECONDS
) -> int | None:
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = worker_lock_path(directory)
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    # A health probe briefly holds a shared lock; retry so it cannot make startup exit.
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return descriptor
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(descriptor)
                return None
            time.sleep(WORKER_LOCK_RETRY_INTERVAL_SECONDS)


def _worker_lock_is_held(data_dir: Path) -> bool:
    path = worker_lock_path(data_dir)
    try:
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def write_heartbeat(data_dir: Path, state: str = "idle") -> None:
    if state not in {*_HEALTHY_STATES, "starting", "stopped"}:
        raise ValueError("Unknown worker heartbeat state")
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = heartbeat_path(directory)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".worker-", dir=directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as temporary_file:
            temporary_file.write(f"{state} {time.time_ns()}\n")
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
        status = path.read_text(encoding="ascii").split(maxsplit=1)[0]
        age = (time.time() if now is None else now) - path.stat().st_mtime
    except (OSError, IndexError):
        return False
    return (
        status in _HEALTHY_STATES
        and -1 <= age <= HEARTBEAT_MAX_AGE_SECONDS
        and _worker_lock_is_held(data_dir)
    )


def _group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_and_reap_process_group(
    process: subprocess.Popen[bytes],
    *,
    term_grace_seconds: float = RUNNER_TERM_GRACE_SECONDS,
    kill_grace_seconds: float = RUNNER_KILL_GRACE_SECONDS,
) -> bool:
    """Stop the runner's entire process group and wait until its leader is reaped."""
    process_group_id = process.pid
    if _group_exists(process_group_id):
        with suppress(ProcessLookupError):
            os.killpg(process_group_id, signal.SIGTERM)

    term_deadline = time.monotonic() + term_grace_seconds
    while time.monotonic() < term_deadline:
        process.poll()
        if process.returncode is not None and not _group_exists(process_group_id):
            return True
        time.sleep(0.05)

    if _group_exists(process_group_id):
        with suppress(ProcessLookupError):
            os.killpg(process_group_id, signal.SIGKILL)

    kill_deadline = time.monotonic() + kill_grace_seconds
    while time.monotonic() < kill_deadline:
        process.poll()
        if process.returncode is not None and not _group_exists(process_group_id):
            return True
        time.sleep(0.05)
    process.poll()
    return process.returncode is not None and not _group_exists(process_group_id)


def _safe_runner_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    return environment


def _decode_event(line: bytes) -> dict[str, Any]:
    value = json.loads(line.decode("utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ValueError("Invalid runner event")
    return value


def _run_task(
    settings: Settings,
    lock_fd: int,
    task: dict[str, Any],
    stop_event: threading.Event,
) -> None:
    task_id = str(task["id"])
    owner_id = str(task["owner_id"])
    started = time.monotonic()
    segments: list[dict[str, Any]] = []
    latest_segment_end = 0.0
    language_probability: float | None = None
    completed_event: dict[str, Any] | None = None
    runner_error: dict[str, str] | None = None
    protocol_error = False
    process: subprocess.Popen[bytes] | None = None
    latest_progress_write = 0.0
    latest_heartbeat = 0.0
    stage = "starting_runner"

    try:
        audio_path = recording_path(settings.data_dir, task["meeting_id"])
        update_task_progress(
            settings.data_dir,
            task_id,
            owner_id=owner_id,
            stage=stage,
            elapsed_seconds=0,
            transcript_end_seconds=0,
            segment_count=0,
        )
        runtime_state = task_runtime_state(settings.data_dir, task_id)
        if runtime_state is None or runtime_state[1] != owner_id:
            return
        if runtime_state[0] == "stopping":
            finish_canceled_task(settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=0)
            return

        command = [
            sys.executable,
            "-m",
            "asr_en_vi.runner",
            "--model",
            str(task["model_path"]),
            "--audio",
            str(audio_path),
            "--language",
            str(task["language_hint"]),
            "--device",
            str(task["device"]),
            "--compute-type",
            str(task["compute_type"]),
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
            close_fds=True,
            pass_fds=(lock_fd,),
            start_new_session=True,
            env=_safe_runner_environment(),
        )
        assert process.stdout is not None
        descriptor = process.stdout.fileno()
        pending = bytearray()
        reached_eof = False
        post_eof_deadline: float | None = None
        child_exit_time: float | None = None
        stop_reason: str | None = None

        while not reached_eof or process.poll() is None:
            if reached_eof:
                assert post_eof_deadline is not None
                remaining = max(0.0, post_eof_deadline - time.monotonic())
                stop_event.wait(min(0.2, remaining))
                readable = []
            else:
                readable, _, _ = select.select([descriptor], [], [], 0.2)
            if readable:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    reached_eof = True
                    post_eof_deadline = time.monotonic() + RUNNER_POST_EOF_GRACE_SECONDS
                else:
                    pending.extend(chunk)
                    while b"\n" in pending:
                        raw_line, _, remainder = pending.partition(b"\n")
                        pending = bytearray(remainder)
                        try:
                            event = _decode_event(raw_line)
                            event_type = event["type"]
                            if event_type == "stage" and event.get("stage") in {
                                "loading_model",
                                "transcribing",
                            }:
                                stage = event["stage"]
                            elif event_type == "segment":
                                segment = {
                                    key: value for key, value in event.items() if key != "type"
                                }
                                segments.append(segment)
                                latest_segment_end = max(
                                    latest_segment_end,
                                    float(segment.get("end_seconds") or 0.0),
                                )
                                stage = "transcribing"
                            elif event_type == "complete":
                                completed_event = event
                                language_probability = event.get("language_probability")
                            elif event_type == "error":
                                runner_error = {
                                    "code": str(event.get("code") or "transcription_failed"),
                                    "message": str(
                                        event.get("message")
                                        or "Local transcription failed. Check the worker logs "
                                        "and try again."
                                    ),
                                }
                            else:
                                raise ValueError("Unknown runner event")
                        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                            protocol_error = True
                            break
                    if protocol_error:
                        break
            now = time.monotonic()
            runtime_state = task_runtime_state(settings.data_dir, task_id)
            if runtime_state is None or runtime_state[1] != owner_id:
                stop_reason = "ownership_lost"
            elif runtime_state[0] == "stopping":
                stop_reason = "canceled"
            elif stop_event.is_set():
                stop_reason = "interrupted"
            if stop_reason is not None or protocol_error:
                break
            if now - latest_progress_write >= TASK_PROGRESS_INTERVAL_SECONDS:
                if not update_task_progress(
                    settings.data_dir,
                    task_id,
                    owner_id=owner_id,
                    stage=stage,
                    elapsed_seconds=now - started,
                    transcript_end_seconds=latest_segment_end,
                    segment_count=len(segments),
                ):
                    stop_reason = "ownership_lost"
                    break
                latest_progress_write = now
            if now - latest_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                write_heartbeat(settings.data_dir, "running")
                latest_heartbeat = now
            if process.poll() is not None and child_exit_time is None:
                child_exit_time = now
            if (
                reached_eof
                and process.poll() is None
                and post_eof_deadline is not None
                and now >= post_eof_deadline
            ):
                protocol_error = True
                break
            if child_exit_time is not None and not reached_eof and now - child_exit_time > 2:
                protocol_error = True
                break

        if stop_reason is not None or protocol_error:
            write_heartbeat(settings.data_dir, "stopping")
            reaped = terminate_and_reap_process_group(process)
            if not reaped:
                # Keep the task and slot owned. The loop below retries until the group is gone.
                while not reaped:
                    if stop_event.wait(0.5):
                        pass
                    write_heartbeat(settings.data_dir, "stopping")
                    reaped = terminate_and_reap_process_group(process, term_grace_seconds=0.1)
            if process.stdout is not None:
                process.stdout.close()
            elapsed = time.monotonic() - started
            if stop_reason == "canceled":
                finish_canceled_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            elif stop_reason == "interrupted" or stop_event.is_set():
                finish_interrupted_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            elif protocol_error:
                fail_task(
                    settings.data_dir,
                    task_id,
                    owner_id=owner_id,
                    error_code="runner_protocol_error",
                    message="The local transcription runner returned an invalid result.",
                    elapsed_seconds=elapsed,
                )
            return

        if pending.strip():
            try:
                event = _decode_event(bytes(pending))
                if event.get("type") == "complete":
                    completed_event = event
                    language_probability = event.get("language_probability")
                elif event.get("type") == "error":
                    runner_error = {
                        "code": str(event.get("code") or "transcription_failed"),
                        "message": str(event.get("message") or "Local transcription failed."),
                    }
                else:
                    protocol_error = True
            except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                protocol_error = True

        return_code = process.wait()
        if _group_exists(process.pid):
            if not terminate_and_reap_process_group(process):
                while not terminate_and_reap_process_group(process, term_grace_seconds=0.1):
                    write_heartbeat(settings.data_dir, "stopping")
                    time.sleep(0.5)
            protocol_error = True
        if process.stdout is not None:
            process.stdout.close()
        elapsed = time.monotonic() - started
        runtime_state = task_runtime_state(settings.data_dir, task_id)
        if runtime_state is None or runtime_state[1] != owner_id:
            return
        if runtime_state[0] == "stopping":
            finish_canceled_task(
                settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
            )
            return
        if stop_event.is_set():
            finish_interrupted_task(
                settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
            )
            return
        if runner_error is not None:
            fail_task(
                settings.data_dir,
                task_id,
                owner_id=owner_id,
                error_code=runner_error["code"],
                message=runner_error["message"],
                elapsed_seconds=elapsed,
            )
            return
        if protocol_error or return_code != 0 or completed_event is None:
            fail_task(
                settings.data_dir,
                task_id,
                owner_id=owner_id,
                error_code="transcription_failed",
                message=(
                    "Local transcription did not return a complete result. Check the worker logs "
                    "and try again."
                ),
                elapsed_seconds=elapsed,
            )
            return
        if completed_event.get("segment_count") != len(segments):
            fail_task(
                settings.data_dir,
                task_id,
                owner_id=owner_id,
                error_code="runner_protocol_error",
                message="The local transcription runner returned an incomplete result.",
                elapsed_seconds=elapsed,
            )
            return
        if not update_task_progress(
            settings.data_dir,
            task_id,
            owner_id=owner_id,
            stage="publishing",
            elapsed_seconds=elapsed,
            transcript_end_seconds=latest_segment_end,
            segment_count=len(segments),
        ):
            runtime_state = task_runtime_state(settings.data_dir, task_id)
            if runtime_state is not None and runtime_state[0] == "stopping":
                finish_canceled_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            return
        generation = publish_complete_generation(
            settings.data_dir,
            task_id,
            owner_id=owner_id,
            segments=segments,
            language_probability=language_probability,
            elapsed_seconds=elapsed,
        )
        if generation is None:
            runtime_state = task_runtime_state(settings.data_dir, task_id)
            if (
                runtime_state is not None
                and runtime_state[1] == owner_id
                and runtime_state[0] == "stopping"
            ):
                finish_canceled_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
    except RecordingError:
        fail_task(
            settings.data_dir,
            task_id,
            owner_id=owner_id,
            error_code="recording_unavailable",
            message="Meeting recording is unavailable to the worker.",
            elapsed_seconds=time.monotonic() - started,
        )
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            reaped = terminate_and_reap_process_group(process)
            if not reaped:
                while not terminate_and_reap_process_group(process, term_grace_seconds=0.1):
                    write_heartbeat(settings.data_dir, "stopping")
                    time.sleep(0.5)
            if process.stdout is not None:
                process.stdout.close()
        runtime_state = task_runtime_state(settings.data_dir, task_id)
        elapsed = time.monotonic() - started
        if runtime_state is not None and runtime_state[1] == owner_id:
            if runtime_state[0] == "stopping":
                finish_canceled_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            elif stop_event.is_set():
                finish_interrupted_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            else:
                fail_task(
                    settings.data_dir,
                    task_id,
                    owner_id=owner_id,
                    error_code="runner_start_failed",
                    message="The local transcription runner could not be started.",
                    elapsed_seconds=elapsed,
                )
    except TaskError as error:
        if process is not None:
            reaped = terminate_and_reap_process_group(process)
            if not reaped:
                while not terminate_and_reap_process_group(process, term_grace_seconds=0.1):
                    time.sleep(0.5)
            if process.stdout is not None:
                process.stdout.close()
        fail_task(
            settings.data_dir,
            task_id,
            owner_id=owner_id,
            error_code=error.code,
            message=error.message,
            elapsed_seconds=time.monotonic() - started,
        )
    except Exception:
        if process is not None:
            reaped = terminate_and_reap_process_group(process)
            while not reaped:
                write_heartbeat(settings.data_dir, "stopping")
                reaped = terminate_and_reap_process_group(process, term_grace_seconds=0.1)
                if not reaped:
                    time.sleep(0.5)
            if process.stdout is not None:
                process.stdout.close()
        runtime_state = task_runtime_state(settings.data_dir, task_id)
        elapsed = time.monotonic() - started
        if runtime_state is not None and runtime_state[1] == owner_id:
            if runtime_state[0] == "stopping":
                finish_canceled_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            elif stop_event.is_set():
                finish_interrupted_task(
                    settings.data_dir, task_id, owner_id=owner_id, elapsed_seconds=elapsed
                )
            else:
                fail_task(
                    settings.data_dir,
                    task_id,
                    owner_id=owner_id,
                    error_code="transcription_failed",
                    message="Local transcription failed. Check the worker logs and try again.",
                    elapsed_seconds=elapsed,
                )


def _worker_loop(settings: Settings, lock_fd: int, stop_event: threading.Event) -> None:
    last_heartbeat = 0.0
    while not stop_event.is_set():
        now = time.monotonic()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
            write_heartbeat(settings.data_dir, "idle")
            last_heartbeat = now
        task = claim_next_task(settings.data_dir, owner_id=uuid.uuid4().hex)
        if task is None:
            stop_event.wait(TASK_POLL_INTERVAL_SECONDS)
            continue
        write_heartbeat(settings.data_dir, "running")
        last_heartbeat = time.monotonic()
        _run_task(settings, lock_fd, task, stop_event)
        write_heartbeat(settings.data_dir, "idle")
        last_heartbeat = time.monotonic()


def run_worker(settings: Settings) -> None:
    previous_umask = os.umask(0o077)
    stop_event = threading.Event()
    previous_handlers = {
        signum: signal.signal(signum, lambda *_: stop_event.set())
        for signum in (signal.SIGTERM, signal.SIGINT)
    }
    lock_fd: int | None = None
    try:
        initialize(settings.data_dir)
        lock_fd = acquire_worker_lock(settings.data_dir)
        if lock_fd is None:
            raise WorkerAlreadyRunning("Another worker still owns the local processing lock.")
        write_heartbeat(settings.data_dir, "starting")
        recover_abandoned_tasks(settings.data_dir)
        write_heartbeat(settings.data_dir, "idle")
        _worker_loop(settings, lock_fd, stop_event)
    finally:
        with suppress(OSError):
            write_heartbeat(settings.data_dir, "stopped")
        if lock_fd is not None:
            os.close(lock_fd)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        os.umask(previous_umask)


def main() -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-worker")
    parser.add_argument("--health-check", action="store_true")
    arguments = parser.parse_args()
    settings = Settings.from_env()
    if arguments.health_check:
        return 0 if is_healthy(settings.data_dir) else 1
    try:
        run_worker(settings)
    except WorkerAlreadyRunning as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
