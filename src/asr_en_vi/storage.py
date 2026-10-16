"""SQLite initialization for the durable app data volume."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2


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
        connection.commit()
    finally:
        connection.close()
    os.chmod(path, 0o600)
    return path
