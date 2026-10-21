from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from notes_helpers import StubNotesProvider, seed_completed_transcript

from asr_en_vi.chatgpt import ChatGPTError, ChatGPTProvider
from asr_en_vi.notes import (
    accept_notes_task,
    assert_provider_mutation_allowed,
    export_note,
    get_note,
    get_notes_source,
    has_active_notes_task,
    load_notes_task_input,
    notes_state,
    publish_notes_revision,
    update_note,
)
from asr_en_vi.notes_document import PROMPT_VERSION
from asr_en_vi.recordings import RecordingError, update_meeting
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import (
    TaskError,
    cancel_task,
    claim_next_task,
    recover_abandoned_tasks,
    transcription_state,
    update_current_generation_segment_text,
)
from asr_en_vi.worker import acquire_worker_lock


def _accept(data_dir: Path, meeting_id: str, generation_id: str, *, request_id="notes-req-0001"):
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


def _markdown(text="Approved next step."):
    return f"# Meeting Notes\n\n{text}\n"


def test_acceptance_freezes_source_pins_account_and_locks_only_its_meeting(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, segment_ids = seed_completed_transcript(data_dir)
    other_meeting, other_generation, other_segments = seed_completed_transcript(
        data_dir, title="Other meeting"
    )

    accepted = _accept(data_dir, meeting_id, generation_id)
    retry = accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id="notes-req-0001",
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=False,
    )

    assert accepted["id"] == retry["id"]
    assert accepted["kind"] == "notes"
    assert accepted["result_scope"] == "notes_only"
    # Notes have their own status panel; they must not replace local ASR progress.
    assert transcription_state(data_dir, meeting_id)["task"]["kind"] == "transcription"
    assert has_active_notes_task(data_dir, meeting_id=meeting_id)
    assert not has_active_notes_task(data_dir, meeting_id=other_meeting)
    with sqlite3.connect(database_path(data_dir)) as connection:
        row = connection.execute(
            "SELECT notes_provider, notes_connection_version, notes_model, "
            "notes_reasoning_effort, notes_prompt_version, notes_schema_version "
            "FROM tasks WHERE id = ?",
            (accepted["id"],),
        ).fetchone()
        source_id = connection.execute(
            "SELECT notes_source_id FROM tasks WHERE id = ?", (accepted["id"],)
        ).fetchone()[0]
        slot_id = connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()[0]
    assert row == ("chatgpt", 7, "gpt-6.1-sol", "high", PROMPT_VERSION, 1)
    assert slot_id == accepted["id"]
    snapshot = get_notes_source(data_dir, source_id)
    assert snapshot["meeting_id"] == meeting_id
    assert snapshot["generation_id"] == generation_id
    assert snapshot["meeting_date"] == "2026-10-19"
    assert [item["id"] for item in snapshot["segments"]] == segment_ids
    assert snapshot["segments"][0]["speaker_name"] == "Morgan"
    encoded_snapshot = json.dumps(snapshot)
    assert "Planning meeting" not in encoded_snapshot
    assert "storage_key" not in encoded_snapshot and "access_token" not in encoded_snapshot
    assert notes_state(data_dir, meeting_id)["source_locked"] is True

    renamed = update_meeting(
        data_dir, meeting_id, expected_version=1, fields={"title": "Renamed meeting"}
    )
    assert renamed["title"] == "Renamed meeting"
    with pytest.raises(RecordingError) as date_lock:
        update_meeting(
            data_dir,
            meeting_id,
            expected_version=2,
            fields={"meeting_date": "2026-10-20"},
        )
    assert date_lock.value.code == "notes_source_locked"
    with pytest.raises(TaskError) as segment_lock:
        update_current_generation_segment_text(
            data_dir,
            meeting_id,
            segment_ids[0],
            expected_generation_id=generation_id,
            expected_source_version=1,
            text="Changed while notes are running.",
        )
    assert segment_lock.value.code == "notes_source_locked"

    changed_other = update_current_generation_segment_text(
        data_dir,
        other_meeting,
        other_segments[0],
        expected_generation_id=other_generation,
        expected_source_version=1,
        text="A different meeting can still change.",
    )
    assert changed_other["source_version"] == 2
    stopping = cancel_task(data_dir, accepted["id"])
    assert stopping["status"] == "canceled"
    assert not has_active_notes_task(data_dir, meeting_id=meeting_id)
    assert notes_state(data_dir, meeting_id)["source_locked"] is False
    changed = update_current_generation_segment_text(
        data_dir,
        meeting_id,
        segment_ids[0],
        expected_generation_id=generation_id,
        expected_source_version=1,
        text="The lock released after the task stopped.",
    )
    assert changed["source_version"] == 2


def test_notes_output_language_is_pinned_and_part_of_idempotency(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _segment_ids = seed_completed_transcript(data_dir)
    english = _accept(data_dir, meeting_id, generation_id, request_id="language-req-0001")
    explicit_english = accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id="language-req-0001",
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=False,
        output_language="en",
    )
    assert english["output_language"] == "en"
    assert explicit_english["id"] == english["id"]
    with pytest.raises(TaskError) as conflict:
        accept_notes_task(
            data_dir,
            provider=StubNotesProvider(),
            meeting_id=meeting_id,
            request_id="language-req-0001",
            expected_generation_id=generation_id,
            expected_source_version=1,
            expected_metadata_version=1,
            worker_ready=False,
            output_language="vi",
        )
    assert conflict.value.code == "idempotency_conflict"

    cancel_task(data_dir, english["id"])
    vietnamese = accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id="language-req-0002",
        expected_generation_id=generation_id,
        expected_source_version=1,
        expected_metadata_version=1,
        worker_ready=True,
        output_language="vi",
    )
    assert vietnamese["output_language"] == "vi"
    task = claim_next_task(data_dir, owner_id="language-worker")
    assert task is not None and task["id"] == vietnamese["id"]
    loaded_task, _snapshot = load_notes_task_input(
        data_dir, vietnamese["id"], owner_id="language-worker"
    )
    assert loaded_task["notes_output_language"] == "vi"
    markdown = "## Tổng quan\n\n- Bản nháp đã lưu.\n"
    revision = publish_notes_revision(
        data_dir,
        vietnamese["id"],
        owner_id="language-worker",
        markdown=markdown,
        elapsed_seconds=1.0,
    )
    assert revision is not None
    assert revision["output_language"] == "vi"
    assert revision["markdown"] == markdown
    assert get_note(data_dir, revision["id"])["output_language"] == "vi"
    assert notes_state(data_dir, meeting_id)["revisions"][0]["output_language"] == "vi"


@pytest.mark.parametrize("language", [None, True, False, "EN", "fr", "", 0])
def test_notes_output_language_rejects_values_outside_exact_language_codes(tmp_path, language):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _segment_ids = seed_completed_transcript(data_dir)

    with pytest.raises(TaskError) as invalid:
        accept_notes_task(
            data_dir,
            provider=StubNotesProvider(),
            meeting_id=meeting_id,
            request_id="invalid-language-001",
            expected_generation_id=generation_id,
            expected_source_version=1,
            expected_metadata_version=1,
            worker_ready=True,
            output_language=language,
        )
    assert invalid.value.code == "invalid_output_language"


def test_existing_notes_omit_timestamp_references_in_reads_and_export(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, segment_ids = seed_completed_transcript(data_dir)
    accepted = _accept(data_dir, meeting_id, generation_id)
    claim_next_task(data_dir, owner_id="notes-worker")
    with sqlite3.connect(database_path(data_dir)) as connection:
        source_id = connection.execute(
            "SELECT notes_source_id FROM tasks WHERE id = ?", (accepted["id"],)
        ).fetchone()[0]
    reference = (
        f"[00:00:01](/meetings/{meeting_id}?notes_source={source_id}&segment={segment_ids[0]})"
    )
    summary = "## Overview\n\n- Review at 10:30.\n- Keep [00:00:01](https://example.test).\n"
    legacy = summary.replace("Review at 10:30.", f"Review at 10:30. {reference} {reference}")
    revision = publish_notes_revision(
        data_dir,
        accepted["id"],
        owner_id="notes-worker",
        markdown=legacy,
        elapsed_seconds=1.0,
    )
    assert revision is not None
    assert get_note(data_dir, revision["id"])["markdown"] == summary
    assert notes_state(data_dir, meeting_id)["revisions"][0]["markdown"] == summary
    assert export_note(data_dir, revision["id"]) == summary
    with sqlite3.connect(database_path(data_dir)) as connection:
        saved = connection.execute(
            "SELECT markdown, edit_version FROM notes_revisions WHERE id = ?", (revision["id"],)
        ).fetchone()
    assert saved == (legacy, 1)


def test_revision_edit_conflicts_export_and_source_staleness(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, segment_ids = seed_completed_transcript(data_dir)
    accepted = _accept(data_dir, meeting_id, generation_id)
    task = claim_next_task(data_dir, owner_id="notes-worker")
    assert task is not None and task["id"] == accepted["id"]
    original_markdown = _markdown()
    revision = publish_notes_revision(
        data_dir,
        accepted["id"],
        owner_id="notes-worker",
        markdown=original_markdown,
        elapsed_seconds=1.5,
    )
    assert revision is not None
    assert revision["source_state"] == "current"
    assert revision["provider"] == "chatgpt"
    assert revision["model"] == "gpt-6.1-sol"
    assert get_notes_source(data_dir, revision["source_snapshot_id"])["segments"][0]["text"] == (
        "We need a launch plan."
    )

    edited_markdown = _markdown("Morgan owns the draft.")
    saved = update_note(
        data_dir,
        revision["id"],
        expected_edit_version=1,
        markdown=edited_markdown,
    )
    assert saved["edit_version"] == 2
    assert saved["markdown"] == edited_markdown
    with pytest.raises(TaskError) as conflict:
        update_note(
            data_dir,
            revision["id"],
            expected_edit_version=1,
            markdown="A stale browser draft.",
        )
    assert conflict.value.code == "notes_edit_version_changed"
    assert export_note(data_dir, revision["id"]) == edited_markdown
    assert get_note(data_dir, revision["id"])["markdown"] == edited_markdown

    renamed = update_meeting(
        data_dir, meeting_id, expected_version=1, fields={"title": "New display title"}
    )
    assert renamed["notes_source_version"] == 1
    assert get_note(data_dir, revision["id"])["source_state"] == "current"
    update_meeting(
        data_dir,
        meeting_id,
        expected_version=2,
        fields={"meeting_date": "2026-10-20"},
    )
    assert get_note(data_dir, revision["id"])["source_state"] == "stale"
    update_current_generation_segment_text(
        data_dir,
        meeting_id,
        segment_ids[0],
        expected_generation_id=generation_id,
        expected_source_version=1,
        text="The transcript changed after publication.",
    )
    assert get_note(data_dir, revision["id"])["source_state"] == "stale"


def test_revision_becomes_historical_when_meeting_selects_another_generation(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    accepted = _accept(data_dir, meeting_id, generation_id)
    claim_next_task(data_dir, owner_id="notes-worker")
    revision = publish_notes_revision(
        data_dir,
        accepted["id"],
        owner_id="notes-worker",
        markdown=_markdown(),
        elapsed_seconds=1.0,
    )
    assert revision is not None

    next_task_id = "b" * 32
    next_generation_id = "c" * 32
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "INSERT INTO tasks(id, request_id, request_hash, meeting_id, kind, model_path, "
            "model_name, device, compute_type, language_hint, status, stage, result_scope, "
            "audio_duration_seconds) VALUES (?, ?, ?, ?, 'transcription', '/models/whisper', "
            "'whisper', 'cpu', 'int8', 'en', 'succeeded', 'complete', 'transcript_only', 30.0)",
            (next_task_id, "next-generation-task", "next-generation-hash", meeting_id),
        )
        connection.execute(
            "INSERT INTO transcript_generations(id, meeting_id, task_id, generation_number, "
            "status, language_hint, model_name, uncertainty_policy, segment_count) "
            "VALUES (?, ?, ?, 2, 'complete', 'en', 'whisper', 'test-policy', 0)",
            (next_generation_id, meeting_id, next_task_id),
        )
        connection.execute(
            "UPDATE meetings SET current_generation_id = ? WHERE id = ?",
            (next_generation_id, meeting_id),
        )

    assert get_note(data_dir, revision["id"])["source_state"] == "historical"


def test_cancel_and_recovery_never_publish_late_result_or_remove_old_revisions(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    first = _accept(data_dir, meeting_id, generation_id)
    claim_next_task(data_dir, owner_id="notes-worker-1")
    previous_revision = publish_notes_revision(
        data_dir,
        first["id"],
        owner_id="notes-worker-1",
        markdown=_markdown("Keep this saved revision."),
        elapsed_seconds=1.0,
    )
    assert previous_revision is not None

    second = _accept(data_dir, meeting_id, generation_id, request_id="notes-req-0002")
    assert cancel_task(data_dir, second["id"])["status"] == "canceled"
    assert (
        publish_notes_revision(
            data_dir,
            second["id"],
            owner_id="notes-worker-2",
            markdown=_markdown("Late output must be discarded."),
            elapsed_seconds=2.0,
        )
        is None
    )
    assert [item["id"] for item in notes_state(data_dir, meeting_id)["revisions"]] == [
        previous_revision["id"]
    ]

    third = _accept(data_dir, meeting_id, generation_id, request_id="notes-req-0003")
    claim_next_task(data_dir, owner_id="notes-worker-3")
    lock_fd = acquire_worker_lock(data_dir)
    assert lock_fd is not None
    try:
        assert recover_abandoned_tasks(data_dir) == [third["id"]]
    finally:
        import os

        os.close(lock_fd)
    state = notes_state(data_dir, meeting_id)
    assert state["task"]["status"] == "interrupted"
    assert state["source_locked"] is False
    assert [item["id"] for item in state["revisions"]] == [previous_revision["id"]]
    assert export_note(data_dir, previous_revision["id"]) == _markdown("Keep this saved revision.")


def test_provider_mutations_are_denied_until_active_notes_task_is_terminal(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, _ = seed_completed_transcript(data_dir)
    task = _accept(data_dir, meeting_id, generation_id)
    provider = ChatGPTProvider(
        tmp_path / "provider",
        callback_url="",
        active_task_guard=lambda: assert_provider_mutation_allowed(data_dir, "chatgpt"),
    )
    provider.ensure()

    with pytest.raises(ChatGPTError) as guarded:
        provider.start_login()
    assert guarded.value.code == "provider_in_use"
    with pytest.raises(ChatGPTError) as checked:
        assert_provider_mutation_allowed(data_dir, "chatgpt")
    assert checked.value.code == "provider_in_use"
    # Only the provider pinned by the active task is blocked.
    assert_provider_mutation_allowed(data_dir, "antigravity")

    assert cancel_task(data_dir, task["id"])["status"] == "canceled"
    assert_provider_mutation_allowed(data_dir, "chatgpt")
    with provider.store.locked() as state:
        assert state["connection_status"] == "disconnected"
        assert state["connection_version"] == 0


def test_oversized_source_is_rejected_without_creating_task_or_snapshot(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, segment_ids = seed_completed_transcript(data_dir)
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute(
            "UPDATE transcript_segments SET text = ? WHERE id = ?",
            ("x" * 60_000, segment_ids[0]),
        )

    with pytest.raises(TaskError) as oversized:
        _accept(data_dir, meeting_id, generation_id)

    assert oversized.value.status_code == 413
    assert oversized.value.code == "notes_source_too_large"
    assert "single transcript segment" in oversized.value.message
    with sqlite3.connect(database_path(data_dir)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tasks WHERE kind = 'notes'").fetchone() == (
            0,
        )
        assert connection.execute("SELECT COUNT(*) FROM notes_sources").fetchone() == (0,)
        assert connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone() == (None,)


def test_long_transcript_is_accepted_with_all_source_segments_frozen(tmp_path):
    data_dir = tmp_path / "data"
    meeting_id, generation_id, initial_segment_ids = seed_completed_transcript(data_dir)
    additional_segments = [
        (
            uuid.uuid4().hex,
            generation_id,
            sequence,
            5.0 + (sequence - 2) * 0.025,
            5.01 + (sequence - 2) * 0.025,
            f"Long-source segment {sequence}: review the proposal and unresolved question.",
            "SPEAKER_00",
            "SPEAKER_00",
            0,
        )
        for sequence in range(2, 1_000)
    ]
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.executemany(
            "INSERT INTO transcript_segments(id, generation_id, sequence, start_seconds, "
            "end_seconds, text, original_speaker_id, speaker_id, uncertain) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            additional_segments,
        )

    accepted = _accept(data_dir, meeting_id, generation_id)
    with sqlite3.connect(database_path(data_dir)) as connection:
        source_id = connection.execute(
            "SELECT notes_source_id FROM tasks WHERE id = ?", (accepted["id"],)
        ).fetchone()[0]
    snapshot = get_notes_source(data_dir, source_id)

    assert accepted["status"] == "accepted"
    assert len(snapshot["segments"]) == 1_000
    assert [segment["id"] for segment in snapshot["segments"][:2]] == initial_segment_ids
    assert [segment["id"] for segment in snapshot["segments"][2:]] == [
        row[0] for row in additional_segments
    ]
