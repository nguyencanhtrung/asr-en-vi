"""Insert meetings straight into SQLite so history tests need no media tools."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from asr_en_vi.storage import database_path


def seed_meeting(
    data_dir: Path,
    title: str,
    meeting_date: str | None = None,
    *,
    language_hint: str = "en",
    duration_seconds: float = 1.0,
) -> str:
    meeting_id = uuid.uuid4().hex
    upload_id = uuid.uuid4().hex
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO uploads(id, filename, declared_size, status, raw_key, managed_key) "
            "VALUES (?, 'seed.wav', 1, 'consumed', ?, ?)",
            (upload_id, f"uploads/{upload_id}.part", f"recordings/{upload_id}.m4a"),
        )
        connection.execute(
            "INSERT INTO meetings(id, title, meeting_date, language_hint) VALUES (?, ?, ?, ?)",
            (meeting_id, title, meeting_date, language_hint),
        )
        connection.execute(
            "INSERT INTO recordings(id, meeting_id, upload_id, storage_key, duration_seconds) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                meeting_id,
                upload_id,
                f"recordings/{upload_id}.m4a",
                duration_seconds,
            ),
        )
    connection.close()
    return meeting_id
