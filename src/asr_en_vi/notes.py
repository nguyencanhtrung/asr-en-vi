"""Durable notes snapshots, task acceptance, revision editing and source state."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from asr_en_vi.chatgpt import ChatGPTError, ChatGPTProvider
from asr_en_vi.notes_document import (
    MAX_OUTPUT_BYTES,
    MAX_PROMPT_BYTES,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    NotesDocumentError,
    build_prompt,
)
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import TaskError, _request_id, _task_summary

_MAX_MARKDOWN_BYTES = MAX_OUTPUT_BYTES * 4
_ACTIVE_STATES = ("accepted", "running", "stopping")
_SEGMENT_ID_RE = re.compile(r"[0-9a-f]{32}\Z")


@contextmanager
def _connect(data_dir: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path(data_dir), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def _connect_read_only(data_dir: Path) -> Iterator[sqlite3.Connection]:
    path = database_path(data_dir).resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", timeout=5, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
    finally:
        connection.close()


def _positive_version(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TaskError(400, f"invalid_{field}", f"Provide a valid {field.replace('_', ' ')}.")
    return value


def _request_hash(
    *,
    meeting_id: str,
    expected_generation_id: str,
    expected_source_version: int,
    expected_metadata_version: int,
) -> str:
    value = {
        "expected_generation_id": expected_generation_id,
        "expected_metadata_version": expected_metadata_version,
        "expected_source_version": expected_source_version,
        "meeting_id": meeting_id,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _existing_task(data_dir: Path, request_id: str, request_hash: str) -> dict[str, object] | None:
    with _connect_read_only(data_dir) as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE request_id = ?", (request_id,)
        ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise TaskError(
            409,
            "idempotency_conflict",
            "This request_id was already used with different task details.",
        )
    return _task_summary(row)


def has_active_notes_task(data_dir: Path, *, meeting_id: str | None = None) -> bool:
    sql = (
        "SELECT 1 FROM tasks WHERE kind = 'notes' AND status IN ('accepted', 'running', 'stopping')"
    )
    parameters: tuple[object, ...] = ()
    if meeting_id is not None:
        sql += " AND meeting_id = ?"
        parameters = (meeting_id,)
    sql += " LIMIT 1"
    with _connect_read_only(data_dir) as connection:
        return connection.execute(sql, parameters).fetchone() is not None


def assert_provider_mutation_allowed(data_dir: Path) -> None:
    if has_active_notes_task(data_dir):
        raise ChatGPTError(
            409,
            "provider_in_use",
            "Wait for notes generation to finish before changing the ChatGPT connection or model.",
        )


def _source_snapshot(
    connection: sqlite3.Connection,
    *,
    meeting: sqlite3.Row,
    generation: sqlite3.Row,
    snapshot_id: str,
) -> dict[str, Any]:
    segment_rows = connection.execute(
        "SELECT id, sequence, start_seconds, end_seconds, text, original_speaker_id, speaker_id "
        "FROM transcript_segments WHERE generation_id = ? ORDER BY sequence",
        (generation["id"],),
    ).fetchall()
    speaker_rows = connection.execute(
        "SELECT speaker_id, display_name, first_seen_seconds, last_seen_seconds "
        "FROM generation_speakers WHERE generation_id = ? "
        "ORDER BY first_seen_seconds, speaker_id",
        (generation["id"],),
    ).fetchall()
    speaker_names = {row["speaker_id"]: row["display_name"] for row in speaker_rows}
    return {
        "id": snapshot_id,
        "meeting_id": meeting["id"],
        "generation_id": generation["id"],
        "source_version": generation["source_version"],
        "notes_source_version": meeting["notes_source_version"],
        "metadata_version": meeting["metadata_version"],
        "meeting_date": meeting["meeting_date"],
        "speakers": [
            {
                "speaker_id": row["speaker_id"],
                "display_name": row["display_name"],
                "first_seen_seconds": row["first_seen_seconds"],
                "last_seen_seconds": row["last_seen_seconds"],
            }
            for row in speaker_rows
        ],
        "segments": [
            {
                "id": row["id"],
                "sequence": row["sequence"],
                "start_seconds": row["start_seconds"],
                "end_seconds": row["end_seconds"],
                "text": row["text"],
                "original_speaker_id": row["original_speaker_id"],
                "speaker_id": row["speaker_id"],
                "speaker_name": speaker_names.get(row["speaker_id"]),
            }
            for row in segment_rows
        ],
    }


def accept_notes_task(
    data_dir: Path,
    *,
    provider: ChatGPTProvider,
    meeting_id: object,
    request_id: object,
    expected_generation_id: object,
    expected_source_version: object,
    expected_metadata_version: object,
    worker_ready: bool,
) -> dict[str, object]:
    """Pin provider state, freeze the source and claim the shared slot atomically."""
    if not isinstance(meeting_id, str) or not meeting_id:
        raise TaskError(400, "invalid_meeting_id", "Provide a meeting_id.")
    normalized_request_id = _request_id(request_id)
    if not isinstance(expected_generation_id, str) or not expected_generation_id:
        raise TaskError(400, "invalid_generation_id", "Provide the expected generation id.")
    source_version = _positive_version(expected_source_version, field="source_version")
    metadata_version = _positive_version(expected_metadata_version, field="metadata_version")
    request_hash = _request_hash(
        meeting_id=meeting_id,
        expected_generation_id=expected_generation_id,
        expected_source_version=source_version,
        expected_metadata_version=metadata_version,
    )
    existing = _existing_task(data_dir, normalized_request_id, request_hash)
    if existing is not None:
        return existing
    if not worker_ready:
        raise TaskError(503, "worker_unavailable", "The processing worker is unavailable.")

    # Acceptance and account changes share this cross-process lock. Lock order is
    # provider operation lock, then SQLite. No inference or filesystem work occurs
    # after the SQLite transaction begins.
    with provider.store.operation():
        pin = provider.notes_task_pin()
        with _connect(data_dir) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT * FROM tasks WHERE request_id = ?", (normalized_request_id,)
            ).fetchone()
            if existing_row is not None:
                if existing_row["request_hash"] != request_hash:
                    raise TaskError(
                        409,
                        "idempotency_conflict",
                        "This request_id was already used with different task details.",
                    )
                return _task_summary(existing_row)

            meeting = connection.execute(
                "SELECT id, meeting_date, language_hint, metadata_version, "
                "notes_source_version, current_generation_id FROM meetings WHERE id = ?",
                (meeting_id,),
            ).fetchone()
            if meeting is None:
                raise TaskError(404, "meeting_not_found", "Meeting not found.")
            if meeting["metadata_version"] != metadata_version:
                raise TaskError(
                    409,
                    "metadata_version_changed",
                    "Meeting details changed. Reload before starting notes generation.",
                )
            if meeting["current_generation_id"] != expected_generation_id:
                raise TaskError(
                    409,
                    "current_generation_changed",
                    "The current transcript changed. Reload before starting notes generation.",
                )
            generation = connection.execute(
                "SELECT id, status, language_hint, model_name, source_version "
                "FROM transcript_generations WHERE id = ? AND meeting_id = ?",
                (expected_generation_id, meeting_id),
            ).fetchone()
            if generation is None or generation["status"] != "complete":
                raise TaskError(
                    409,
                    "transcript_required",
                    "Generate a complete transcript before creating notes.",
                )
            if generation["source_version"] != source_version:
                raise TaskError(
                    409,
                    "source_version_changed",
                    "The transcript changed. Reload before starting notes generation.",
                )
            recording = connection.execute(
                "SELECT duration_seconds FROM recordings WHERE meeting_id = ?", (meeting_id,)
            ).fetchone()
            if recording is None:
                raise TaskError(404, "meeting_not_found", "Meeting recording not found.")
            slot = connection.execute(
                "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
            ).fetchone()
            if slot is None:
                raise TaskError(
                    503, "processing_unavailable", "The processing slot is unavailable."
                )
            if slot["active_task_id"] is not None:
                raise TaskError(
                    409,
                    "system_busy",
                    "Another task owns the processing slot. Wait for it to finish.",
                )

            snapshot_id = uuid.uuid4().hex
            snapshot = _source_snapshot(
                connection, meeting=meeting, generation=generation, snapshot_id=snapshot_id
            )
            if not snapshot["segments"]:
                raise TaskError(
                    409,
                    "transcript_empty",
                    "The current transcript has no source segments for notes generation.",
                )
            try:
                prompt = build_prompt(snapshot)
            except NotesDocumentError:
                raise TaskError(
                    413,
                    "notes_source_too_large",
                    f"This transcript exceeds the {MAX_PROMPT_BYTES}-byte notes context budget.",
                ) from None
            del prompt
            snapshot_json = json.dumps(
                snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            task_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO notes_sources(id, meeting_id, generation_id, source_version, "
                "notes_source_version, meeting_date, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    meeting_id,
                    generation["id"],
                    generation["source_version"],
                    meeting["notes_source_version"],
                    meeting["meeting_date"],
                    snapshot_json,
                ),
            )
            connection.execute(
                "INSERT INTO tasks(id, request_id, request_hash, meeting_id, kind, model_path, "
                "model_name, device, compute_type, language_hint, status, stage, result_scope, "
                "audio_duration_seconds, segment_count, notes_provider, notes_connection_version, "
                "notes_model, notes_reasoning_effort, notes_prompt_version, notes_schema_version, "
                "notes_source_id) VALUES (?, ?, ?, ?, 'notes', '', ?, 'auto', 'provider', ?, "
                "'accepted', 'accepted', 'notes_only', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    normalized_request_id,
                    request_hash,
                    meeting_id,
                    pin["model"],
                    generation["language_hint"],
                    recording["duration_seconds"],
                    len(snapshot["segments"]),
                    pin["provider"],
                    pin["connection_version"],
                    pin["model"],
                    pin["reasoning_effort"],
                    PROMPT_VERSION,
                    SCHEMA_VERSION,
                    snapshot_id,
                ),
            )
            cursor = connection.execute(
                "UPDATE processing_slot SET active_task_id = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE slot_id = 1 AND active_task_id IS NULL",
                (task_id,),
            )
            if cursor.rowcount != 1:
                raise TaskError(409, "system_busy", "Another task owns the processing slot.")
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            assert row is not None
            return _task_summary(row)


def _revision_payload(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    current_generation_id: str | None,
    current_source_version: int | None,
    current_notes_source_version: int,
    current_meeting_date: str | None,
) -> dict[str, object]:
    if row["generation_id"] != current_generation_id:
        source_state = "historical"
    elif (
        row["source_version"] != current_source_version
        or row["notes_source_version"] != current_notes_source_version
        or row["source_meeting_date"] != current_meeting_date
    ):
        source_state = "stale"
    else:
        source_state = "current"
    return {
        "id": row["id"],
        "meeting_id": row["meeting_id"],
        "source_snapshot_id": row["source_snapshot_id"],
        "markdown": row["markdown"],
        "edit_version": row["edit_version"],
        "source_state": source_state,
        "provider": row["provider"],
        "model": row["model"],
        "reasoning_effort": row["reasoning_effort"],
        "connection_version": row["connection_version"],
        "prompt_version": row["prompt_version"],
        "schema_version": row["schema_version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_REVISION_SELECT = (
    "SELECT revisions.*, sources.generation_id, sources.source_version, "
    "sources.notes_source_version, sources.meeting_date AS source_meeting_date "
    "FROM notes_revisions AS revisions "
    "JOIN notes_sources AS sources ON sources.id = revisions.source_snapshot_id "
)


def _source_state_context(
    connection: sqlite3.Connection, meeting_id: str
) -> tuple[str | None, int | None, int, str | None]:
    meeting = connection.execute(
        "SELECT current_generation_id, notes_source_version, meeting_date "
        "FROM meetings WHERE id = ?",
        (meeting_id,),
    ).fetchone()
    if meeting is None:
        raise TaskError(404, "meeting_not_found", "Meeting not found.")
    current_source_version = None
    if meeting["current_generation_id"] is not None:
        current = connection.execute(
            "SELECT source_version FROM transcript_generations WHERE id = ?",
            (meeting["current_generation_id"],),
        ).fetchone()
        if current is not None:
            current_source_version = current["source_version"]
    return (
        meeting["current_generation_id"],
        current_source_version,
        meeting["notes_source_version"],
        meeting["meeting_date"],
    )


def _active_notes_for_meeting(connection: sqlite3.Connection, meeting_id: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM tasks WHERE meeting_id = ? AND kind = 'notes' "
            "AND status IN ('accepted', 'running', 'stopping') LIMIT 1",
            (meeting_id,),
        ).fetchone()
        is not None
    )


def notes_state(data_dir: Path, meeting_id: str) -> dict[str, object]:
    with _connect_read_only(data_dir) as connection:
        current_generation, current_version, date_version, meeting_date = _source_state_context(
            connection, meeting_id
        )
        rows = connection.execute(
            _REVISION_SELECT + "WHERE revisions.meeting_id = ? ORDER BY revisions.rowid DESC",
            (meeting_id,),
        ).fetchall()
        task = connection.execute(
            "SELECT * FROM tasks WHERE meeting_id = ? AND kind = 'notes' "
            "ORDER BY rowid DESC LIMIT 1",
            (meeting_id,),
        ).fetchone()
        source_locked = _active_notes_for_meeting(connection, meeting_id)
        revisions = [
            _revision_payload(
                connection,
                row,
                current_generation_id=current_generation,
                current_source_version=current_version,
                current_notes_source_version=date_version,
                current_meeting_date=meeting_date,
            )
            for row in rows
        ]
    return {
        "revisions": revisions,
        "task": _task_summary(task) if task is not None else None,
        "source_locked": source_locked,
    }


def get_note(data_dir: Path, note_id: str) -> dict[str, object]:
    with _connect_read_only(data_dir) as connection:
        row = connection.execute(_REVISION_SELECT + "WHERE revisions.id = ?", (note_id,)).fetchone()
        if row is None:
            raise TaskError(404, "notes_not_found", "Notes revision not found.")
        current_generation, current_version, date_version, meeting_date = _source_state_context(
            connection, row["meeting_id"]
        )
        return _revision_payload(
            connection,
            row,
            current_generation_id=current_generation,
            current_source_version=current_version,
            current_notes_source_version=date_version,
            current_meeting_date=meeting_date,
        )


def update_note(
    data_dir: Path,
    note_id: str,
    *,
    expected_edit_version: object,
    markdown: object,
) -> dict[str, object]:
    if (
        isinstance(expected_edit_version, bool)
        or not isinstance(expected_edit_version, int)
        or expected_edit_version < 1
    ):
        raise TaskError(400, "invalid_edit_version", "Provide a valid expected_edit_version.")
    if not isinstance(markdown, str) or "\x00" in markdown:
        raise TaskError(400, "invalid_markdown", "Provide valid Markdown text.")
    try:
        markdown_size = len(markdown.encode("utf-8"))
    except UnicodeEncodeError:
        raise TaskError(400, "invalid_markdown", "Provide valid Markdown text.") from None
    if markdown_size > _MAX_MARKDOWN_BYTES:
        raise TaskError(413, "markdown_too_large", "Notes Markdown exceeds the size limit.")

    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT meeting_id, edit_version FROM notes_revisions WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise TaskError(404, "notes_not_found", "Notes revision not found.")
        if row["edit_version"] != expected_edit_version:
            raise TaskError(
                409,
                "notes_edit_version_changed",
                "This notes revision changed. Keep your draft, reload, "
                "and compare it before saving.",
            )
        connection.execute(
            "UPDATE notes_revisions SET markdown = ?, edit_version = edit_version + 1, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND edit_version = ?",
            (markdown, note_id, expected_edit_version),
        )
    return get_note(data_dir, note_id)


def export_note(data_dir: Path, note_id: str) -> str:
    with _connect_read_only(data_dir) as connection:
        row = connection.execute(
            "SELECT markdown FROM notes_revisions WHERE id = ?", (note_id,)
        ).fetchone()
    if row is None:
        raise TaskError(404, "notes_not_found", "Notes revision not found.")
    return row["markdown"]


def get_notes_source(data_dir: Path, source_id: str) -> dict[str, Any]:
    if not isinstance(source_id, str) or not _SEGMENT_ID_RE.fullmatch(source_id):
        raise TaskError(404, "notes_source_not_found", "Notes source snapshot not found.")
    with _connect_read_only(data_dir) as connection:
        row = connection.execute(
            "SELECT snapshot_json FROM notes_sources WHERE id = ?", (source_id,)
        ).fetchone()
    if row is None:
        raise TaskError(404, "notes_source_not_found", "Notes source snapshot not found.")
    try:
        snapshot = json.loads(row["snapshot_json"])
    except (TypeError, json.JSONDecodeError):
        raise TaskError(
            500, "notes_source_unavailable", "The saved notes source is unavailable."
        ) from None
    if not isinstance(snapshot, dict):
        raise TaskError(500, "notes_source_unavailable", "The saved notes source is unavailable.")
    return snapshot


def load_notes_task_input(
    data_dir: Path, task_id: str, *, owner_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load only the task's immutable source and pinned provider fields for its worker."""
    with _connect_read_only(data_dir) as connection:
        task = connection.execute(
            "SELECT id, owner_id, status, kind, notes_provider, notes_connection_version, "
            "notes_model, notes_reasoning_effort, notes_prompt_version, notes_schema_version, "
            "notes_source_id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None or task["kind"] != "notes":
            raise TaskError(404, "task_not_found", "Notes task not found.")
        if task["owner_id"] != owner_id or task["status"] != "running":
            raise TaskError(409, "task_not_running", "The notes task is no longer running.")
        source = connection.execute(
            "SELECT snapshot_json FROM notes_sources WHERE id = ?", (task["notes_source_id"],)
        ).fetchone()
    if source is None:
        raise TaskError(500, "notes_source_unavailable", "The saved notes source is unavailable.")
    try:
        snapshot = json.loads(source["snapshot_json"])
    except (TypeError, json.JSONDecodeError):
        raise TaskError(
            500, "notes_source_unavailable", "The saved notes source is unavailable."
        ) from None
    if not isinstance(snapshot, dict):
        raise TaskError(500, "notes_source_unavailable", "The saved notes source is unavailable.")
    return dict(task), snapshot


def publish_notes_revision(
    data_dir: Path,
    task_id: str,
    *,
    owner_id: str,
    markdown: object,
    elapsed_seconds: float,
) -> dict[str, object] | None:
    if not isinstance(markdown, str) or "\x00" in markdown:
        raise TaskError(400, "invalid_markdown", "The generated notes document is invalid.")
    if len(markdown.encode("utf-8")) > _MAX_MARKDOWN_BYTES:
        raise TaskError(413, "markdown_too_large", "Generated notes exceed the size limit.")
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ? AND kind = 'notes'",
            (task_id, owner_id),
        ).fetchone()
        if task is None or task["status"] != "running":
            return None
        slot = connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()
        if slot is None or slot["active_task_id"] != task_id:
            return None
        revision_id = uuid.uuid4().hex
        connection.execute(
            "INSERT INTO notes_revisions(id, meeting_id, source_snapshot_id, task_id, markdown, "
            "provider, model, reasoning_effort, connection_version, prompt_version, "
            "schema_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                task["meeting_id"],
                task["notes_source_id"],
                task_id,
                markdown,
                task["notes_provider"],
                task["notes_model"],
                task["notes_reasoning_effort"],
                task["notes_connection_version"],
                task["notes_prompt_version"],
                task["notes_schema_version"],
            ),
        )
        connection.execute(
            "UPDATE tasks SET status = 'succeeded', stage = 'succeeded', "
            "elapsed_seconds = ?, completed_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_id = ? AND status = 'running'",
            (max(0.0, elapsed_seconds), task_id, owner_id),
        )
        connection.execute(
            "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE slot_id = 1 AND active_task_id = ?",
            (task_id,),
        )
        row = connection.execute(
            _REVISION_SELECT + "WHERE revisions.id = ?", (revision_id,)
        ).fetchone()
        assert row is not None
        current_generation, current_version, date_version, meeting_date = _source_state_context(
            connection, task["meeting_id"]
        )
        return _revision_payload(
            connection,
            row,
            current_generation_id=current_generation,
            current_source_version=current_version,
            current_notes_source_version=date_version,
            current_meeting_date=meeting_date,
        )
