from __future__ import annotations

import asyncio
import io
import json
import sqlite3
import threading
import time
import wave

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from media_tools import require_media_tools
from starlette.requests import ClientDisconnect

from asr_en_vi import recordings as recordings_module
from asr_en_vi import routes as routes_module
from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.media import MediaProcessingError

pytestmark = pytest.mark.anyio


def _wav_bytes(duration_seconds: float = 0.5) -> bytes:
    frame_rate = 16000
    frame_count = int(frame_rate * duration_seconds)
    audio = io.BytesIO()
    with wave.open(audio, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(frame_rate)
        output.writeframes(b"\0\0" * frame_count)
    return audio.getvalue()


async def _authorize(client: AsyncClient, settings: Settings) -> None:
    state = AuthStore(settings.auth_dir).load()
    response = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": state.token},
    )
    assert response.status_code == 204


async def _upload_ready(client: AsyncClient, settings: Settings, content: bytes) -> dict:
    _require_media_tools()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "sample.wav", "size_bytes": len(content)},
    )
    assert created.status_code == 201, created.text
    upload = created.json()
    received = await client.put(
        upload["content_url"],
        headers={"Origin": settings.public_url},
        content=content,
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "uploaded"
    complete = await client.post(
        upload["complete_url"],
        headers={"Origin": settings.public_url},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "ready"
    return upload


_require_media_tools = require_media_tools


async def test_wav_upload_normalizes_attaches_idempotently_and_keeps_date_empty(client, settings):
    await _authorize(client, settings)
    policy = await client.get("/api/uploads/policy")
    assert policy.status_code == 200
    assert policy.json()["extensions"] == [
        "wav",
        "mp3",
        "m4a",
        "mp4",
        "mov",
        "webm",
        "ogg",
        "opus",
        "flac",
    ]
    assert policy.json()["max_size_bytes"] == 4 * 1024**3
    assert policy.json()["max_duration_seconds"] == 4 * 60 * 60
    assert policy.json()["output"] == {
        "container": "m4a",
        "audio_codec": "aac",
        "bitrate_kbps": 160,
        "faststart": True,
    }

    source = _wav_bytes()
    upload = await _upload_ready(client, settings, source)
    raw_path = settings.data_dir / "uploads" / f"{upload['id']}.part"
    managed_path = settings.data_dir / "recordings" / f"{upload['id']}.m4a"
    assert not raw_path.exists()
    assert managed_path.is_file()
    assert managed_path.stat().st_mode & 0o777 == 0o600

    attached = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url},
        json={"upload_id": upload["id"], "title": "  Planning  ", "language_hint": "en"},
    )
    assert attached.status_code == 201, attached.text
    meeting = attached.json()
    assert meeting["title"] == "Planning"
    assert meeting["meeting_date"] is None
    assert meeting["language_hint"] == "en"
    assert meeting["metadata_version"] == 1
    assert meeting["recording"]["content_type"] == "audio/mp4"
    assert meeting["recording"]["audio_url"] == f"/api/meetings/{meeting['id']}/audio"

    retry = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url},
        json={"upload_id": upload["id"], "title": "Planning", "language_hint": "en"},
    )
    assert retry.status_code == 201
    assert retry.json() == meeting
    conflict = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url},
        json={"upload_id": upload["id"], "title": "Different", "language_hint": "en"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"

    upload_state = await client.get(f"/api/uploads/{upload['id']}")
    assert upload_state.json()["status"] == "consumed"
    assert upload_state.json()["meeting_url"] == f"/meetings/{meeting['id']}"
    assert str(settings.data_dir) not in json.dumps(meeting)
    assert str(settings.data_dir) not in json.dumps(upload_state.json())


async def test_corrupt_and_unsupported_uploads_fail_with_safe_codes_and_cleanup(client, settings):
    _require_media_tools()
    await _authorize(client, settings)
    unsupported = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "sample.exe", "size_bytes": 8},
    )
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"]["code"] == "unsupported_extension"
    missing_dot = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "wav", "size_bytes": 8},
    )
    assert missing_dot.status_code == 400
    assert missing_dot.json()["detail"]["code"] == "invalid_filename"

    content = b"not an audio file"
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "corrupt.wav", "size_bytes": len(content)},
    )
    upload_id = created.json()["id"]
    received = await client.put(
        f"/api/uploads/{upload_id}/content",
        headers={"Origin": settings.public_url},
        content=content,
    )
    assert received.status_code == 200
    failed = await client.post(
        f"/api/uploads/{upload_id}/complete",
        headers={"Origin": settings.public_url},
    )
    assert failed.status_code == 422
    assert failed.json()["detail"]["code"] == "invalid_media"
    state = await client.get(f"/api/uploads/{upload_id}")
    assert state.json()["status"] == "failed"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()
    assert not (settings.data_dir / "recordings" / f"{upload_id}.m4a").exists()
    assert str(settings.data_dir) not in failed.text


async def test_oversize_and_byte_mismatch_fail_before_media_processing(client, settings):
    await _authorize(client, settings)
    oversize = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "large.wav", "size_bytes": 4 * 1024**3 + 1},
    )
    assert oversize.status_code == 413
    assert oversize.json()["detail"]["code"] == "upload_too_large"

    content = _wav_bytes()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "short.wav", "size_bytes": len(content) + 1},
    )
    upload_id = created.json()["id"]
    mismatch = await client.put(
        f"/api/uploads/{upload_id}/content",
        headers={"Origin": settings.public_url},
        content=content,
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "size_mismatch"
    state = await client.get(f"/api/uploads/{upload_id}")
    assert state.json()["status"] == "failed"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()


async def test_interrupted_upload_stream_is_failed_and_removed(client, settings):
    await _authorize(client, settings)
    content = _wav_bytes()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "disconnect.wav", "size_bytes": len(content)},
    )
    upload_id = created.json()["id"]

    async def interrupted_stream():
        yield content[:32]
        raise httpx.ReadError("simulated disconnect")

    interrupted = await client.put(
        f"/api/uploads/{upload_id}/content",
        headers={"Origin": settings.public_url},
        content=interrupted_stream(),
    )
    assert interrupted.status_code == 400
    assert interrupted.json()["detail"]["code"] == "upload_interrupted"

    state = await client.get(f"/api/uploads/{upload_id}")
    assert state.json()["status"] == "failed"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()


async def test_client_disconnect_is_propagated_after_upload_cleanup(client, settings):
    await _authorize(client, settings)
    content = _wav_bytes()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "disconnect.wav", "size_bytes": len(content)},
    )
    upload_id = created.json()["id"]

    async def disconnected_stream():
        yield content[:32]
        raise ClientDisconnect

    with pytest.raises(ClientDisconnect):
        await client.put(
            f"/api/uploads/{upload_id}/content",
            headers={"Origin": settings.public_url},
            content=disconnected_stream(),
        )

    state = await client.get(f"/api/uploads/{upload_id}")
    assert state.json()["status"] == "failed"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()


async def test_range_head_and_unsatisfiable_range_are_exact(client, settings):
    await _authorize(client, settings)
    upload = await _upload_ready(client, settings, _wav_bytes())
    attached = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url},
        json={"upload_id": upload["id"], "title": "Range test", "language_hint": "vi"},
    )
    meeting_id = attached.json()["id"]
    full = await client.get(f"/api/meetings/{meeting_id}/audio")
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["content-type"] == "audio/mp4"
    assert int(full.headers["content-length"]) == len(full.content)

    partial = await client.get(f"/api/meetings/{meeting_id}/audio", headers={"Range": "bytes=0-5"})
    assert partial.status_code == 206
    assert partial.content == full.content[:6]
    assert partial.headers["content-range"] == f"bytes 0-5/{len(full.content)}"
    assert partial.headers["content-length"] == "6"

    suffix = await client.get(f"/api/meetings/{meeting_id}/audio", headers={"Range": "bytes=-5"})
    assert suffix.status_code == 206
    assert suffix.content == full.content[-5:]
    assert (
        suffix.headers["content-range"]
        == f"bytes {len(full.content) - 5}-{len(full.content) - 1}/{len(full.content)}"
    )

    head = await client.head(f"/api/meetings/{meeting_id}/audio", headers={"Range": "bytes=2-7"})
    assert head.status_code == 206
    assert head.content == b""
    assert head.headers["content-range"] == f"bytes 2-7/{len(full.content)}"
    assert head.headers["content-length"] == "6"

    invalid = await client.get(
        f"/api/meetings/{meeting_id}/audio", headers={"Range": f"bytes={len(full.content)}-"}
    )
    assert invalid.status_code == 416
    assert invalid.headers["content-range"] == f"bytes */{len(full.content)}"
    multiple = await client.get(
        f"/api/meetings/{meeting_id}/audio", headers={"Range": "bytes=0-1,4-5"}
    )
    assert multiple.status_code == 200
    assert multiple.content == full.content
    for ignored_range in ("items=0-1", "bytes=bad", "bytes=7-2"):
        ignored = await client.get(
            f"/api/meetings/{meeting_id}/audio", headers={"Range": ignored_range}
        )
        assert ignored.status_code == 200
        assert ignored.content == full.content
    zero_suffix = await client.get(
        f"/api/meetings/{meeting_id}/audio", headers={"Range": "bytes=-0"}
    )
    assert zero_suffix.status_code == 416


async def test_audio_survives_app_recreation_and_original_is_gone(settings):
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        await _authorize(client, settings)
        upload = await _upload_ready(client, settings, _wav_bytes())
        meeting = await client.post(
            "/api/meetings",
            headers={"Origin": settings.public_url},
            json={
                "upload_id": upload["id"],
                "title": "Persistent",
                "language_hint": "en",
            },
        )
        meeting_id = meeting.json()["id"]
        persisted_audio = await client.get(f"/api/meetings/{meeting_id}/audio")
        assert persisted_audio.status_code == 200
        assert not (settings.data_dir / "uploads" / f"{upload['id']}.part").exists()

    reopened_app = create_app(settings)
    async with (
        reopened_app.router.lifespan_context(reopened_app),
        AsyncClient(
            transport=ASGITransport(app=reopened_app), base_url=settings.public_url
        ) as client,
    ):
        await _authorize(client, settings)
        meeting_response = await client.get(f"/api/meetings/{meeting_id}")
        audio_response = await client.get(f"/api/meetings/{meeting_id}/audio")
        assert meeting_response.status_code == 200
        assert audio_response.status_code == 200
        assert audio_response.content == persisted_audio.content


async def test_startup_recovery_fails_unattached_uploads_and_keeps_consumed_audio(settings):
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        await _authorize(client, settings)
        upload = await _upload_ready(client, settings, _wav_bytes())
        ready_upload = await _upload_ready(client, settings, _wav_bytes())
        meeting = await client.post(
            "/api/meetings",
            headers={"Origin": settings.public_url},
            json={
                "upload_id": upload["id"],
                "title": "Keep me",
                "language_hint": "en",
            },
        )
        meeting_id = meeting.json()["id"]
        stale_ids = []
        for status in ("receiving", "uploaded", "validating"):
            stale = await client.post(
                "/api/uploads",
                headers={"Origin": settings.public_url},
                json={"filename": f"{status}.wav", "size_bytes": len(_wav_bytes())},
            )
            stale_ids.append(stale.json()["id"])
        with sqlite3.connect(settings.data_dir / "app.sqlite3") as connection:
            for stale_id, status in zip(
                stale_ids, ("receiving", "uploaded", "validating"), strict=True
            ):
                connection.execute("UPDATE uploads SET status = ? WHERE id = ?", (status, stale_id))
        stale_paths = [settings.data_dir / "uploads" / f"{stale_id}.part" for stale_id in stale_ids]
        temp_dir = settings.data_dir / ".recording-tmp"
        temp_path = temp_dir / "orphan.tmp"
        temp_path.write_bytes(b"temporary")
        orphan_upload = settings.data_dir / "uploads" / "orphan.part"
        orphan_audio = settings.data_dir / "recordings" / f"{'f' * 32}.m4a"
        orphan_upload.write_bytes(b"partial")
        orphan_audio.write_bytes(b"unreferenced")

    restarted = create_app(settings)
    async with restarted.router.lifespan_context(restarted):
        assert all(not path.exists() for path in stale_paths)
        assert not temp_path.exists()
        assert not orphan_upload.exists()
        assert not orphan_audio.exists()
        assert (settings.data_dir / "recordings" / f"{upload['id']}.m4a").exists()
        assert not (settings.data_dir / "recordings" / f"{ready_upload['id']}.m4a").exists()
        with sqlite3.connect(settings.data_dir / "app.sqlite3") as connection:
            statuses = [
                connection.execute(
                    "SELECT status FROM uploads WHERE id = ?", (stale_id,)
                ).fetchone()[0]
                for stale_id in stale_ids
            ]
        assert statuses == ["failed", "failed", "failed"]
        async with AsyncClient(
            transport=ASGITransport(app=restarted), base_url=settings.public_url
        ) as client:
            await _authorize(client, settings)
            response = await client.get(f"/api/meetings/{meeting_id}/audio")
            ready_response = await client.get(f"/api/uploads/{ready_upload['id']}")
            assert response.status_code == 200
            assert ready_response.json()["status"] == "failed"


async def test_new_upload_sweeps_stale_unattached_files(client, settings):
    await _authorize(client, settings)
    stale = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "stale.wav", "size_bytes": 8},
    )
    stale_id = stale.json()["id"]
    stale_path = settings.data_dir / "uploads" / f"{stale_id}.part"
    stale_path.write_bytes(b"partial")
    with sqlite3.connect(settings.data_dir / "app.sqlite3") as connection:
        connection.execute(
            "UPDATE uploads SET created_at = datetime('now', '-2 days') WHERE id = ?",
            (stale_id,),
        )

    replacement = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "replacement.wav", "size_bytes": 8},
    )

    assert replacement.status_code == 201
    stale_state = await client.get(f"/api/uploads/{stale_id}")
    assert stale_state.json()["status"] == "failed"
    assert not stale_path.exists()


async def test_delete_cancels_active_validation_and_removes_artifacts(
    client, settings, monkeypatch
):
    await _authorize(client, settings)
    content = _wav_bytes()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "cancel.wav", "size_bytes": len(content)},
    )
    upload_id = created.json()["id"]
    received = await client.put(
        f"/api/uploads/{upload_id}/content",
        headers={"Origin": settings.public_url},
        content=content,
    )
    assert received.status_code == 200
    validation_started = threading.Event()

    def cancellable_normalize(
        source_path,
        output_path,
        *,
        max_duration_seconds,
        should_cancel,
    ):
        validation_started.set()
        deadline = time.monotonic() + 2
        while not should_cancel() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not should_cancel():
            raise AssertionError("DELETE did not cancel the active validation")
        raise MediaProcessingError("media_processing_cancelled")

    monkeypatch.setattr(recordings_module, "normalize_media", cancellable_normalize)
    completion_task = asyncio.create_task(
        client.post(
            f"/api/uploads/{upload_id}/complete",
            headers={"Origin": settings.public_url},
        )
    )
    assert await asyncio.to_thread(validation_started.wait, 2)

    deleted = await client.delete(
        f"/api/uploads/{upload_id}", headers={"Origin": settings.public_url}
    )
    completed = await asyncio.wait_for(completion_task, timeout=2)

    assert deleted.status_code == 200
    assert deleted.json()["status"] == "failed"
    assert completed.status_code == 409
    assert completed.json()["detail"]["code"] == "media_processing_cancelled"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()
    assert not (settings.data_dir / "recordings" / f"{upload_id}.m4a").exists()


async def test_upload_idle_timeout_fails_and_cleans_partial_file(client, settings, monkeypatch):
    await _authorize(client, settings)
    content = _wav_bytes()
    created = await client.post(
        "/api/uploads",
        headers={"Origin": settings.public_url},
        json={"filename": "stalled.wav", "size_bytes": len(content)},
    )
    upload_id = created.json()["id"]
    monkeypatch.setattr(routes_module, "_UPLOAD_IDLE_TIMEOUT_SECONDS", 0.02)

    async def stalled_stream():
        yield content[:32]
        await asyncio.Event().wait()

    timed_out = await asyncio.wait_for(
        client.put(
            f"/api/uploads/{upload_id}/content",
            headers={"Origin": settings.public_url},
            content=stalled_stream(),
        ),
        timeout=2,
    )

    assert timed_out.status_code == 408
    assert timed_out.json()["detail"]["code"] == "upload_timeout"
    state = await client.get(f"/api/uploads/{upload_id}")
    assert state.json()["status"] == "failed"
    assert not (settings.data_dir / "uploads" / f"{upload_id}.part").exists()


async def test_declared_duration_limit_is_enforced(tmp_path):
    _require_media_tools()
    settings = Settings(
        data_dir=tmp_path / "limited-data",
        auth_dir=tmp_path / "limited-auth",
        public_url="http://127.0.0.1:8765",
        max_recording_seconds=1,
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        await _authorize(client, settings)
        upload = await client.post(
            "/api/uploads",
            headers={"Origin": settings.public_url},
            json={"filename": "long.wav", "size_bytes": len(_wav_bytes(1.5))},
        )
        upload_id = upload.json()["id"]
        await client.put(
            f"/api/uploads/{upload_id}/content",
            headers={"Origin": settings.public_url},
            content=_wav_bytes(1.5),
        )
        complete = await client.post(
            f"/api/uploads/{upload_id}/complete",
            headers={"Origin": settings.public_url},
        )
        assert complete.status_code == 413
        assert complete.json()["detail"]["code"] == "duration_limit"


async def test_meeting_details_validate_title_date_and_language(client, settings):
    await _authorize(client, settings)
    upload = await _upload_ready(client, settings, _wav_bytes())
    base_payload = {"upload_id": upload["id"], "title": "Valid", "language_hint": "en"}
    invalids = [
        {**base_payload, "title": "   "},
        {**base_payload, "title": "x" * 201},
        {**base_payload, "meeting_date": "2026-02-30"},
        {**base_payload, "language_hint": "fr"},
    ]
    for payload in invalids:
        response = await client.post(
            "/api/meetings", headers={"Origin": settings.public_url}, json=payload
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"].startswith("invalid_")


async def test_shell_route_and_script_are_protected_and_refresh_uses_shell(client, settings):
    unauthenticated = await client.get("/meetings/known-id", follow_redirects=False)
    assert unauthenticated.status_code == 303
    await _authorize(client, settings)
    page = await client.get("/meetings/known-id")
    assert page.status_code == 200
    assert "ASR EN VI" in page.text
    for name in (
        "shell.js",
        "shell-core.js",
        "store.js",
        "notes-core.js",
        "notes.js",
        "provider-core.js",
        "connections.js",
        "antigravity.js",
    ):
        script = await client.get(f"/assets/{name}")
        assert script.status_code == 200, name
        assert script.headers["content-type"].startswith("text/javascript"), name
