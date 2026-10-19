"""Upload, meeting and recording persistence for app-managed audio."""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import stat
import unicodedata
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import date
from pathlib import Path
from typing import BinaryIO

from asr_en_vi.media import (
    ALLOWED_EXTENSIONS,
    OUTPUT_CONTENT_TYPE,
    MediaProcessingError,
    normalize_media,
)
from asr_en_vi.storage import database_path

_UPLOAD_KEY_RE = re.compile(r"uploads/[0-9a-f]{32}\.part\Z")
_AUDIO_KEY_RE = re.compile(r"recordings/[0-9a-f]{32}\.m4a\Z")
_FILENAME_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
STALE_UPLOAD_SECONDS = 24 * 60 * 60


class RecordingError(RuntimeError):
    """An API-safe failure in upload or recording operations."""

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


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise RecordingError(500, "storage_unavailable", "Recording storage is unavailable.")
    os.chmod(path, 0o700)


def _path_for_key(data_dir: Path, key: str) -> Path:
    if _UPLOAD_KEY_RE.fullmatch(key) or _AUDIO_KEY_RE.fullmatch(key):
        return Path(data_dir) / key
    raise RecordingError(500, "storage_unavailable", "Recording storage is unavailable.")


def _unlink_key(data_dir: Path, key: str | None) -> None:
    if key is None:
        return
    path = _path_for_key(data_dir, key)
    with suppress(FileNotFoundError):
        path.unlink()


def _safe_filename(filename: object) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 255
        or filename in {".", ".."}
        or "." not in filename
        or "/" in filename
        or "\\" in filename
        or _FILENAME_CONTROL_RE.search(filename)
    ):
        raise RecordingError(400, "invalid_filename", "Provide a filename without a path.")
    extension = filename.rpartition(".")[2].lower()
    if not extension or extension not in ALLOWED_EXTENSIONS:
        raise RecordingError(
            415,
            "unsupported_extension",
            "Choose an audio or video file with a supported extension.",
        )
    return filename


def cleanup_stale_uploads(data_dir: Path, *, max_age_seconds: int = STALE_UPLOAD_SECONDS) -> None:
    """Fail and remove abandoned, unattached uploads older than the retention window."""
    if max_age_seconds < 1:
        raise ValueError("max_age_seconds must be positive")
    modifier = f"-{max_age_seconds} seconds"
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            "SELECT id, raw_key, managed_key FROM uploads "
            "WHERE status IN ('receiving', 'uploaded', 'validating', 'ready') "
            "AND created_at <= datetime('now', ?)",
            (modifier,),
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE uploads SET status = 'failed', content_started = 0, "
                "failure_code = 'expired' WHERE id = ? "
                "AND status IN ('receiving', 'uploaded', 'validating', 'ready')",
                (row["id"],),
            )
    for row in rows:
        _unlink_key(data_dir, row["raw_key"])
        _unlink_key(data_dir, row["managed_key"])


def _upload_summary(row: sqlite3.Row, *, meeting_id: str | None = None) -> dict[str, object]:
    summary: dict[str, object] = {
        "id": row["id"],
        "filename": row["filename"],
        "size_bytes": row["declared_size"],
        "status": row["status"],
        "upload_url": f"/api/uploads/{row['id']}",
        "content_url": f"/api/uploads/{row['id']}/content",
        "complete_url": f"/api/uploads/{row['id']}/complete",
    }
    if row["duration_seconds"] is not None:
        summary["duration_seconds"] = row["duration_seconds"]
    if row["status"] in {"ready", "consumed"}:
        summary["content_type"] = OUTPUT_CONTENT_TYPE
    if meeting_id is not None:
        summary["meeting_url"] = f"/meetings/{meeting_id}"
    return summary


def create_upload(
    data_dir: Path,
    *,
    filename: object,
    size_bytes: object,
    max_upload_bytes: int,
) -> dict[str, object]:
    cleanup_stale_uploads(data_dir)
    safe_name = _safe_filename(filename)
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 1:
        raise RecordingError(400, "invalid_size", "Provide a positive size_bytes value.")
    if size_bytes > max_upload_bytes:
        raise RecordingError(
            413,
            "upload_too_large",
            f"The file exceeds the {max_upload_bytes}-byte upload limit.",
        )

    upload_id = uuid.uuid4().hex
    raw_key = f"uploads/{upload_id}.part"
    raw_path = _path_for_key(data_dir, raw_key)
    _ensure_private_directory(raw_path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(raw_path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    os.close(descriptor)
    try:
        with _connect(data_dir) as connection, connection:
            connection.execute(
                "INSERT INTO uploads(id, filename, declared_size, status, raw_key) "
                "VALUES (?, ?, ?, 'receiving', ?)",
                (upload_id, safe_name, size_bytes, raw_key),
            )
    except BaseException:
        _unlink_key(data_dir, raw_key)
        raise
    return {
        "id": upload_id,
        "filename": safe_name,
        "size_bytes": size_bytes,
        "status": "receiving",
        "upload_url": f"/api/uploads/{upload_id}",
        "content_url": f"/api/uploads/{upload_id}/content",
        "complete_url": f"/api/uploads/{upload_id}/complete",
    }


def begin_upload(data_dir: Path, upload_id: str) -> tuple[Path, int]:
    with _connect(data_dir) as connection, connection:
        cursor = connection.execute(
            "UPDATE uploads SET content_started = 1 "
            "WHERE id = ? AND status = 'receiving' AND content_started = 0",
            (upload_id,),
        )
        if cursor.rowcount != 1:
            row = connection.execute(
                "SELECT status FROM uploads WHERE id = ?", (upload_id,)
            ).fetchone()
            if row is None:
                raise RecordingError(404, "upload_not_found", "Upload not found.")
            raise RecordingError(
                409,
                "upload_state_conflict",
                f"Upload content cannot be received while status is {row['status']}.",
            )
        row = connection.execute(
            "SELECT raw_key, declared_size FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        assert row is not None
        return _path_for_key(data_dir, row["raw_key"]), row["declared_size"]


def finish_upload(data_dir: Path, upload_id: str) -> None:
    with _connect(data_dir) as connection, connection:
        cursor = connection.execute(
            "UPDATE uploads SET status = 'uploaded', content_started = 0 "
            "WHERE id = ? AND status = 'receiving' AND content_started = 1",
            (upload_id,),
        )
        if cursor.rowcount != 1:
            raise RecordingError(
                409, "upload_state_conflict", "Upload state changed during transfer."
            )


def fail_upload(data_dir: Path, upload_id: str, *, code: str) -> None:
    raw_key: str | None = None
    managed_key: str | None = None
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status, raw_key, managed_key FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if row is None or row["status"] in {"ready", "consumed"}:
            return
        connection.execute(
            "UPDATE uploads SET status = 'failed', content_started = 0, failure_code = ? "
            "WHERE id = ? AND status NOT IN ('ready', 'consumed')",
            (code, upload_id),
        )
        raw_key = row["raw_key"]
        managed_key = row["managed_key"]
    _unlink_key(data_dir, raw_key)
    _unlink_key(data_dir, managed_key)


def _media_error(error: MediaProcessingError) -> RecordingError:
    messages = {
        "media_tool_unavailable": (503, "Audio validation tools are unavailable."),
        "media_processing_timeout": (422, "Audio processing timed out. Try a shorter recording."),
        "media_processing_cancelled": (409, "Audio validation was cancelled."),
        "media_processing_failed": (422, "The uploaded file could not be processed."),
        "invalid_media": (422, "The uploaded file is corrupt or cannot be read."),
        "missing_audio_stream": (422, "The uploaded file does not contain an audio stream."),
        "unsupported_codec": (415, "The audio codec is not supported. Choose another file."),
        "duration_limit": (413, "The recording exceeds the maximum audio duration."),
        "conversion_failed": (422, "The audio could not be converted. Choose another file."),
    }
    status_code, message = messages.get(
        error.code, (422, "The uploaded file could not be processed.")
    )
    return RecordingError(status_code, error.code, message)


def _upload_validation_cancelled(data_dir: Path, upload_id: str) -> bool:
    with _connect(data_dir) as connection:
        row = connection.execute("SELECT status FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    return row is None or row["status"] != "validating"


def complete_upload(
    data_dir: Path,
    upload_id: str,
    *,
    max_duration_seconds: int,
) -> dict[str, object]:
    """Validate and publish one upload. Call from a worker thread, not the event loop."""
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
        if row is None:
            raise RecordingError(404, "upload_not_found", "Upload not found.")
        if row["status"] in {"ready", "consumed"}:
            return _upload_summary(row)
        if row["status"] != "uploaded":
            raise RecordingError(
                409,
                "upload_state_conflict",
                f"Upload cannot be completed while status is {row['status']}.",
            )
        cursor = connection.execute(
            "UPDATE uploads SET status = 'validating' WHERE id = ? AND status = 'uploaded'",
            (upload_id,),
        )
        if cursor.rowcount != 1:
            raise RecordingError(409, "upload_state_conflict", "Upload state changed.")
        raw_key = row["raw_key"]

    managed_key = f"recordings/{upload_id}.m4a"
    ready_committed = False
    temp_path: Path | None = None
    try:
        raw_path = _path_for_key(data_dir, raw_key)
        final_path = _path_for_key(data_dir, managed_key)
        _ensure_private_directory(final_path.parent)
        temp_dir = Path(data_dir) / ".recording-tmp"
        _ensure_private_directory(temp_dir)
        temp_path = temp_dir / f"{upload_id}-{secrets.token_hex(8)}.m4a"
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temp_path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        normalized = normalize_media(
            raw_path,
            temp_path,
            max_duration_seconds=max_duration_seconds,
            should_cancel=lambda: _upload_validation_cancelled(data_dir, upload_id),
        )
        os.chmod(temp_path, 0o600)
        with temp_path.open("rb") as audio_file:
            os.fsync(audio_file.fileno())
        os.replace(temp_path, final_path)
        os.chmod(final_path, 0o600)
        directory_fd = os.open(final_path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        with _connect(data_dir) as connection, connection:
            cursor = connection.execute(
                "UPDATE uploads SET status = 'ready', managed_key = ?, duration_seconds = ?, "
                "source_codec = ?, failure_code = NULL "
                "WHERE id = ? AND status = 'validating'",
                (managed_key, normalized.duration_seconds, normalized.codec_name, upload_id),
            )
            if cursor.rowcount != 1:
                raise RecordingError(409, "upload_state_conflict", "Upload state changed.")
        ready_committed = True
        _unlink_key(data_dir, raw_key)
        with _connect(data_dir) as connection:
            row = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
            assert row is not None
            return _upload_summary(row)
    except MediaProcessingError as error:
        fail_upload(data_dir, upload_id, code=error.code)
        _unlink_key(data_dir, managed_key)
        raise _media_error(error) from None
    except BaseException as error:
        if not ready_committed:
            fail_upload(data_dir, upload_id, code="storage_failed")
            _unlink_key(data_dir, managed_key)
        if isinstance(error, RecordingError):
            raise
        raise RecordingError(
            500, "storage_failed", "The recording could not be saved safely."
        ) from None
    finally:
        if temp_path is not None:
            with suppress(FileNotFoundError):
                temp_path.unlink()


def get_upload(data_dir: Path, upload_id: str) -> dict[str, object]:
    with _connect(data_dir) as connection:
        row = connection.execute(
            "SELECT uploads.*, recordings.meeting_id "
            "FROM uploads LEFT JOIN recordings ON recordings.upload_id = uploads.id "
            "WHERE uploads.id = ?",
            (upload_id,),
        ).fetchone()
    if row is None:
        raise RecordingError(404, "upload_not_found", "Upload not found.")
    return _upload_summary(row, meeting_id=row["meeting_id"])


def delete_upload(data_dir: Path, upload_id: str) -> dict[str, object]:
    raw_key: str | None = None
    managed_key: str | None = None
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
        if row is None:
            raise RecordingError(404, "upload_not_found", "Upload not found.")
        if row["status"] == "consumed":
            raise RecordingError(
                409,
                "upload_consumed",
                "This upload belongs to a meeting and cannot be deleted.",
            )
        raw_key = row["raw_key"]
        managed_key = row["managed_key"]
        connection.execute(
            "UPDATE uploads SET status = 'failed', content_started = 0, "
            "failure_code = 'deleted' WHERE id = ?",
            (upload_id,),
        )
    _unlink_key(data_dir, raw_key)
    _unlink_key(data_dir, managed_key)
    return {"id": upload_id, "status": "failed"}


def _validate_title(title: object) -> str:
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise RecordingError(400, "invalid_title", "Title must contain 1 to 200 characters.")
    return title.strip()


def _validate_date(meeting_date: object) -> str | None:
    if meeting_date is not None:
        if not isinstance(meeting_date, str):
            raise RecordingError(400, "invalid_meeting_date", "Use a YYYY-MM-DD meeting date.")
        try:
            parsed_date = date.fromisoformat(meeting_date)
        except ValueError:
            raise RecordingError(
                400, "invalid_meeting_date", "Use a valid YYYY-MM-DD meeting date."
            ) from None
        if parsed_date.isoformat() != meeting_date:
            raise RecordingError(400, "invalid_meeting_date", "Use a YYYY-MM-DD meeting date.")
    return meeting_date


def _validate_meeting(
    title: object, meeting_date: object, language_hint: object
) -> tuple[str, str | None, str]:
    normalized_title = _validate_title(title)
    normalized_date = _validate_date(meeting_date)
    if not isinstance(language_hint, str) or language_hint not in {"en", "vi"}:
        raise RecordingError(400, "invalid_language_hint", "language_hint must be en or vi.")
    return normalized_title, normalized_date, language_hint


def create_meeting(
    data_dir: Path,
    *,
    upload_id: object,
    title: object,
    meeting_date: object,
    language_hint: object,
) -> dict[str, object]:
    if not isinstance(upload_id, str) or not upload_id:
        raise RecordingError(400, "invalid_upload_id", "Provide a ready upload_id.")
    normalized_title, normalized_date, normalized_language = _validate_meeting(
        title, meeting_date, language_hint
    )
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT meetings.*, recordings.id AS recording_id, recordings.upload_id, "
            "recordings.storage_key, recordings.content_type, recordings.duration_seconds "
            "FROM recordings JOIN meetings ON meetings.id = recordings.meeting_id "
            "WHERE recordings.upload_id = ?",
            (upload_id,),
        ).fetchone()
        if existing is not None:
            payload_matches = (
                existing["title"] == normalized_title
                and existing["meeting_date"] == normalized_date
                and existing["language_hint"] == normalized_language
            )
            if not payload_matches:
                raise RecordingError(
                    409,
                    "idempotency_conflict",
                    "This upload was already attached with different meeting details.",
                )
            return _meeting_summary(existing)

        upload = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
        if upload is None:
            raise RecordingError(404, "upload_not_found", "Upload not found.")
        if upload["status"] != "ready" or not upload["managed_key"]:
            raise RecordingError(
                409,
                "upload_not_ready",
                "Complete and validate the upload before creating a meeting.",
            )
        meeting_id = uuid.uuid4().hex
        recording_id = uuid.uuid4().hex
        connection.execute(
            "INSERT INTO meetings(id, title, meeting_date, language_hint) VALUES (?, ?, ?, ?)",
            (meeting_id, normalized_title, normalized_date, normalized_language),
        )
        connection.execute(
            "INSERT INTO recordings(id, meeting_id, upload_id, storage_key, content_type, "
            "duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (
                recording_id,
                meeting_id,
                upload_id,
                upload["managed_key"],
                OUTPUT_CONTENT_TYPE,
                upload["duration_seconds"],
            ),
        )
        cursor = connection.execute(
            "UPDATE uploads SET status = 'consumed' WHERE id = ? AND status = 'ready'",
            (upload_id,),
        )
        if cursor.rowcount != 1:
            raise RecordingError(409, "upload_not_ready", "Upload state changed.")
        row = connection.execute(
            "SELECT meetings.*, recordings.id AS recording_id, recordings.upload_id, "
            "recordings.storage_key, recordings.content_type, recordings.duration_seconds "
            "FROM recordings JOIN meetings ON meetings.id = recordings.meeting_id "
            "WHERE meetings.id = ?",
            (meeting_id,),
        ).fetchone()
        assert row is not None
        return _meeting_summary(row)


def _meeting_summary(row: sqlite3.Row) -> dict[str, object]:
    meeting_id = row["id"]
    return {
        "id": meeting_id,
        "meeting_url": f"/meetings/{meeting_id}",
        "title": row["title"],
        "meeting_date": row["meeting_date"],
        "language_hint": row["language_hint"],
        "metadata_version": row["metadata_version"],
        "notes_source_version": row["notes_source_version"],
        "created_at": row["created_at"],
        "recording": {
            "id": row["recording_id"],
            "duration_seconds": row["duration_seconds"],
            "content_type": row["content_type"],
            "audio_url": f"/api/meetings/{meeting_id}/audio",
        },
    }


def get_meeting(data_dir: Path, meeting_id: str) -> dict[str, object]:
    with _connect(data_dir) as connection:
        row = connection.execute(
            "SELECT meetings.*, recordings.id AS recording_id, recordings.upload_id, "
            "recordings.storage_key, recordings.content_type, recordings.duration_seconds "
            "FROM meetings JOIN recordings ON recordings.meeting_id = meetings.id "
            "WHERE meetings.id = ?",
            (meeting_id,),
        ).fetchone()
        source_locked = (
            connection.execute(
                "SELECT 1 FROM tasks WHERE meeting_id = ? AND kind = 'notes' "
                "AND status IN ('accepted', 'running', 'stopping') LIMIT 1",
                (meeting_id,),
            ).fetchone()
            is not None
        )
    if row is None:
        raise RecordingError(404, "meeting_not_found", "Meeting not found.")
    summary = _meeting_summary(row)
    summary["notes_source_locked"] = source_locked
    from asr_en_vi.tasks import transcription_state

    summary["transcription"] = transcription_state(data_dir, meeting_id)
    return summary


def _history_item(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "meeting_url": f"/meetings/{row['id']}",
        "title": row["title"],
        "meeting_date": row["meeting_date"],
        "metadata_version": row["metadata_version"],
        "duration_seconds": row["duration_seconds"],
    }


def _search_key(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def list_meetings(data_dir: Path, *, query: str | None = None) -> dict[str, object]:
    """Meeting history: newest meeting date first, undated last, title search over all rows.

    ``recent`` ignores the search and holds at most three dated meetings.
    """
    with _connect(data_dir) as connection:
        rows = connection.execute(
            "SELECT meetings.id, meetings.title, meetings.meeting_date, "
            "meetings.metadata_version, recordings.duration_seconds "
            "FROM meetings JOIN recordings ON recordings.meeting_id = meetings.id "
            "ORDER BY meetings.meeting_date IS NULL, meetings.meeting_date DESC, "
            "meetings.created_at DESC, meetings.rowid DESC"
        ).fetchall()
    items = [_history_item(row) for row in rows]
    needle = _search_key(query.strip()) if query else ""
    matches = [item for item in items if needle in _search_key(str(item["title"]))]
    return {
        "meetings": matches,
        "total": len(items),
        "recent": [item for item in items if item["meeting_date"] is not None][:3],
    }


def update_meeting(
    data_dir: Path,
    meeting_id: str,
    *,
    expected_version: object,
    fields: dict[str, object],
) -> dict[str, object]:
    """Edit title and/or meeting date under optimistic concurrency.

    Only a date change bumps ``notes_source_version``; language is never editable here.
    """
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise RecordingError(400, "invalid_expected_version", "Provide expected_metadata_version.")
    if not fields:
        raise RecordingError(400, "invalid_request", "Provide a title or meeting_date change.")
    new_title = _validate_title(fields["title"]) if "title" in fields else None
    new_date = _validate_date(fields["meeting_date"]) if "meeting_date" in fields else None
    with _connect(data_dir) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT title, meeting_date, metadata_version FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        if current is None:
            raise RecordingError(404, "meeting_not_found", "Meeting not found.")
        if current["metadata_version"] != expected_version:
            raise RecordingError(
                409,
                "stale_version",
                "Meeting metadata changed in another tab. Reload it and compare your draft.",
            )
        title = current["title"] if new_title is None else new_title
        meeting_date = current["meeting_date"] if "meeting_date" not in fields else new_date
        date_changed = meeting_date != current["meeting_date"]
        if date_changed:
            active_notes = connection.execute(
                "SELECT 1 FROM tasks WHERE meeting_id = ? AND kind = 'notes' "
                "AND status IN ('accepted', 'running', 'stopping') LIMIT 1",
                (meeting_id,),
            ).fetchone()
            if active_notes is not None:
                raise RecordingError(
                    409,
                    "notes_source_locked",
                    "The meeting date is locked while notes are being generated.",
                )
        if title != current["title"] or date_changed:
            connection.execute(
                "UPDATE meetings SET title = ?, meeting_date = ?, "
                "metadata_version = metadata_version + 1, "
                "notes_source_version = notes_source_version + ? WHERE id = ?",
                (title, meeting_date, int(date_changed), meeting_id),
            )
    return get_meeting(data_dir, meeting_id)


def get_audio_recording(data_dir: Path, meeting_id: str) -> dict[str, object]:
    with _connect(data_dir) as connection:
        row = connection.execute(
            "SELECT id, storage_key, content_type FROM recordings WHERE meeting_id = ?",
            (meeting_id,),
        ).fetchone()
    if row is None:
        raise RecordingError(404, "meeting_not_found", "Meeting recording not found.")
    return {
        "id": row["id"],
        "storage_key": row["storage_key"],
        "content_type": row["content_type"],
    }


def recording_path(data_dir: Path, meeting_id: str) -> Path:
    """Resolve an application-managed recording for the local transcription runner."""
    recording = get_audio_recording(data_dir, meeting_id)
    path = _path_for_key(data_dir, recording["storage_key"])
    try:
        file_stat = path.lstat()
    except OSError as error:
        raise RecordingError(
            500, "recording_unavailable", "Meeting recording is unavailable."
        ) from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise RecordingError(500, "recording_unavailable", "Meeting recording is unavailable.")
    return path


def open_audio(data_dir: Path, storage_key: str) -> tuple[int, BinaryIO]:
    path = _path_for_key(data_dir, storage_key)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RecordingError(
            500, "recording_unavailable", "Recording audio is unavailable."
        ) from exc
    file_stat = os.fstat(descriptor)
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(descriptor)
        raise RecordingError(500, "recording_unavailable", "Recording audio is unavailable.")
    return file_stat.st_size, os.fdopen(descriptor, "rb")


def recover_recordings(data_dir: Path) -> None:
    """Fail abandoned uploads and remove unreferenced app-managed artifacts at startup."""
    root = Path(data_dir)
    upload_dir = root / "uploads"
    audio_dir = root / "recordings"
    temp_dir = root / ".recording-tmp"
    _ensure_private_directory(upload_dir)
    _ensure_private_directory(audio_dir)
    _ensure_private_directory(temp_dir)

    with _connect(root) as connection:
        with connection:
            connection.execute(
                "UPDATE uploads SET status = 'failed', content_started = 0, "
                "failure_code = 'interrupted' "
                "WHERE status IN ('receiving', 'uploaded', 'validating', 'ready')"
            )
        rows = connection.execute("SELECT status, raw_key, managed_key FROM uploads").fetchall()
        referenced_audio = {
            row["managed_key"] for row in rows if row["status"] == "consumed" and row["managed_key"]
        }

    for row in rows:
        _unlink_key(root, row["raw_key"])
        if row["status"] != "consumed":
            _unlink_key(root, row["managed_key"])

    for path in upload_dir.iterdir():
        if path.is_file() or path.is_symlink():
            with suppress(FileNotFoundError):
                path.unlink()
    for directory, keep in ((audio_dir, referenced_audio),):
        for path in directory.iterdir():
            key = f"recordings/{path.name}"
            if key not in keep and (path.is_file() or path.is_symlink()):
                with suppress(FileNotFoundError):
                    path.unlink()
    for path in temp_dir.iterdir():
        if path.is_file() or path.is_symlink():
            with suppress(FileNotFoundError):
                path.unlink()
