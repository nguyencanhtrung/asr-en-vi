from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest
from notes_helpers import StubNotesProvider, seed_completed_transcript

from asr_en_vi import worker
from asr_en_vi.config import Settings
from asr_en_vi.notes import accept_notes_task, notes_state
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import TaskError, cancel_task, claim_next_task
from asr_en_vi.worker import acquire_worker_lock, heartbeat_path


def _accept(data_dir: Path, meeting_id: str, generation_id: str, request_id: str):
    return accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id=request_id,
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=True,
    )


def test_notes_worker_keeps_stopping_slot_until_local_child_is_reaped(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    other_meeting, other_generation, _ = seed_completed_transcript(data_dir, title="Other meeting")
    accepted = _accept(data_dir, meeting_id, generation_id, "notes-worker-request-001")
    task = claim_next_task(data_dir, owner_id="worker-owner")
    assert task is not None and task["id"] == accepted["id"]
    settings = Settings(data_dir=data_dir, auth_dir=tmp_path / "auth")
    lock_fd = acquire_worker_lock(data_dir)
    assert lock_fd is not None
    marker = tmp_path / "notes-child-started"
    monkeypatch.setattr(
        worker,
        "_notes_command",
        lambda *_args: [
            sys.executable,
            "-c",
            "import os,pathlib,sys,time; "
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)",
            str(marker),
        ],
    )
    reaper_entered = threading.Event()
    release_reaper = threading.Event()
    original_reaper = worker.terminate_and_reap_process_group
    observed_process = []

    def pause_before_reaping(process, **_kwargs):
        observed_process.append(process)
        reaper_entered.set()
        assert release_reaper.wait(timeout=5)
        return original_reaper(process, term_grace_seconds=0.2, kill_grace_seconds=1.0)

    monkeypatch.setattr(worker, "terminate_and_reap_process_group", pause_before_reaping)
    runner_thread = threading.Thread(
        target=worker._run_notes_task,
        args=(settings, lock_fd, task, threading.Event()),
    )
    runner_thread.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.02)
        assert marker.exists(), "The notes child did not start."
        child_pid = int(marker.read_text(encoding="ascii"))
        assert cancel_task(data_dir, accepted["id"])["status"] == "stopping"
        assert reaper_entered.wait(timeout=5), "The worker did not begin child shutdown."
        assert heartbeat_path(data_dir).read_text(encoding="ascii").startswith("stopping ")
        with sqlite3.connect(database_path(data_dir)) as connection:
            assert connection.execute(
                "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
            ).fetchone() == (accepted["id"],)

        with pytest.raises(TaskError) as busy:
            _accept(data_dir, other_meeting, other_generation, "notes-worker-request-002")
        assert busy.value.code == "system_busy"

        release_reaper.set()
        runner_thread.join(timeout=8)
        assert not runner_thread.is_alive()
        assert notes_state(data_dir, meeting_id)["task"]["status"] == "canceled"
        assert notes_state(data_dir, meeting_id)["revisions"] == []
        with sqlite3.connect(database_path(data_dir)) as connection:
            assert connection.execute(
                "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
            ).fetchone() == (None,)
        assert child_pid is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        release_reaper.set()
        runner_thread.join(timeout=8)
        if runner_thread.is_alive() and observed_process:
            original_reaper(
                observed_process[0],
                term_grace_seconds=0.2,
                kill_grace_seconds=1.0,
            )
        os.close(lock_fd)
