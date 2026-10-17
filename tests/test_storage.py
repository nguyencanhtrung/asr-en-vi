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
    }
    assert versions == [1, 2, 3, 4]
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
        }.issubset(tables)
