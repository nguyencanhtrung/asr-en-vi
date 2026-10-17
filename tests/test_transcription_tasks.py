from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from seeding import seed_meeting

from asr_en_vi.storage import database_path, initialize
from asr_en_vi.tasks import (
    TaskError,
    accept_transcription_task,
    cancel_task,
    claim_next_task,
    fail_task,
    finish_canceled_task,
    finish_interrupted_task,
    publish_complete_generation,
    recover_abandoned_tasks,
    transcription_state,
    update_task_progress,
)
from asr_en_vi.worker import acquire_worker_lock


def _task_store(tmp_path: Path, *, meeting_count: int = 1):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.bin").write_bytes(b"model")
    (model_dir / "config.json").write_text(
        json.dumps({"lang_ids": [], "suppress_ids": [], "suppress_ids_begin": []}),
        encoding="utf-8",
    )
    (model_dir / "tokenizer.json").write_text(
        json.dumps({"model": {"type": "BPE"}}), encoding="utf-8"
    )
    (model_dir / "preprocessor_config.json").write_text(
        json.dumps(
            {
                "feature_size": 128,
                "sampling_rate": 16000,
                "hop_length": 160,
                "n_fft": 400,
                "chunk_length": 30,
            }
        ),
        encoding="utf-8",
    )
    meetings = [seed_meeting(data_dir, f"Meeting {index}") for index in range(meeting_count)]
    return data_dir, model_dir, meetings


def _accept(data_dir: Path, model_dir: Path, meeting_id: str, request_id: str):
    return accept_transcription_task(
        data_dir,
        meeting_id=meeting_id,
        request_id=request_id,
        model_path=model_dir,
        device="cpu",
        compute_type="int8",
        worker_ready=True,
    )


def _segment(segment_id: str, **overrides):
    return {
        "id": segment_id,
        "start_seconds": 1.25,
        "end_seconds": 2.5,
        "text": "A saved utterance.",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
        **overrides,
    }


def test_request_id_returns_original_task_and_rejects_payload_reuse(tmp_path):
    data_dir, model_dir, (first_meeting, second_meeting) = _task_store(tmp_path, meeting_count=2)
    accepted = _accept(data_dir, model_dir, first_meeting, "request-0001")

    retry = accept_transcription_task(
        data_dir,
        meeting_id=first_meeting,
        request_id="request-0001",
        model_path=tmp_path / "changed-server-model",
        device="cuda",
        compute_type="float16",
        worker_ready=False,
    )
    assert retry["id"] == accepted["id"]
    assert retry["status"] == "accepted"
    assert retry["request_id"] == "request-0001"

    with pytest.raises(TaskError) as error:
        _accept(data_dir, model_dir, second_meeting, "request-0001")
    assert error.value.code == "idempotency_conflict"


def test_server_computes_stale_worker_state_for_active_task(tmp_path):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "heartbeat-0001")
    assert task["worker_state"] == "checking-worker"
    claimed = claim_next_task(data_dir, owner_id="worker-owner")
    assert claimed and claimed["id"] == task["id"]
    assert transcription_state(data_dir, meeting_id)["task"]["worker_state"] == "healthy"

    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "UPDATE tasks SET heartbeat_at = '2000-01-01 00:00:00' WHERE id = ?",
            (task["id"],),
        )
    stale = transcription_state(data_dir, meeting_id)["task"]
    assert stale["worker_state"] == "checking-worker"


def test_concurrent_acceptance_claims_only_one_global_slot(tmp_path):
    data_dir, model_dir, meetings = _task_store(tmp_path, meeting_count=2)
    barrier = threading.Barrier(2)

    def attempt(index: int):
        barrier.wait(timeout=5)
        try:
            return _accept(data_dir, model_dir, meetings[index], f"request-{index:04d}")
        except TaskError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        accepted = list(executor.map(attempt, range(2)))

    assert sum(isinstance(item, dict) for item in accepted) == 1
    assert sum(item == "system_busy" for item in accepted) == 1

    barrier = threading.Barrier(2)

    def claim(index: int):
        barrier.wait(timeout=5)
        return claim_next_task(data_dir, owner_id=f"worker-{index}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(claim, range(2)))
    assert sum(item is not None for item in claimed) == 1


def test_progress_requires_current_owner_and_reports_measured_values(tmp_path):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "progress-0001")
    claimed = claim_next_task(data_dir, owner_id="worker-owner")
    assert claimed and claimed["id"] == task["id"]

    assert (
        publish_complete_generation(
            data_dir,
            task["id"],
            owner_id="stale-owner",
            segments=[_segment("a" * 32)],
            language_probability=0.9,
            elapsed_seconds=10.0,
        )
        is None
    )
    assert not update_task_progress(
        data_dir,
        task["id"],
        owner_id="stale-owner",
        stage="transcribing",
        elapsed_seconds=10.2,
        transcript_end_seconds=14.5,
        segment_count=3,
    )
    assert update_task_progress(
        data_dir,
        task["id"],
        owner_id="worker-owner",
        stage="transcribing",
        elapsed_seconds=10.2,
        transcript_end_seconds=14.5,
        segment_count=3,
    )
    current = transcription_state(data_dir, meeting_id)["task"]
    assert current["stage"] == "transcribing"
    assert current["elapsed_seconds"] == 10.2
    assert current["transcript_end_seconds"] == 14.5
    assert current["segment_count"] == 3
    assert "model_path" not in current and "owner_id" not in current


def test_cancel_holds_slot_and_rejects_late_generation_until_runner_reaped(tmp_path):
    data_dir, model_dir, meetings = _task_store(tmp_path, meeting_count=2)
    task = _accept(data_dir, model_dir, meetings[0], "cancel-0001")
    claim_next_task(data_dir, owner_id="worker-owner")

    stopping = cancel_task(data_dir, task["id"])
    assert stopping["status"] == "stopping"
    with pytest.raises(TaskError) as error:
        _accept(data_dir, model_dir, meetings[1], "cancel-0002")
    assert error.value.code == "system_busy"

    late_result = publish_complete_generation(
        data_dir,
        task["id"],
        owner_id="worker-owner",
        segments=[_segment("a" * 32)],
        language_probability=0.9,
        elapsed_seconds=3.0,
    )
    assert late_result is None
    assert transcription_state(data_dir, meetings[0])["generation"] is None
    with sqlite3.connect(database_path(data_dir)) as connection:
        assert connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone() == (task["id"],)

    assert finish_canceled_task(data_dir, task["id"], owner_id="worker-owner", elapsed_seconds=4.0)
    assert cancel_task(data_dir, task["id"])["status"] == "canceled"
    accepted_after_reap = _accept(data_dir, model_dir, meetings[1], "cancel-0002")
    assert accepted_after_reap["status"] == "accepted"


def test_error_finalization_honors_cancel_and_releases_reaped_slot(tmp_path):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "cancel-error-0001")
    claim_next_task(data_dir, owner_id="worker-owner")
    assert cancel_task(data_dir, task["id"])["status"] == "stopping"

    assert fail_task(
        data_dir,
        task["id"],
        owner_id="worker-owner",
        error_code="transcription_failed",
        message="Runner failed as the user canceled.",
        elapsed_seconds=2.0,
    )
    assert cancel_task(data_dir, task["id"])["status"] == "canceled"
    with sqlite3.connect(database_path(data_dir)) as connection:
        assert connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone() == (None,)


def test_worker_shutdown_finalization_honors_cancel_after_reap(tmp_path):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "cancel-shutdown-0001")
    claim_next_task(data_dir, owner_id="worker-owner")
    assert cancel_task(data_dir, task["id"])["status"] == "stopping"

    assert finish_interrupted_task(
        data_dir, task["id"], owner_id="worker-owner", elapsed_seconds=2.0
    )
    assert cancel_task(data_dir, task["id"])["status"] == "canceled"


def test_complete_generations_are_atomic_stable_and_preserve_previous_current(tmp_path):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    first = _accept(data_dir, model_dir, meeting_id, "generation-001")
    claim_next_task(data_dir, owner_id="owner-1")
    result = publish_complete_generation(
        data_dir,
        first["id"],
        owner_id="owner-1",
        segments=[
            _segment("1" * 32),
            _segment(
                "2" * 32,
                start_seconds=2.5,
                end_seconds=3.75,
                text="Review this line.",
                avg_logprob=-1.2,
                no_speech_prob=0.7,
                compression_ratio=2.5,
            ),
        ],
        language_probability=0.91,
        elapsed_seconds=12.5,
    )
    assert result and result["status"] == "complete"
    assert result["segment_count"] == 2

    state = transcription_state(data_dir, meeting_id)
    assert state["task"]["status"] == "succeeded"
    assert state["task"]["result_scope"] == "transcript_only"
    assert state["generation"]["generation_number"] == 1
    assert state["generation"]["language_probability"] == 0.91
    assert [segment["id"] for segment in state["generation"]["segments"]] == [
        "1" * 32,
        "2" * 32,
    ]
    assert state["generation"]["segments"][1]["uncertain"] is True
    assert state["generation"]["segments"][1]["avg_logprob"] == -1.2

    failed = _accept(data_dir, model_dir, meeting_id, "generation-002")
    claim_next_task(data_dir, owner_id="owner-2")
    fail_task(
        data_dir,
        failed["id"],
        owner_id="owner-2",
        error_code="transcription_failed",
        message="Failed before a complete transcript was returned.",
        elapsed_seconds=2.0,
    )
    assert transcription_state(data_dir, meeting_id)["generation"]["id"] == result["id"]

    rerun = _accept(data_dir, model_dir, meeting_id, "generation-003")
    claim_next_task(data_dir, owner_id="owner-3")
    second = publish_complete_generation(
        data_dir,
        rerun["id"],
        owner_id="owner-3",
        segments=[_segment("3" * 32, text="A later generation.")],
        language_probability=0.88,
        elapsed_seconds=8.0,
    )
    current = transcription_state(data_dir, meeting_id)
    assert second and second["generation_number"] == 2
    assert current["generation"]["id"] == second["id"]
    assert current["generation"]["segments"][0]["id"] == "3" * 32
    with sqlite3.connect(database_path(data_dir)) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM transcript_generations WHERE meeting_id = ?",
            (meeting_id,),
        ).fetchone() == (2,)


def test_new_exclusive_worker_recovery_cancels_stopping_and_interrupts_other_active_work(
    tmp_path,
):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "recovery-001")
    claim_next_task(data_dir, owner_id="old-worker")
    cancel_task(data_dir, task["id"])

    lock_fd = acquire_worker_lock(data_dir)
    assert lock_fd is not None
    try:
        assert recover_abandoned_tasks(data_dir) == [task["id"]]
    finally:
        import os

        os.close(lock_fd)

    recovered = transcription_state(data_dir, meeting_id)["task"]
    assert recovered["status"] == "canceled"
    assert recovered["stage"] == "canceled"
    assert recovered["error_code"] is None
    assert recovered["completed_at"]
    assert _active_slot(data_dir) is None
    assert transcription_state(data_dir, meeting_id)["generation"] is None
    assert claim_next_task(data_dir, owner_id="new-worker") is None


@pytest.mark.parametrize("claimed", [False, True])
def test_new_exclusive_worker_recovery_interrupts_accepted_and_running_tasks(tmp_path, claimed):
    data_dir, model_dir, (meeting_id,) = _task_store(tmp_path)
    task = _accept(data_dir, model_dir, meeting_id, "recovery-002")
    if claimed:
        claim_next_task(data_dir, owner_id="old-worker")

    assert recover_abandoned_tasks(data_dir) == [task["id"]]

    recovered = transcription_state(data_dir, meeting_id)["task"]
    assert recovered["status"] == "interrupted"
    assert recovered["error_code"] == "worker_restarted"
    assert _active_slot(data_dir) is None
    assert transcription_state(data_dir, meeting_id)["generation"] is None
    assert claim_next_task(data_dir, owner_id="new-worker") is None


def _active_slot(data_dir: Path):
    with sqlite3.connect(database_path(data_dir)) as connection:
        return connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()[0]
