"""Durable transcription task transitions and complete transcript publication."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asr_en_vi.runner import ModelConfigurationError, prepared_model_directory
from asr_en_vi.storage import database_path

UNCERTAINTY_POLICY = "faster-whisper-review-cues-v1"
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{8,128}\Z")
_SEGMENT_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
_ACTIVE_TASK_STATES = frozenset({"accepted", "running", "stopping"})
_TASK_HEARTBEAT_MAX_AGE_SECONDS = 20


class TaskError(RuntimeError):
    """An API-safe failure in task acceptance or lifecycle transitions."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


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


def _request_id(value: object) -> str:
    if not isinstance(value, str) or not _REQUEST_ID_RE.fullmatch(value):
        raise TaskError(
            400,
            "invalid_request_id",
            "request_id must contain 8 to 128 letters, digits, dots, underscores, "
            "colons, or hyphens.",
        )
    return value


def _payload_hash(
    *,
    meeting_id: str,
) -> str:
    encoded = json.dumps(
        {"meeting_id": meeting_id}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _worker_state(row: sqlite3.Row) -> str:
    if row["status"] not in _ACTIVE_TASK_STATES:
        return "idle"
    heartbeat_at = row["heartbeat_at"]
    if not heartbeat_at:
        return "checking-worker"
    try:
        heartbeat = datetime.fromisoformat(heartbeat_at)
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - heartbeat).total_seconds()
    except (TypeError, ValueError):
        return "checking-worker"
    if -1 <= age <= _TASK_HEARTBEAT_MAX_AGE_SECONDS:
        return "healthy"
    return "checking-worker"


def _task_summary(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "request_id": row["request_id"],
        "meeting_id": row["meeting_id"],
        "kind": row["kind"],
        "status": row["status"],
        "worker_state": _worker_state(row),
        "stage": row["stage"],
        "result_scope": row["result_scope"],
        "audio_duration_seconds": row["audio_duration_seconds"],
        "transcript_end_seconds": row["transcript_end_seconds"],
        "segment_count": row["segment_count"],
        "elapsed_seconds": row["elapsed_seconds"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "accepted_at": row["accepted_at"],
        "started_at": row["started_at"],
        "heartbeat_at": row["heartbeat_at"],
        "cancel_requested_at": row["cancel_requested_at"],
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
    }


def accept_transcription_task(
    data_dir: Path,
    *,
    meeting_id: object,
    request_id: object,
    model_path: Path,
    device: str,
    compute_type: str,
    worker_ready: bool,
) -> dict[str, object]:
    """Accept one request atomically, returning the original row for HTTP retries."""
    if not isinstance(meeting_id, str) or not meeting_id:
        raise TaskError(400, "invalid_meeting_id", "Provide a meeting_id.")
    normalized_request_id = _request_id(request_id)
    normalized_model_path = str(Path(model_path).expanduser().resolve())
    model_name = Path(normalized_model_path).name
    task_id = uuid.uuid4().hex

    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        meeting = connection.execute(
            "SELECT id, language_hint FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        if meeting is None:
            raise TaskError(404, "meeting_not_found", "Meeting not found.")
        request_hash = _payload_hash(
            meeting_id=meeting_id,
        )
        existing = connection.execute(
            "SELECT * FROM tasks WHERE request_id = ?", (normalized_request_id,)
        ).fetchone()
        if existing is not None:
            if existing["request_hash"] != request_hash:
                raise TaskError(
                    409,
                    "idempotency_conflict",
                    "This request_id was already used with different task details.",
                )
            return _task_summary(existing)

        slot = connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()
        if slot is None:
            raise TaskError(503, "processing_unavailable", "The processing slot is unavailable.")
        if slot["active_task_id"] is not None:
            raise TaskError(
                409,
                "system_busy",
                "Another transcription task owns the processing slot.",
            )
        if not worker_ready:
            raise TaskError(503, "worker_unavailable", "The transcription worker is unavailable.")
        try:
            prepared_model_directory(Path(normalized_model_path))
        except ModelConfigurationError:
            raise TaskError(
                503,
                "model_unavailable",
                "The configured local faster-whisper model is not prepared.",
            ) from None

        recording = connection.execute(
            "SELECT duration_seconds FROM recordings WHERE meeting_id = ?", (meeting_id,)
        ).fetchone()
        if recording is None:
            raise TaskError(404, "meeting_not_found", "Meeting recording not found.")

        connection.execute(
            "INSERT INTO tasks(id, request_id, request_hash, meeting_id, kind, model_path, "
            "model_name, device, compute_type, language_hint, status, stage, "
            "audio_duration_seconds) "
            "VALUES (?, ?, ?, ?, 'transcription', ?, ?, ?, ?, ?, 'accepted', 'accepted', ?)",
            (
                task_id,
                normalized_request_id,
                request_hash,
                meeting_id,
                normalized_model_path,
                model_name,
                device,
                compute_type,
                meeting["language_hint"],
                recording["duration_seconds"],
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
        summary = _task_summary(row)
    return summary


def get_task(data_dir: Path, task_id: str) -> dict[str, object]:
    with _connect(data_dir) as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskError(404, "task_not_found", "Task not found.")
    return _task_summary(row)


def cancel_task(data_dir: Path, task_id: str) -> dict[str, object]:
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskError(404, "task_not_found", "Task not found.")
        if row["status"] == "accepted":
            connection.execute(
                "UPDATE tasks SET status = 'canceled', stage = 'canceled', "
                "cancel_requested_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'accepted'",
                (task_id,),
            )
            connection.execute(
                "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE slot_id = 1 AND active_task_id = ?",
                (task_id,),
            )
        elif row["status"] == "running":
            connection.execute(
                "UPDATE tasks SET status = 'stopping', stage = 'stopping', "
                "cancel_requested_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND status = 'running'",
                (task_id,),
            )
        updated = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert updated is not None
        return _task_summary(updated)


def claim_next_task(data_dir: Path, *, owner_id: str) -> dict[str, object] | None:
    """Atomically claim the one accepted task and bind it to a worker ownership token."""
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        slot = connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()
        if slot is None or slot["active_task_id"] is None:
            return None
        task_id = slot["active_task_id"]
        cursor = connection.execute(
            "UPDATE tasks SET status = 'running', stage = 'starting', owner_id = ?, "
            "started_at = CURRENT_TIMESTAMP, heartbeat_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'accepted'",
            (owner_id, task_id),
        )
        if cursor.rowcount != 1:
            return None
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        return dict(row)


def task_runtime_state(data_dir: Path, task_id: str) -> tuple[str, str | None] | None:
    with _connect(data_dir) as connection:
        row = connection.execute(
            "SELECT status, owner_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return None
    return row["status"], row["owner_id"]


def update_task_progress(
    data_dir: Path,
    task_id: str,
    *,
    owner_id: str,
    stage: str,
    elapsed_seconds: float,
    transcript_end_seconds: float,
    segment_count: int,
) -> bool:
    with _connect(data_dir) as connection, connection:
        cursor = connection.execute(
            "UPDATE tasks SET stage = ?, elapsed_seconds = ?, "
            "transcript_end_seconds = MAX(transcript_end_seconds, ?), segment_count = ?, "
            "heartbeat_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND owner_id = ? AND status = 'running'",
            (
                stage,
                max(0.0, elapsed_seconds),
                max(0.0, transcript_end_seconds),
                max(0, segment_count),
                task_id,
                owner_id,
            ),
        )
        return cursor.rowcount == 1


def fail_task(
    data_dir: Path,
    task_id: str,
    *,
    owner_id: str,
    error_code: str,
    message: str,
    elapsed_seconds: float,
) -> bool:
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            "SELECT status FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        if task is None or task["status"] not in {"running", "stopping"}:
            return False
        if task["status"] == "stopping":
            connection.execute(
                "UPDATE tasks SET status = 'canceled', stage = 'canceled', "
                "elapsed_seconds = ?, completed_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_id = ? "
                "AND status = 'stopping'",
                (max(0.0, elapsed_seconds), task_id, owner_id),
            )
        else:
            connection.execute(
                "UPDATE tasks SET status = 'failed', stage = 'failed', error_code = ?, "
                "error_message = ?, elapsed_seconds = ?, completed_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_id = ? "
                "AND status = 'running'",
                (error_code, message, max(0.0, elapsed_seconds), task_id, owner_id),
            )
        connection.execute(
            "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE slot_id = 1 AND active_task_id = ?",
            (task_id,),
        )
        return True


def finish_canceled_task(
    data_dir: Path, task_id: str, *, owner_id: str, elapsed_seconds: float
) -> bool:
    """Release the slot only after the worker has terminated and reaped its runner group."""
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            "UPDATE tasks SET status = 'canceled', stage = 'canceled', elapsed_seconds = ?, "
            "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND owner_id = ? AND status = 'stopping'",
            (max(0.0, elapsed_seconds), task_id, owner_id),
        )
        if cursor.rowcount == 1:
            connection.execute(
                "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE slot_id = 1 AND active_task_id = ?",
                (task_id,),
            )
            return True
        return False


def finish_interrupted_task(
    data_dir: Path,
    task_id: str,
    *,
    owner_id: str,
    elapsed_seconds: float,
    message: str = "The worker stopped before transcription finished.",
) -> bool:
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            "SELECT status FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        if task is None or task["status"] not in {"running", "stopping"}:
            return False
        if task["status"] == "stopping":
            connection.execute(
                "UPDATE tasks SET status = 'canceled', stage = 'canceled', elapsed_seconds = ?, "
                "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND owner_id = ? AND status = 'stopping'",
                (max(0.0, elapsed_seconds), task_id, owner_id),
            )
        else:
            connection.execute(
                "UPDATE tasks SET status = 'interrupted', stage = 'interrupted', "
                "error_code = 'worker_stopped', error_message = ?, elapsed_seconds = ?, "
                "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND owner_id = ? AND status = 'running'",
                (message, max(0.0, elapsed_seconds), task_id, owner_id),
            )
        connection.execute(
            "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE slot_id = 1 AND active_task_id = ?",
            (task_id,),
        )
        return True


def _number(value: object, *, field: str, minimum: float | None = None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TaskError(500, "invalid_runner_result", f"Invalid {field} in runner result.")
    normalized = float(value)
    if not math.isfinite(normalized) or (minimum is not None and normalized < minimum):
        raise TaskError(500, "invalid_runner_result", f"Invalid {field} in runner result.")
    return normalized


def _validated_segments(segments: Sequence[dict[str, Any]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for sequence, segment in enumerate(segments):
        segment_id = segment.get("id")
        text = segment.get("text")
        if (
            not isinstance(segment_id, str)
            or not _SEGMENT_ID_RE.fullmatch(segment_id)
            or segment_id in seen_ids
            or not isinstance(text, str)
        ):
            raise TaskError(500, "invalid_runner_result", "The runner returned an invalid segment.")
        seen_ids.add(segment_id)
        start_seconds = _number(segment.get("start_seconds"), field="start_seconds", minimum=0)
        end_seconds = _number(segment.get("end_seconds"), field="end_seconds", minimum=0)
        if start_seconds is None or end_seconds is None:
            raise TaskError(500, "invalid_runner_result", "Segment timestamps are required.")
        if end_seconds < start_seconds:
            raise TaskError(500, "invalid_runner_result", "Segment timestamps are out of order.")
        avg_logprob = _number(segment.get("avg_logprob"), field="avg_logprob")
        no_speech_prob = _number(segment.get("no_speech_prob"), field="no_speech_prob", minimum=0)
        compression_ratio = _number(
            segment.get("compression_ratio"), field="compression_ratio", minimum=0
        )
        if no_speech_prob is not None and no_speech_prob > 1:
            raise TaskError(
                500, "invalid_runner_result", "Invalid no_speech_prob in runner result."
            )
        uncertain = (
            (avg_logprob is not None and avg_logprob < -1.0)
            or (no_speech_prob is not None and no_speech_prob >= 0.6)
            or (compression_ratio is not None and compression_ratio > 2.4)
        )
        rows.append(
            {
                "id": segment_id,
                "sequence": sequence,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "text": text,
                "original_speaker_id": None,
                "speaker_id": None,
                "avg_logprob": avg_logprob,
                "no_speech_prob": no_speech_prob,
                "compression_ratio": compression_ratio,
                "uncertain": int(uncertain),
            }
        )
    return rows


def publish_complete_generation(
    data_dir: Path,
    task_id: str,
    *,
    owner_id: str,
    segments: Sequence[dict[str, Any]],
    language_probability: object,
    elapsed_seconds: float,
) -> dict[str, object] | None:
    """Atomically publish a full generation and succeed only for its current owner."""
    rows = _validated_segments(segments)
    normalized_language_probability = _number(
        language_probability, field="language_probability", minimum=0
    )
    if normalized_language_probability is not None and normalized_language_probability > 1:
        raise TaskError(500, "invalid_runner_result", "Invalid language probability.")
    latest_segment_end = max((float(row["end_seconds"]) for row in rows), default=0.0)

    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        slot = connection.execute(
            "SELECT active_task_id FROM processing_slot WHERE slot_id = 1"
        ).fetchone()
        if (
            task is None
            or task["status"] != "running"
            or task["owner_id"] != owner_id
            or slot is None
            or slot["active_task_id"] != task_id
        ):
            return None

        generation_id = uuid.uuid4().hex
        generation_number = connection.execute(
            "SELECT COALESCE(MAX(generation_number), 0) + 1 FROM transcript_generations "
            "WHERE meeting_id = ?",
            (task["meeting_id"],),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO transcript_generations(id, meeting_id, task_id, generation_number, "
            "status, language_hint, model_name, language_probability, uncertainty_policy, "
            "segment_count) VALUES (?, ?, ?, ?, 'complete', ?, ?, ?, ?, ?)",
            (
                generation_id,
                task["meeting_id"],
                task_id,
                generation_number,
                task["language_hint"],
                task["model_name"],
                normalized_language_probability,
                UNCERTAINTY_POLICY,
                len(rows),
            ),
        )
        connection.executemany(
            "INSERT INTO transcript_segments(id, generation_id, sequence, start_seconds, "
            "end_seconds, text, original_speaker_id, speaker_id, avg_logprob, no_speech_prob, "
            "compression_ratio, uncertain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["id"],
                    generation_id,
                    row["sequence"],
                    row["start_seconds"],
                    row["end_seconds"],
                    row["text"],
                    row["original_speaker_id"],
                    row["speaker_id"],
                    row["avg_logprob"],
                    row["no_speech_prob"],
                    row["compression_ratio"],
                    row["uncertain"],
                )
                for row in rows
            ],
        )
        connection.execute(
            "UPDATE meetings SET current_generation_id = ? WHERE id = ?",
            (generation_id, task["meeting_id"]),
        )
        cursor = connection.execute(
            "UPDATE tasks SET status = 'succeeded', stage = 'complete', "
            "result_scope = 'transcript_only', transcript_end_seconds = ?, segment_count = ?, "
            "elapsed_seconds = ?, completed_at = CURRENT_TIMESTAMP, "
            "heartbeat_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND owner_id = ? AND status = 'running'",
            (
                latest_segment_end,
                len(rows),
                max(0.0, elapsed_seconds),
                task_id,
                owner_id,
            ),
        )
        if cursor.rowcount != 1:
            raise TaskError(409, "task_ownership_changed", "Task ownership changed before publish.")
        connection.execute(
            "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE slot_id = 1 AND active_task_id = ?",
            (task_id,),
        )
        return {
            "id": generation_id,
            "meeting_id": task["meeting_id"],
            "generation_number": generation_number,
            "status": "complete",
            "segment_count": len(rows),
            "uncertainty_policy": UNCERTAINTY_POLICY,
        }


def recover_abandoned_tasks(data_dir: Path) -> list[str]:
    """Cancel stopping tasks and interrupt other active work once the exclusive lock is held."""
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            "SELECT id FROM tasks WHERE status IN ('accepted', 'running', 'stopping')"
        ).fetchall()
        task_ids = [row["id"] for row in rows]
        connection.execute(
            "UPDATE tasks SET status = 'canceled', stage = 'canceled', "
            "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE status = 'stopping'"
        )
        connection.execute(
            "UPDATE tasks SET status = 'interrupted', stage = 'interrupted', "
            "error_code = 'worker_restarted', "
            "error_message = 'The worker restarted before transcription finished.', "
            "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE status IN ('accepted', 'running')"
        )
        connection.execute(
            "UPDATE processing_slot SET active_task_id = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE slot_id = 1"
        )
    return task_ids


def transcription_state(data_dir: Path, meeting_id: str) -> dict[str, object]:
    """Return the latest durable task and the current complete generation for meeting detail."""
    with _connect(data_dir) as connection:
        latest = connection.execute(
            "SELECT * FROM tasks WHERE meeting_id = ? ORDER BY rowid DESC LIMIT 1",
            (meeting_id,),
        ).fetchone()
        generation = connection.execute(
            "SELECT transcript_generations.* FROM meetings "
            "JOIN transcript_generations "
            "ON transcript_generations.id = meetings.current_generation_id "
            "WHERE meetings.id = ?",
            (meeting_id,),
        ).fetchone()
        segments: list[dict[str, object]] = []
        if generation is not None:
            segment_rows = connection.execute(
                "SELECT id, sequence, start_seconds, end_seconds, text, original_speaker_id, "
                "speaker_id, avg_logprob, no_speech_prob, compression_ratio, uncertain "
                "FROM transcript_segments WHERE generation_id = ? ORDER BY sequence",
                (generation["id"],),
            ).fetchall()
            segments = [
                {
                    "id": row["id"],
                    "sequence": row["sequence"],
                    "start_seconds": row["start_seconds"],
                    "end_seconds": row["end_seconds"],
                    "text": row["text"],
                    "original_speaker_id": row["original_speaker_id"],
                    "speaker_id": row["speaker_id"],
                    "avg_logprob": row["avg_logprob"],
                    "no_speech_prob": row["no_speech_prob"],
                    "compression_ratio": row["compression_ratio"],
                    "uncertain": bool(row["uncertain"]),
                }
                for row in segment_rows
            ]

    generation_summary: dict[str, object] | None = None
    if generation is not None:
        generation_summary = {
            "id": generation["id"],
            "generation_number": generation["generation_number"],
            "status": generation["status"],
            "language_hint": generation["language_hint"],
            "model_name": generation["model_name"],
            "language_probability": generation["language_probability"],
            "source_version": generation["source_version"],
            "uncertainty_policy": generation["uncertainty_policy"],
            "segment_count": generation["segment_count"],
            "completed_at": generation["completed_at"],
            "segments": segments,
        }
    return {
        "task": _task_summary(latest) if latest is not None else None,
        "generation": generation_summary,
    }
