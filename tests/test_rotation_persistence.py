from __future__ import annotations

import sqlite3

import pytest

from asr_en_vi.auth import AuthStore, create_session_cookie, session_is_valid, token_matches
from asr_en_vi.storage import initialize
from asr_en_vi.worker import heartbeat_path, write_heartbeat


def test_rotation_invalidates_old_access_and_preserves_data_and_worker_state(settings):
    store = AuthStore(settings.auth_dir)
    previous = store.ensure()
    old_cookie = create_session_cookie(previous)
    database = initialize(settings.data_dir)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE acceptance_seed (value TEXT NOT NULL)")
        connection.execute("INSERT INTO acceptance_seed(value) VALUES ('keep this row')")
    write_heartbeat(settings.data_dir)
    liveness = heartbeat_path(settings.data_dir)
    worker_state_before = (liveness.read_bytes(), liveness.stat().st_mtime_ns)

    rotated = store.rotate()

    assert rotated.token != previous.token
    assert rotated.generation == previous.generation + 1
    assert rotated.signing_secret == previous.signing_secret
    assert not token_matches(previous.token, rotated.token)
    assert not session_is_valid(old_cookie, rotated)
    assert session_is_valid(create_session_cookie(rotated), rotated)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM acceptance_seed").fetchone() == (
            "keep this row",
        )
    assert (liveness.read_bytes(), liveness.stat().st_mtime_ns) == worker_state_before


@pytest.mark.anyio
async def test_http_exchange_rejects_old_token_and_cookie_after_rotation(client, settings):
    store = AuthStore(settings.auth_dir)
    previous = store.load()
    exchange = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": previous.token},
    )
    assert exchange.status_code == 204
    old_cookie = client.cookies.get("asr_en_vi_session")
    assert (await client.get("/")).status_code == 200

    rotated = store.rotate()

    old_token = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": previous.token},
    )
    assert old_token.status_code == 401
    assert old_cookie is not None
    assert (await client.get("/api/meetings")).status_code == 401

    new_session = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": rotated.token},
    )
    assert new_session.status_code == 204
    assert (await client.get("/")).status_code == 200
