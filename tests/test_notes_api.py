from __future__ import annotations

import sqlite3
import time

import pytest
from httpx import ASGITransport, AsyncClient
from notes_helpers import seed_completed_transcript

from asr_en_vi.app import create_app
from asr_en_vi.chatgpt import DIRECT_SCOPE
from asr_en_vi.config import Settings
from asr_en_vi.notes import publish_notes_revision
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import claim_next_task

pytestmark = pytest.mark.anyio


async def test_notes_routes_enforce_auth_and_preserve_saved_revision_contract(
    tmp_path, monkeypatch
):
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        meeting_id, generation_id, _ = seed_completed_transcript(settings.data_dir)
        monkeypatch.setattr("asr_en_vi.notes_routes.worker_is_healthy", lambda _path: True)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=settings.public_url
        ) as client:
            assert (await client.get(f"/api/meetings/{meeting_id}/notes")).status_code == 401
            assert (await client.get("/assets/notes.js")).status_code == 303
            token = app.state.auth_store.load().token
            origin = {"Origin": settings.public_url}
            authenticated = await client.post(
                "/api/access/session", headers=origin, json={"token": token}
            )
            assert authenticated.status_code == 204

            provider = app.state.chatgpt_provider
            client_id = "oaiapp_test-123456"
            with provider.store.locked(write=True) as state:
                state["connection_status"] = "connected"
                state["connection_version"] = 9
                state["active_client_id"] = client_id
                state["registrations"][client_id] = {
                    "access_token": "local-test-access-token",
                    "refresh_token": "local-test-refresh-token",
                    "expires_at": time.time() + 3600,
                    "scopes": [DIRECT_SCOPE],
                    "subject": "test-subject",
                    "label": "Test account",
                }
                state["notes_provider"] = "chatgpt"
                state["selected_model"] = "gpt-6.1-sol"
                state["selected_reasoning_effort"] = "high"

            accepted = await client.post(
                f"/api/meetings/{meeting_id}/notes-runs",
                headers=origin,
                json={
                    "request_id": "api-notes-request-001",
                    "expected_generation_id": generation_id,
                    "expected_source_version": 1,
                    "expected_metadata_version": 1,
                },
            )
            assert accepted.status_code == 202
            task = accepted.json()
            assert task["kind"] == "notes"
            assert task["status"] == "accepted"
            assert task["result_scope"] == "notes_only"

            listing = await client.get(f"/api/meetings/{meeting_id}/notes")
            assert listing.status_code == 200
            assert listing.json()["revisions"] == []
            assert listing.json()["task"]["id"] == task["id"]
            assert listing.json()["source_locked"] is True
            meeting = await client.get(f"/api/meetings/{meeting_id}")
            assert meeting.json()["notes_source_locked"] is True
            with sqlite3.connect(database_path(settings.data_dir)) as connection:
                source_id = connection.execute(
                    "SELECT notes_source_id FROM tasks WHERE id = ?", (task["id"],)
                ).fetchone()[0]

            claimed = claim_next_task(settings.data_dir, owner_id="api-notes-worker")
            assert claimed is not None and claimed["id"] == task["id"]
            saved = publish_notes_revision(
                settings.data_dir,
                task["id"],
                owner_id="api-notes-worker",
                markdown="# Notes\n\nSaved, complete text.\n",
                elapsed_seconds=2.0,
            )
            assert saved is not None

            source = await client.get(f"/api/notes-sources/{source_id}")
            assert source.status_code == 200
            assert source.json()["segments"][0]["text"] == "We need a launch plan."
            detail = await client.get(f"/api/notes/{saved['id']}")
            assert detail.status_code == 200
            assert detail.json()["source_state"] == "current"
            export = await client.get(f"/api/notes/{saved['id']}/export")
            assert export.status_code == 200
            assert export.text == "# Notes\n\nSaved, complete text.\n"

            conflict = await client.patch(
                f"/api/notes/{saved['id']}",
                headers=origin,
                json={"expected_edit_version": 2, "markdown": "Do not overwrite."},
            )
            assert conflict.status_code == 409
            assert conflict.json()["detail"]["code"] == "notes_edit_version_changed"
            updated = await client.patch(
                f"/api/notes/{saved['id']}",
                headers=origin,
                json={"expected_edit_version": 1, "markdown": "# Edited locally\n"},
            )
            assert updated.status_code == 200
            assert updated.json()["edit_version"] == 2
            assert updated.json()["markdown"] == "# Edited locally\n"
