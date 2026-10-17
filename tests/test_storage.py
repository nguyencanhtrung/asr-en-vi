from __future__ import annotations

import os
import sqlite3

from asr_en_vi.storage import initialize


def test_sqlite_persists_across_reopen_with_current_domain_schema(tmp_path):
    data_dir = tmp_path / "persistent-data"
    database = initialize(data_dir)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE acceptance_seed (value TEXT NOT NULL)")
        connection.execute("INSERT INTO acceptance_seed(value) VALUES ('persisted')")

    reopened = initialize(data_dir)

    assert reopened == database
    with sqlite3.connect(reopened) as connection:
        assert connection.execute("SELECT value FROM acceptance_seed").fetchone() == ("persisted",)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
    assert tables == {
        "schema_migrations",
        "acceptance_seed",
        "meetings",
        "uploads",
        "recordings",
        "tasks",
        "processing_slot",
        "transcript_generations",
        "transcript_segments",
        "generation_speakers",
    }
    assert versions == [1, 2, 3, 4, 5]
    assert os.stat(data_dir).st_mode & 0o777 == 0o700
    assert os.stat(database).st_mode & 0o777 == 0o600


def test_schema_v1_database_migrates_transactionally_and_preserves_existing_data(tmp_path):
    data_dir = tmp_path / "legacy-data"
    data_dir.mkdir(mode=0o700)
    database = data_dir / "app.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")
        connection.execute("CREATE TABLE legacy_values (value TEXT NOT NULL)")
        connection.execute("INSERT INTO legacy_values(value) VALUES ('kept')")

    initialize(data_dir)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM legacy_values").fetchone() == ("kept",)
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [
            (1,),
            (2,),
            (3,),
            (4,),
            (5,),
        ]
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "meetings",
            "uploads",
            "recordings",
            "tasks",
            "processing_slot",
            "transcript_generations",
            "transcript_segments",
            "generation_speakers",
        }.issubset(tables)


def test_schema_v4_migration_preserves_existing_generation_and_backfills_its_speaker_catalog(
    tmp_path,
):
    data_dir = tmp_path / "version-four-data"
    data_dir.mkdir(mode=0o700)
    database = data_dir / "app.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);"
            "INSERT INTO schema_migrations(version) VALUES (4);"
            "CREATE TABLE tasks(id TEXT PRIMARY KEY);"
            "CREATE TABLE transcript_generations(id TEXT PRIMARY KEY);"
            "CREATE TABLE meetings(id TEXT PRIMARY KEY, current_generation_id TEXT);"
            "CREATE TABLE transcript_segments("
            "id TEXT PRIMARY KEY, generation_id TEXT NOT NULL, sequence INTEGER NOT NULL, "
            "start_seconds REAL NOT NULL, end_seconds REAL NOT NULL, text TEXT NOT NULL, "
            "original_speaker_id TEXT, speaker_id TEXT);"
            "INSERT INTO transcript_generations(id) VALUES ('old-generation');"
            "INSERT INTO meetings(id, current_generation_id) "
            "VALUES ('old-meeting', 'old-generation');"
            "INSERT INTO transcript_segments(id, generation_id, sequence, start_seconds, "
            "end_seconds, text, original_speaker_id, speaker_id) VALUES "
            "('old-segment', 'old-generation', 0, 1.25, 2.5, 'Kept text.', "
            "'legacy-speaker', 'legacy-speaker');"
        )

    initialize(data_dir)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT current_generation_id FROM meetings WHERE id = 'old-meeting'"
        ).fetchone() == ("old-generation",)
        assert connection.execute(
            "SELECT text, start_seconds, end_seconds, original_speaker_id, speaker_id "
            "FROM transcript_segments WHERE id = 'old-segment'"
        ).fetchone() == ("Kept text.", 1.25, 2.5, "legacy-speaker", "legacy-speaker")
        assert connection.execute(
            "SELECT speaker_id, display_name, first_seen_seconds, last_seen_seconds "
            "FROM generation_speakers WHERE generation_id = 'old-generation'"
        ).fetchall() == [("legacy-speaker", "legacy-speaker", 1.25, 2.5)]
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone() == (5,)
