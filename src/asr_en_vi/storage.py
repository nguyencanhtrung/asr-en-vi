"""SQLite initialization for the durable app data volume."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 5


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE meetings ("
        "id TEXT PRIMARY KEY, "
        "title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200), "
        "meeting_date TEXT CHECK(meeting_date IS NULL OR ("
        "length(meeting_date) = 10 AND "
        "meeting_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')), "
        "language_hint TEXT NOT NULL CHECK(language_hint IN ('en', 'vi')), "
        "metadata_version INTEGER NOT NULL DEFAULT 1 CHECK(metadata_version >= 1), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    connection.execute(
        "CREATE TABLE uploads ("
        "id TEXT PRIMARY KEY, "
        "filename TEXT NOT NULL, "
        "declared_size INTEGER NOT NULL CHECK(declared_size > 0), "
        "status TEXT NOT NULL CHECK(status IN ("
        "'receiving', 'uploaded', 'validating', 'ready', 'failed', 'consumed')), "
        "raw_key TEXT NOT NULL UNIQUE, "
        "managed_key TEXT UNIQUE, "
        "content_started INTEGER NOT NULL DEFAULT 0 CHECK(content_started IN (0, 1)), "
        "duration_seconds REAL CHECK(duration_seconds IS NULL OR duration_seconds > 0), "
        "source_codec TEXT, "
        "failure_code TEXT, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    connection.execute("CREATE INDEX uploads_status_idx ON uploads(status)")
    connection.execute(
        "CREATE TABLE recordings ("
        "id TEXT PRIMARY KEY, "
        "meeting_id TEXT NOT NULL UNIQUE REFERENCES meetings(id) ON DELETE RESTRICT, "
        "upload_id TEXT NOT NULL UNIQUE REFERENCES uploads(id) ON DELETE RESTRICT, "
        "storage_key TEXT NOT NULL UNIQUE, "
        "content_type TEXT NOT NULL DEFAULT 'audio/mp4', "
        "duration_seconds REAL NOT NULL CHECK(duration_seconds > 0), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )


def _migrate_v3(connection: sqlite3.Connection) -> None:
    # Bumped only when meeting_date changes; later Notes revisions compare it to
    # their source snapshot to detect staleness. Title edits never touch it.
    connection.execute(
        "ALTER TABLE meetings ADD COLUMN notes_source_version INTEGER NOT NULL DEFAULT 1 "
        "CHECK(notes_source_version >= 1)"
    )
    connection.execute("CREATE INDEX meetings_date_idx ON meetings(meeting_date)")


def _migrate_v4(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE tasks ("
        "id TEXT PRIMARY KEY, "
        "request_id TEXT NOT NULL UNIQUE, "
        "request_hash TEXT NOT NULL, "
        "meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE RESTRICT, "
        "kind TEXT NOT NULL CHECK(kind = 'transcription'), "
        "model_path TEXT NOT NULL, "
        "model_name TEXT NOT NULL, "
        "device TEXT NOT NULL CHECK(device IN ('auto', 'cpu', 'cuda')), "
        "compute_type TEXT NOT NULL, "
        "language_hint TEXT NOT NULL CHECK(language_hint IN ('en', 'vi')), "
        "status TEXT NOT NULL CHECK(status IN ("
        "'accepted', 'running', 'stopping', 'succeeded', 'failed', 'canceled', 'interrupted')), "
        "stage TEXT NOT NULL, "
        "result_scope TEXT CHECK(result_scope IS NULL OR result_scope = 'transcript_only'), "
        "audio_duration_seconds REAL NOT NULL CHECK(audio_duration_seconds > 0), "
        "transcript_end_seconds REAL NOT NULL DEFAULT 0 CHECK(transcript_end_seconds >= 0), "
        "segment_count INTEGER NOT NULL DEFAULT 0 CHECK(segment_count >= 0), "
        "elapsed_seconds REAL NOT NULL DEFAULT 0 CHECK(elapsed_seconds >= 0), "
        "owner_id TEXT, "
        "error_code TEXT, "
        "error_message TEXT, "
        "accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "started_at TEXT, "
        "heartbeat_at TEXT, "
        "cancel_requested_at TEXT, "
        "completed_at TEXT, "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    connection.execute(
        "CREATE INDEX tasks_meeting_created_idx ON tasks(meeting_id, accepted_at DESC, id DESC)"
    )
    connection.execute(
        "CREATE TABLE transcript_generations ("
        "id TEXT PRIMARY KEY, "
        "meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE RESTRICT, "
        "task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE RESTRICT, "
        "generation_number INTEGER NOT NULL CHECK(generation_number >= 1), "
        "status TEXT NOT NULL CHECK(status = 'complete'), "
        "language_hint TEXT NOT NULL CHECK(language_hint IN ('en', 'vi')), "
        "model_name TEXT NOT NULL, "
        "language_probability REAL CHECK(language_probability IS NULL OR "
        "(language_probability >= 0 AND language_probability <= 1)), "
        "source_version INTEGER NOT NULL DEFAULT 1 CHECK(source_version >= 1), "
        "uncertainty_policy TEXT NOT NULL, "
        "segment_count INTEGER NOT NULL CHECK(segment_count >= 0), "
        "completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(meeting_id, generation_number)"
        ")"
    )
    connection.execute(
        "CREATE INDEX transcript_generations_meeting_idx "
        "ON transcript_generations(meeting_id, generation_number DESC)"
    )
    connection.execute(
        "CREATE TABLE transcript_segments ("
        "id TEXT PRIMARY KEY, "
        "generation_id TEXT NOT NULL REFERENCES transcript_generations(id) ON DELETE RESTRICT, "
        "sequence INTEGER NOT NULL CHECK(sequence >= 0), "
        "start_seconds REAL NOT NULL CHECK(start_seconds >= 0), "
        "end_seconds REAL NOT NULL CHECK(end_seconds >= start_seconds), "
        "text TEXT NOT NULL, "
        "original_speaker_id TEXT, "
        "speaker_id TEXT, "
        "avg_logprob REAL, "
        "no_speech_prob REAL CHECK(no_speech_prob IS NULL OR "
        "(no_speech_prob >= 0 AND no_speech_prob <= 1)), "
        "compression_ratio REAL CHECK(compression_ratio IS NULL OR compression_ratio >= 0), "
        "uncertain INTEGER NOT NULL CHECK(uncertain IN (0, 1)), "
        "UNIQUE(generation_id, sequence)"
        ")"
    )
    connection.execute(
        "CREATE INDEX transcript_segments_generation_idx "
        "ON transcript_segments(generation_id, sequence)"
    )
    connection.execute(
        "CREATE TABLE processing_slot ("
        "slot_id INTEGER PRIMARY KEY CHECK(slot_id = 1), "
        "active_task_id TEXT UNIQUE REFERENCES tasks(id) ON DELETE RESTRICT, "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    connection.execute("INSERT INTO processing_slot(slot_id, active_task_id) VALUES (1, NULL)")
    connection.execute(
        "ALTER TABLE meetings ADD COLUMN current_generation_id TEXT "
        "REFERENCES transcript_generations(id) ON DELETE SET NULL"
    )


def _migrate_v5(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE tasks ADD COLUMN diarization_model_path TEXT NOT NULL DEFAULT ''"
    )
    connection.execute("ALTER TABLE transcript_generations ADD COLUMN diarization_model_name TEXT")
    connection.execute(
        "ALTER TABLE transcript_generations ADD COLUMN regular_turn_count INTEGER NOT NULL "
        "DEFAULT 0 CHECK(regular_turn_count >= 0)"
    )
    connection.execute(
        "ALTER TABLE transcript_generations ADD COLUMN exclusive_turn_count INTEGER NOT NULL "
        "DEFAULT 0 CHECK(exclusive_turn_count >= 0)"
    )
    connection.execute("ALTER TABLE transcript_generations ADD COLUMN alignment_policy TEXT")
    connection.execute(
        "ALTER TABLE transcript_segments ADD COLUMN review_reasons TEXT NOT NULL DEFAULT '[]' "
        "CHECK(json_valid(review_reasons))"
    )
    connection.execute(
        "ALTER TABLE transcript_segments ADD COLUMN overlap INTEGER NOT NULL DEFAULT 0 "
        "CHECK(overlap IN (0, 1))"
    )
    connection.execute(
        "ALTER TABLE transcript_segments ADD COLUMN speaker_dominance REAL CHECK("
        "speaker_dominance IS NULL OR (speaker_dominance >= 0 AND speaker_dominance <= 1))"
    )
    connection.execute(
        "ALTER TABLE transcript_segments ADD COLUMN assignment_version INTEGER NOT NULL "
        "DEFAULT 1 CHECK(assignment_version >= 1)"
    )
    connection.execute(
        "CREATE TABLE generation_speakers ("
        "generation_id TEXT NOT NULL REFERENCES transcript_generations(id) ON DELETE RESTRICT, "
        "speaker_id TEXT NOT NULL CHECK(length(trim(speaker_id)) BETWEEN 1 AND 80), "
        "display_name TEXT NOT NULL CHECK(length(trim(display_name)) BETWEEN 1 AND 80), "
        "first_seen_seconds REAL NOT NULL CHECK(first_seen_seconds >= 0), "
        "last_seen_seconds REAL NOT NULL CHECK(last_seen_seconds >= first_seen_seconds), "
        "PRIMARY KEY(generation_id, speaker_id), "
        "UNIQUE(generation_id, display_name)"
        ")"
    )
    connection.execute(
        "INSERT INTO generation_speakers(generation_id, speaker_id, display_name, "
        "first_seen_seconds, last_seen_seconds) "
        "SELECT generation_id, speaker_id, speaker_id, MIN(start_seconds), MAX(end_seconds) "
        "FROM ("
        "SELECT generation_id, original_speaker_id AS speaker_id, start_seconds, end_seconds "
        "FROM transcript_segments WHERE original_speaker_id IS NOT NULL "
        "UNION ALL "
        "SELECT generation_id, speaker_id, start_seconds, end_seconds "
        "FROM transcript_segments WHERE speaker_id IS NOT NULL"
        ") GROUP BY generation_id, speaker_id"
    )
    connection.execute(
        "CREATE TRIGGER transcript_segments_speakers_insert "
        "BEFORE INSERT ON transcript_segments WHEN "
        "(NEW.original_speaker_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM generation_speakers WHERE generation_id = NEW.generation_id "
        "AND speaker_id = NEW.original_speaker_id)) OR "
        "(NEW.speaker_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM generation_speakers WHERE generation_id = NEW.generation_id "
        "AND speaker_id = NEW.speaker_id)) "
        "BEGIN SELECT RAISE(ABORT, 'speaker_generation_mismatch'); END"
    )
    connection.execute(
        "CREATE TRIGGER transcript_segments_speakers_update "
        "BEFORE UPDATE OF generation_id, original_speaker_id, speaker_id "
        "ON transcript_segments WHEN "
        "(NEW.generation_id != OLD.generation_id) OR "
        "(NEW.original_speaker_id IS NOT OLD.original_speaker_id) OR "
        "(NEW.original_speaker_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM generation_speakers WHERE generation_id = NEW.generation_id "
        "AND speaker_id = NEW.original_speaker_id)) OR "
        "(NEW.speaker_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM generation_speakers WHERE generation_id = NEW.generation_id "
        "AND speaker_id = NEW.speaker_id)) "
        "BEGIN SELECT RAISE(ABORT, 'speaker_generation_mismatch'); END"
    )
    connection.execute(
        "CREATE TRIGGER generation_speakers_delete_guard BEFORE DELETE ON generation_speakers "
        "BEGIN SELECT RAISE(ABORT, 'generation_speakers_are_immutable'); END"
    )


def database_path(data_dir: Path) -> Path:
    return Path(data_dir) / "app.sqlite3"


def initialize(data_dir: Path) -> Path:
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = database_path(directory)
    if path.is_symlink():
        raise RuntimeError("SQLite database path must not be a symbolic link")
    if not path.exists():
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(descriptor)
    else:
        os.chmod(path, 0o600)

    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        current_version = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()[0]
        if current_version > SCHEMA_VERSION:
            raise RuntimeError("Database schema is newer than this application")
        if current_version < 2:
            _migrate_v2(connection)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (2)")
        if current_version < 3:
            _migrate_v3(connection)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (3)")
        if current_version < 4:
            _migrate_v4(connection)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (4)")
        if current_version < 5:
            _migrate_v5(connection)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (5)")
        connection.commit()
    finally:
        connection.close()
    os.chmod(path, 0o600)
    return path
