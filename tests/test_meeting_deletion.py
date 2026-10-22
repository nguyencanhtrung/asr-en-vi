from __future__ import annotations

import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from notes_helpers import StubNotesProvider, rerun_transcript, seed_completed_transcript
from seeding import prepare_diarization_model, seed_meeting

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.meeting_deletion import (
    MeetingDeletionError,
    delete_meeting,
    recover_pending_meeting_deletions,
)
from asr_en_vi.notes import accept_notes_task, publish_notes_revision
from asr_en_vi.recordings import get_meeting
from asr_en_vi.storage import database_path, initialize
from asr_en_vi.tasks import (
    TaskError,
    accept_transcription_task,
    cancel_task,
    claim_next_task,
    publish_complete_generation,
    update_task_progress,
)

pytestmark = pytest.mark.anyio


async def _authorize(client: AsyncClient, settings: Settings) -> dict[str, str]:
    headers = {"Origin": settings.public_url}
    token = AuthStore(settings.auth_dir).load().token
    response = await client.post("/api/access/session", headers=headers, json={"token": token})
    assert response.status_code == 204
    return headers


def _audio_artifacts(data_dir: Path, meeting_id: str) -> dict[str, Path]:
    with sqlite3.connect(database_path(data_dir)) as connection:
        row = connection.execute(
            "SELECT uploads.id, uploads.raw_key, uploads.managed_key, recordings.storage_key "
            "FROM recordings JOIN uploads ON uploads.id = recordings.upload_id "
            "WHERE recordings.meeting_id = ?",
            (meeting_id,),
        ).fetchone()
    assert row is not None
    upload_id, raw_key, managed_key, storage_key = row
    assert managed_key == storage_key
    paths = {
        "raw": data_dir / raw_key,
        "audio": data_dir / storage_key,
        "temp": data_dir / ".recording-tmp" / f"{upload_id}-0123456789abcdef.m4a",
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"managed {name} for {meeting_id}".encode())
    return paths


def _task_model(tmp_path: Path) -> tuple[Path, Path]:
    model_dir = tmp_path / "whisper-model"
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
    diarization_dir = prepare_diarization_model(tmp_path / "diarization-model")
    return model_dir, diarization_dir


def _accept_transcription(data_dir: Path, model_dir: Path, diarization_dir: Path, meeting_id: str):
    return accept_transcription_task(
        data_dir,
        meeting_id=meeting_id,
        request_id=f"delete-race-{meeting_id}",
        model_path=model_dir,
        diarization_model_path=diarization_dir,
        device="cpu",
        compute_type="int8",
        worker_ready=True,
    )


def _race(start: threading.Barrier, operation):
    start.wait(timeout=5)
    try:
        return ("ok", operation())
    except (MeetingDeletionError, TaskError) as error:
        return ("error", error.code)


async def test_delete_removes_all_meeting_data_and_managed_files_only(client, settings, tmp_path):
    headers = await _authorize(client, settings)
    meeting_id, _generation_id, _ = seed_completed_transcript(
        settings.data_dir, title="Remove this meeting"
    )
    rerun_transcript(settings.data_dir, meeting_id)
    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        generation_id = connection.execute(
            "SELECT current_generation_id FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()[0]
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM transcript_generations WHERE meeting_id = ?", (meeting_id,)
            ).fetchone()[0]
            == 2
        )
    # Keep a prior transcript generation and a notes revision to exercise FK order.
    notes_task = accept_notes_task(
        settings.data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id="delete-notes-revision",
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=True,
    )
    claim_next_task(settings.data_dir, owner_id="delete-notes-worker")
    publish_notes_revision(
        settings.data_dir,
        notes_task["id"],
        owner_id="delete-notes-worker",
        markdown="# Meeting notes\n\nA saved decision.\n",
        elapsed_seconds=0.1,
    )
    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        connection.execute("UPDATE notes_preferences SET provider = 'antigravity' WHERE id = 1")

    other_meeting = seed_meeting(settings.data_dir, "Keep this meeting", "2026-10-20")
    owned = _audio_artifacts(settings.data_dir, meeting_id)
    other_owned = _audio_artifacts(settings.data_dir, other_meeting)
    external_source = tmp_path / "original-source.wav"
    external_source.write_bytes(b"keep the operator's original source")

    response = await client.request(
        "DELETE",
        f"/api/meetings/{meeting_id}",
        headers=headers,
        json={"target": str(external_source)},
    )

    assert response.status_code == 200
    assert response.json() == {"meeting_id": meeting_id, "status": "deleted"}
    for path in owned.values():
        assert not path.exists()
    for path in other_owned.values():
        assert path.exists()
    assert external_source.read_bytes() == b"keep the operator's original source"
    assert (await client.get(f"/api/meetings/{meeting_id}")).status_code == 404
    assert (await client.get(f"/api/meetings/{other_meeting}")).status_code == 200
    history = (await client.get("/api/meetings")).json()
    assert [meeting["id"] for meeting in history["meetings"]] == [other_meeting]
    assert [meeting["id"] for meeting in history["recent"]] == [other_meeting]
    search = (await client.get("/api/meetings", params={"q": "Remove this meeting"})).json()
    assert search["meetings"] == []
    assert search["total"] == 1
    assert [meeting["id"] for meeting in search["recent"]] == [other_meeting]

    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE meeting_id = ?", (meeting_id,)
            ).fetchone()[0]
            for table in ("tasks", "transcript_generations", "notes_sources", "notes_revisions")
        }
        transcript_rows = connection.execute(
            "SELECT COUNT(*) FROM transcript_segments WHERE generation_id IN "
            "(SELECT id FROM transcript_generations WHERE meeting_id = ?)",
            (meeting_id,),
        ).fetchone()[0]
        speaker_rows = connection.execute(
            "SELECT COUNT(*) FROM generation_speakers WHERE generation_id IN "
            "(SELECT id FROM transcript_generations WHERE meeting_id = ?)",
            (meeting_id,),
        ).fetchone()[0]
        upload_rows = connection.execute(
            "SELECT COUNT(*) FROM uploads WHERE id IN "
            "(SELECT upload_id FROM recordings WHERE meeting_id = ?)",
            (meeting_id,),
        ).fetchone()[0]
        meeting_count = connection.execute(
            "SELECT COUNT(*) FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()[0]
        other_count = connection.execute(
            "SELECT COUNT(*) FROM meetings WHERE id = ?", (other_meeting,)
        ).fetchone()[0]
        provider_preference = connection.execute(
            "SELECT provider FROM notes_preferences WHERE id = 1"
        ).fetchone()[0]
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    assert counts == {
        "tasks": 0,
        "transcript_generations": 0,
        "notes_sources": 0,
        "notes_revisions": 0,
    }
    assert (transcript_rows, speaker_rows, upload_rows) == (0, 0, 0)
    assert (meeting_count, other_count, provider_preference, foreign_key_violations) == (
        0,
        1,
        "antigravity",
        [],
    )


@pytest.mark.parametrize("state", ["accepted", "running", "stopping"])
async def test_delete_rejects_each_active_transcription_state(client, settings, tmp_path, state):
    headers = await _authorize(client, settings)
    meeting_id = seed_meeting(settings.data_dir, f"Active {state}")
    model_dir, diarization_dir = _task_model(tmp_path)
    task = _accept_transcription(settings.data_dir, model_dir, diarization_dir, meeting_id)
    if state in {"running", "stopping"}:
        claim_next_task(settings.data_dir, owner_id=f"active-{state}-worker")
    if state == "stopping":
        cancel_task(settings.data_dir, task["id"])

    response = await client.delete(f"/api/meetings/{meeting_id}", headers=headers)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "meeting_task_active"
    assert "cancel" in detail["message"].lower() and "wait" in detail["message"].lower()
    assert (await client.get(f"/api/meetings/{meeting_id}")).status_code == 200


async def test_active_notes_task_also_blocks_meeting_deletion(client, settings):
    headers = await _authorize(client, settings)
    meeting_id, generation_id, _ = seed_completed_transcript(settings.data_dir)
    accept_notes_task(
        settings.data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id="active-notes-block-delete",
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=True,
    )

    response = await client.delete(f"/api/meetings/{meeting_id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "meeting_task_active"
    assert (await client.get(f"/api/meetings/{meeting_id}")).status_code == 200


async def test_delete_api_requires_an_authenticated_session(client, settings):
    meeting_id = seed_meeting(settings.data_dir, "Authentication guard")

    response = await client.delete(
        f"/api/meetings/{meeting_id}", headers={"Origin": settings.public_url}
    )

    assert response.status_code == 401
    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        assert (
            connection.execute(
                "SELECT deletion_requested_at FROM meetings WHERE id = ?", (meeting_id,)
            ).fetchone()[0]
            is None
        )


async def test_symlinked_managed_directory_fails_safely_and_keeps_mark_for_both_task_kinds(
    client, settings, tmp_path
):
    headers = await _authorize(client, settings)
    meeting_id, generation_id, _ = seed_completed_transcript(settings.data_dir)
    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        upload_id = connection.execute(
            "SELECT upload_id FROM recordings WHERE meeting_id = ?", (meeting_id,)
        ).fetchone()[0]
    outside = tmp_path / "outside"
    outside.mkdir()
    external_file = outside / f"{upload_id}.part"
    external_file.write_bytes(b"outside target")
    upload_dir = settings.data_dir / "uploads"
    upload_dir.rmdir()
    upload_dir.symlink_to(outside, target_is_directory=True)

    response = await client.delete(f"/api/meetings/{meeting_id}", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "meeting_deletion_cleanup_failed"
    assert external_file.read_bytes() == b"outside target"
    meeting = get_meeting(settings.data_dir, meeting_id)
    assert meeting["deletion_status"] == "failed"

    with pytest.raises(TaskError, match="being deleted") as transcription_error:
        _accept_transcription(
            settings.data_dir, Path("unused-model"), Path("unused-diarization"), meeting_id
        )
    assert transcription_error.value.code == "meeting_deletion_pending"
    with pytest.raises(TaskError, match="being deleted") as notes_error:
        accept_notes_task(
            settings.data_dir,
            provider=StubNotesProvider(),
            meeting_id=meeting_id,
            request_id="notes-after-delete-mark",
            expected_generation_id=generation_id,
            expected_source_version=1,
            expected_metadata_version=1,
            worker_ready=True,
        )
    assert notes_error.value.code == "meeting_deletion_pending"

    upload_dir.unlink()
    upload_dir.mkdir()
    retry = await client.delete(f"/api/meetings/{meeting_id}", headers=headers)
    assert retry.status_code == 200
    assert external_file.read_bytes() == b"outside target"


@pytest.mark.parametrize("data_path_kind", ["real", "symlinked_root", "symlinked_ancestor"])
def test_delete_resolves_real_and_symlinked_data_roots(tmp_path, data_path_kind):
    physical_parent = tmp_path / "physical-parent"
    physical_parent.mkdir()
    real_data_dir = physical_parent / "data"
    initialize(real_data_dir)
    meeting_id = seed_meeting(real_data_dir, f"Delete through {data_path_kind}")
    owned = _audio_artifacts(real_data_dir, meeting_id)
    external_file = tmp_path / "external-source.m4a"
    external_file.write_bytes(b"keep outside data")

    if data_path_kind == "real":
        configured_data_dir = real_data_dir
    elif data_path_kind == "symlinked_root":
        configured_data_dir = tmp_path / "linked-data"
        configured_data_dir.symlink_to(real_data_dir, target_is_directory=True)
    else:
        linked_parent = tmp_path / "linked-parent"
        linked_parent.symlink_to(physical_parent, target_is_directory=True)
        configured_data_dir = linked_parent / "data"

    assert delete_meeting(configured_data_dir, meeting_id) == {
        "meeting_id": meeting_id,
        "status": "deleted",
    }
    assert all(not path.exists() for path in owned.values())
    assert external_file.read_bytes() == b"keep outside data"
    with sqlite3.connect(database_path(real_data_dir)) as connection:
        assert (
            connection.execute("SELECT 1 FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            is None
        )


def test_delete_tolerates_temp_file_removed_by_competing_cleanup(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, "Competing temp cleanup")
    owned = _audio_artifacts(data_dir, meeting_id)
    from asr_en_vi import meeting_deletion

    real_unlink = os.unlink
    competitor_unlinked = False

    def unlink_after_competitor(path, *args, **kwargs):
        nonlocal competitor_unlinked
        if path == owned["temp"].name and not competitor_unlinked:
            competitor_unlinked = True
            real_unlink(path, *args, **kwargs)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(meeting_deletion.os, "unlink", unlink_after_competitor)

    assert delete_meeting(data_dir, meeting_id)["status"] == "deleted"
    assert competitor_unlinked
    assert all(not path.exists() for path in owned.values())


async def test_restart_resumes_cleanup_after_partial_file_removal(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
    )
    initialize(settings.data_dir)
    meeting_id = seed_meeting(settings.data_dir, "Restart while deleting")
    owned = _audio_artifacts(settings.data_dir, meeting_id)
    from asr_en_vi import meeting_deletion

    real_unlink = os.unlink

    def fail_on_temp(path, *args, **kwargs):
        if str(path).endswith("0123456789abcdef.m4a"):
            raise OSError("simulated interruption during cleanup")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(meeting_deletion.os, "unlink", fail_on_temp)
        with pytest.raises(MeetingDeletionError) as error:
            delete_meeting(settings.data_dir, meeting_id)
        assert error.value.code == "meeting_deletion_cleanup_failed"

    assert not owned["raw"].exists()
    assert not owned["audio"].exists()
    assert owned["temp"].exists()
    assert get_meeting(settings.data_dir, meeting_id)["deletion_status"] == "failed"

    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        headers = await _authorize(client, settings)
        response = await client.get(f"/api/meetings/{meeting_id}", headers=headers)
        assert response.status_code == 404
    assert not owned["temp"].exists()


@pytest.mark.anyio
async def test_startup_recovers_interrupted_cleanup_through_symlinked_data_ancestor(
    tmp_path, monkeypatch
):
    physical_parent = tmp_path / "physical-parent"
    physical_parent.mkdir()
    real_data_dir = physical_parent / "data"
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(physical_parent, target_is_directory=True)
    configured_data_dir = linked_parent / "data"
    settings = Settings(
        data_dir=configured_data_dir,
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
    )
    initialize(real_data_dir)
    meeting_id = seed_meeting(real_data_dir, "Symlinked root restart recovery")
    owned = _audio_artifacts(real_data_dir, meeting_id)
    from asr_en_vi import meeting_deletion

    real_unlink = os.unlink

    def fail_on_temp(path, *args, **kwargs):
        if str(path).endswith("0123456789abcdef.m4a"):
            raise OSError("simulated interruption during cleanup")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(meeting_deletion.os, "unlink", fail_on_temp)
        with pytest.raises(MeetingDeletionError) as error:
            delete_meeting(configured_data_dir, meeting_id)
        assert error.value.code == "meeting_deletion_cleanup_failed"

    assert not owned["raw"].exists()
    assert not owned["audio"].exists()
    assert owned["temp"].exists()
    assert get_meeting(real_data_dir, meeting_id)["deletion_status"] == "failed"

    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        headers = await _authorize(client, settings)
        response = await client.get(f"/api/meetings/{meeting_id}", headers=headers)
        assert response.status_code == 404
    assert not owned["temp"].exists()


def test_recovery_defers_real_sqlite_write_lock_then_succeeds(tmp_path, caplog):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, "Locked deletion recovery")
    owned = _audio_artifacts(data_dir, meeting_id)
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "UPDATE meetings SET deletion_requested_at = CURRENT_TIMESTAMP WHERE id = ?",
            (meeting_id,),
        )

    blocker = sqlite3.connect(database_path(data_dir), timeout=5)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        with (
            caplog.at_level("WARNING", logger="asr_en_vi.meeting_deletion"),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            recovery = executor.submit(recover_pending_meeting_deletions, data_dir)
            assert recovery.result(timeout=15) == []
        assert blocker.execute(
            "SELECT deletion_requested_at FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()[0]
        assert "Deferring pending meeting deletion recovery" in caplog.text
        assert "locked" in caplog.text
    finally:
        blocker.rollback()
        blocker.close()

    assert recover_pending_meeting_deletions(data_dir) == [meeting_id]
    assert all(not path.exists() for path in owned.values())


@pytest.mark.parametrize("error_type", [sqlite3.IntegrityError, RuntimeError])
def test_recovery_does_not_suppress_unrelated_errors(tmp_path, monkeypatch, error_type):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, "Unrelated recovery error")
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "UPDATE meetings SET deletion_requested_at = CURRENT_TIMESTAMP WHERE id = ?",
            (meeting_id,),
        )
    from asr_en_vi import meeting_deletion

    def raise_unrelated_error(_data_dir, _meeting_id):
        raise error_type("injected unrelated failure")

    monkeypatch.setattr(meeting_deletion, "_mark_meeting_for_deletion", raise_unrelated_error)
    with pytest.raises(error_type, match="injected unrelated failure"):
        recover_pending_meeting_deletions(data_dir)


async def test_restart_finishes_after_files_are_removed_before_final_database_commit(
    tmp_path, monkeypatch
):
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
    )
    initialize(settings.data_dir)
    meeting_id = seed_meeting(settings.data_dir, "Restart before final commit")
    owned = _audio_artifacts(settings.data_dir, meeting_id)
    from asr_en_vi import meeting_deletion

    def fail_finalize(_data_dir, _meeting_id):
        raise OSError("simulated stop before the final database commit")

    with monkeypatch.context() as patch:
        patch.setattr(meeting_deletion, "_finalize_database_delete", fail_finalize)
        with pytest.raises(MeetingDeletionError) as error:
            delete_meeting(settings.data_dir, meeting_id)
        assert error.value.code == "meeting_deletion_cleanup_failed"

    assert all(not path.exists() for path in owned.values())
    assert get_meeting(settings.data_dir, meeting_id)["deletion_status"] == "failed"
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        headers = await _authorize(client, settings)
        response = await client.get(f"/api/meetings/{meeting_id}", headers=headers)
        assert response.status_code == 404


def test_speaker_catalog_is_immutable_except_for_marked_meeting(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, _generation_id, _segment_ids = seed_completed_transcript(data_dir)
    with sqlite3.connect(database_path(data_dir)) as connection:
        generation_id = connection.execute(
            "SELECT current_generation_id FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="generation_speakers_are_immutable"):
            connection.execute(
                "DELETE FROM generation_speakers WHERE generation_id = ?", (generation_id,)
            )
        connection.execute(
            "UPDATE meetings SET deletion_requested_at = CURRENT_TIMESTAMP WHERE id = ?",
            (meeting_id,),
        )
        connection.execute(
            "DELETE FROM generation_speakers WHERE generation_id = ?", (generation_id,)
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM generation_speakers WHERE generation_id = ?", (generation_id,)
            ).fetchone()[0]
            == 0
        )


def test_delete_races_transcription_acceptance_atomically(tmp_path):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, "Accept race")
    model_dir, diarization_dir = _task_model(tmp_path)
    gate = threading.Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        accepted = executor.submit(
            _race,
            gate,
            lambda: _accept_transcription(data_dir, model_dir, diarization_dir, meeting_id),
        )
        deleted = executor.submit(_race, gate, lambda: delete_meeting(data_dir, meeting_id))
        gate.wait(timeout=5)
    accept_result = accepted.result(timeout=10)
    delete_result = deleted.result(timeout=10)
    assert accept_result[0] != delete_result[0]
    if delete_result[0] == "ok":
        assert accept_result == ("error", "meeting_not_found") or accept_result == (
            "error",
            "meeting_deletion_pending",
        )
    else:
        assert delete_result[1] == "meeting_task_active"
        assert accept_result[0] == "ok"
        with sqlite3.connect(database_path(data_dir)) as connection:
            assert (
                connection.execute(
                    "SELECT status FROM tasks WHERE meeting_id = ? AND kind = 'transcription'",
                    (meeting_id,),
                ).fetchone()[0]
                == "accepted"
            )


def test_delete_races_notes_acceptance_atomically(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    gate = threading.Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        accepted = executor.submit(
            _race,
            gate,
            lambda: accept_notes_task(
                data_dir,
                provider=StubNotesProvider(),
                meeting_id=meeting_id,
                request_id="notes-delete-accept-race",
                expected_generation_id=generation_id,
                expected_source_version=1,
                expected_metadata_version=1,
                worker_ready=True,
            ),
        )
        deleted = executor.submit(_race, gate, lambda: delete_meeting(data_dir, meeting_id))
        gate.wait(timeout=5)
    accept_result = accepted.result(timeout=10)
    delete_result = deleted.result(timeout=10)
    assert accept_result[0] != delete_result[0]
    if delete_result[0] == "ok":
        assert accept_result == ("error", "meeting_not_found") or accept_result == (
            "error",
            "meeting_deletion_pending",
        )
    else:
        assert delete_result[1] == "meeting_task_active"
        assert accept_result[0] == "ok"
        with sqlite3.connect(database_path(data_dir)) as connection:
            assert (
                connection.execute(
                    "SELECT status FROM tasks WHERE meeting_id = ? AND kind = 'notes'",
                    (meeting_id,),
                ).fetchone()[0]
                == "accepted"
            )


def test_delete_races_cancel_and_completion_without_removing_active_work(tmp_path):
    data_dir = tmp_path / "data"
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, "Cancel race")
    model_dir, diarization_dir = _task_model(tmp_path)
    task = _accept_transcription(data_dir, model_dir, diarization_dir, meeting_id)
    gate = threading.Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        canceled = executor.submit(
            _race,
            gate,
            lambda: cancel_task(data_dir, task["id"]),
        )
        deleted = executor.submit(_race, gate, lambda: delete_meeting(data_dir, meeting_id))
        gate.wait(timeout=5)
    cancel_result = canceled.result(timeout=10)
    delete_result = deleted.result(timeout=10)
    if delete_result[0] == "error":
        assert delete_result[1] == "meeting_task_active"
        assert cancel_result[0] == "ok"
        assert delete_meeting(data_dir, meeting_id)["status"] == "deleted"

    next_meeting = seed_meeting(data_dir, "Completion race")
    next_task = _accept_transcription(data_dir, model_dir, diarization_dir, next_meeting)
    claim_next_task(data_dir, owner_id="completion-race-worker")
    update_task_progress(
        data_dir,
        next_task["id"],
        owner_id="completion-race-worker",
        stage="publishing",
        elapsed_seconds=0.1,
        transcript_end_seconds=0,
        segment_count=0,
    )
    gate = threading.Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        completed = executor.submit(
            _race,
            gate,
            lambda: publish_complete_generation(
                data_dir,
                next_task["id"],
                owner_id="completion-race-worker",
                segments=[],
                language_probability=None,
                elapsed_seconds=0.1,
            ),
        )
        deleted = executor.submit(_race, gate, lambda: delete_meeting(data_dir, next_meeting))
        gate.wait(timeout=5)
    complete_result = completed.result(timeout=10)
    delete_result = deleted.result(timeout=10)
    assert complete_result[0] == "ok" or delete_result[1] == "meeting_task_active"
    if delete_result[0] == "error":
        assert delete_result[1] == "meeting_task_active"
        assert complete_result[0] == "ok"
        assert delete_meeting(data_dir, next_meeting)["status"] == "deleted"
