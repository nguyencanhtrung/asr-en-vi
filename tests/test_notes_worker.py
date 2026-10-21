from __future__ import annotations

import json
import os
import signal
import sqlite3
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

import pytest
from notes_helpers import StubNotesProvider, seed_completed_transcript

from asr_en_vi import worker
from asr_en_vi.config import Settings
from asr_en_vi.notes import accept_notes_task, notes_state
from asr_en_vi.notes_document import LEGACY_ENGLISH_PROMPT_VERSION, PROMPT_VERSION
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import TaskError, cancel_task, claim_next_task
from asr_en_vi.worker import acquire_worker_lock, heartbeat_path

_COVERAGE = {
    "version": 1,
    "segment_count": 2,
    "chunks": [
        {"index": 1, "owned": [0, 2], "overlap": None, "parts": [], "provider_call_index": 1}
    ],
}


def _child_printing(*events):
    """A notes child that prints the given events, one JSON line each, and exits."""
    lines = "".join(json.dumps(event) + "\n" for event in events)
    return lambda *_args: [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write(sys.argv[1])",
        lines,
    ]


def _accept(
    data_dir: Path,
    meeting_id: str,
    generation_id: str,
    request_id: str,
    *,
    output_language: str = "en",
):
    return accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id=request_id,
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=True,
        output_language=output_language,
    )


def test_notes_runner_uses_the_durable_language_pin_for_provider_and_render(
    tmp_path, monkeypatch, capsys
):
    from asr_en_vi import notes_runner

    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    accepted = _accept(
        data_dir,
        meeting_id,
        generation_id,
        "notes-runner-language-vi",
        output_language="vi",
    )
    claimed = claim_next_task(data_dir, owner_id="notes-runner-language-owner")
    assert claimed is not None and claimed["id"] == accepted["id"]
    monkeypatch.setenv("ASR_PROVIDER_DIR", str(tmp_path / "provider"))
    provider_calls = []
    render_calls = []

    class StubProvider:
        def __init__(self, _directory, *, callback_url):
            assert callback_url == ""

        def generate_notes_document(self, **kwargs):
            provider_calls.append(kwargs)
            kwargs["on_coverage"](_COVERAGE)
            return {"schema_version": 1}

    def render(_document, _snapshot, *, output_language):
        render_calls.append(output_language)
        return "## Tổng quan\n\nBản tóm tắt.\n"

    monkeypatch.setattr(notes_runner, "ChatGPTProvider", StubProvider)
    monkeypatch.setattr(notes_runner, "render_markdown", render)

    assert notes_runner.run_notes_task(data_dir, accepted["id"], "notes-runner-language-owner") == 0
    output = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert output == {
        "type": "result",
        "markdown": "## Tổng quan\n\nBản tóm tắt.\n",
        "coverage": _COVERAGE,
    }
    assert provider_calls[0]["output_language"] == "vi"
    assert render_calls == ["vi"]


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


def test_notes_task_deadline_reaps_child_and_publishes_no_partial_revision(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    accepted = _accept(data_dir, meeting_id, generation_id, "notes-worker-deadline-001")
    task = claim_next_task(data_dir, owner_id="worker-deadline-owner")
    assert task is not None and task["id"] == accepted["id"]
    settings = Settings(data_dir=data_dir, auth_dir=tmp_path / "auth")
    lock_fd = acquire_worker_lock(data_dir)
    assert lock_fd is not None
    marker = tmp_path / "notes-deadline-child-started"
    monkeypatch.setattr(worker, "NOTES_TASK_TIMEOUT_SECONDS", 0.2)
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
    runner_thread = threading.Thread(
        target=worker._run_notes_task,
        args=(settings, lock_fd, task, threading.Event()),
    )
    runner_thread.start()
    child_pid = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.02)
        assert marker.exists(), "The notes child did not start."
        child_pid = int(marker.read_text(encoding="ascii"))
        runner_thread.join(timeout=8)
        assert not runner_thread.is_alive()

        state = notes_state(data_dir, meeting_id)
        assert state["task"]["status"] == "failed"
        assert state["task"]["error_code"] == "notes_timeout"
        assert state["revisions"] == []
        with sqlite3.connect(database_path(data_dir)) as connection:
            assert connection.execute(
                "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
            ).fetchone() == (None,)
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        runner_thread.join(timeout=8)
        if runner_thread.is_alive() and child_pid is not None:
            with suppress(ProcessLookupError):
                os.kill(child_pid, signal.SIGKILL)
            runner_thread.join(timeout=8)
        os.close(lock_fd)


def _run_child_through_worker(tmp_path, monkeypatch, request_id, *events):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    accepted = _accept(data_dir, meeting_id, generation_id, request_id)
    task = claim_next_task(data_dir, owner_id="worker-coverage-owner")
    assert task is not None and task["id"] == accepted["id"]
    settings = Settings(data_dir=data_dir, auth_dir=tmp_path / "auth")
    lock_fd = acquire_worker_lock(data_dir)
    assert lock_fd is not None
    monkeypatch.setattr(worker, "_notes_command", _child_printing(*events))
    try:
        worker._run_notes_task(settings, lock_fd, task, threading.Event())
    finally:
        os.close(lock_fd)
    return data_dir, meeting_id


def test_notes_worker_publishes_the_result_with_its_coverage_manifest(tmp_path, monkeypatch):
    data_dir, meeting_id = _run_child_through_worker(
        tmp_path,
        monkeypatch,
        "notes-worker-coverage-001",
        {"type": "stage", "stage": "generating_notes"},
        {"type": "result", "markdown": "## Overview\n\nDone.\n", "coverage": _COVERAGE},
    )

    state = notes_state(data_dir, meeting_id)
    assert state["task"]["status"] == "succeeded"
    assert len(state["revisions"]) == 1
    with sqlite3.connect(database_path(data_dir)) as connection:
        stored = connection.execute("SELECT coverage_json FROM notes_revisions").fetchone()[0]
    assert json.loads(stored) == _COVERAGE


@pytest.mark.parametrize("coverage", [None, {}, "all", [], {"chunks": [{"index": 1}]}])
def test_notes_worker_publishes_no_revision_for_a_result_without_proven_coverage(
    tmp_path, monkeypatch, coverage
):
    result = {"type": "result", "markdown": "## Overview\n\nLooks complete.\n"}
    if coverage is not None:
        result["coverage"] = coverage
    data_dir, meeting_id = _run_child_through_worker(
        tmp_path,
        monkeypatch,
        "notes-worker-coverage-002",
        {"type": "stage", "stage": "generating_notes"},
        result,
    )

    state = notes_state(data_dir, meeting_id)
    assert state["task"]["status"] == "failed"
    assert state["revisions"] == []
    with sqlite3.connect(database_path(data_dir)) as connection:
        assert connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone() == (None,)


@pytest.mark.parametrize(
    ("prompt_version", "language", "runs"),
    [
        (PROMPT_VERSION, "en", True),
        (PROMPT_VERSION, "vi", True),
        (LEGACY_ENGLISH_PROMPT_VERSION, "en", True),
        (LEGACY_ENGLISH_PROMPT_VERSION, "vi", False),
        ("notes-hierarchical-v5", "en", False),
    ],
)
def test_notes_runner_runs_only_the_current_prompt_and_the_legacy_english_contract(
    tmp_path, monkeypatch, capsys, prompt_version, language, runs
):
    from asr_en_vi import notes_runner

    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    accepted = _accept(
        data_dir, meeting_id, generation_id, "prompt-contract", output_language=language
    )
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "UPDATE tasks SET notes_prompt_version = ? WHERE id = ?",
            (prompt_version, accepted["id"]),
        )
    claim_next_task(data_dir, owner_id="prompt-contract-owner")
    monkeypatch.setenv("ASR_PROVIDER_DIR", str(tmp_path / "provider"))

    class StubProvider:
        def __init__(self, _directory, *, callback_url):
            pass

        def generate_notes_document(self, **kwargs):
            kwargs["on_coverage"](_COVERAGE)
            return {"schema_version": 1}

    monkeypatch.setattr(notes_runner, "ChatGPTProvider", StubProvider)
    monkeypatch.setattr(notes_runner, "render_markdown", lambda *_args, **_kwargs: "## Notes\n")

    code = notes_runner.run_notes_task(data_dir, accepted["id"], "prompt-contract-owner")

    event = json.loads(capsys.readouterr().out.splitlines()[-1])
    if runs:
        assert (code, event["type"]) == (0, "result")
    else:
        assert (code, event["type"], event["code"]) == (1, "error", "notes_contract_changed")
