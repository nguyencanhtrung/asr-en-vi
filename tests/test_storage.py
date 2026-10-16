from __future__ import annotations

import os
import sqlite3

from asr_en_vi.storage import initialize


def test_sqlite_persists_across_reopen_without_prescribing_domain_schema(tmp_path):
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
    assert tables == {"schema_migrations", "acceptance_seed"}
    assert os.stat(data_dir).st_mode & 0o777 == 0o700
    assert os.stat(database).st_mode & 0o777 == 0o600
