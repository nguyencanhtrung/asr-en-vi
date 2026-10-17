from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from seeding import seed_meeting

from asr_en_vi import routes
from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.tasks import claim_next_task, transcription_state
from asr_en_vi.worker import acquire_worker_lock, write_heartbeat

pytestmark = pytest.mark.anyio


def _prepared_model(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "model.bin").write_bytes(b"model")
    (path / "config.json").write_text(
        json.dumps({"lang_ids": [], "suppress_ids": [], "suppress_ids_begin": []}),
        encoding="utf-8",
    )
    (path / "tokenizer.json").write_text(json.dumps({"model": {"type": "BPE"}}), encoding="utf-8")
    (path / "preprocessor_config.json").write_text(
        json.dumps(
            {
                "feature_size": 128,
                "sampling_rate": 16000,
                "hop_length": 160,
                "n_fft": 400,
                "chunk_length": 30,
            }
        ),
        encoding="utf-8",
    )
    return path


async def _authorize(client: AsyncClient, settings: Settings) -> dict[str, str]:
    token = AuthStore(settings.auth_dir).load().token
    headers = {"Origin": settings.public_url}
    response = await client.post("/api/access/session", headers=headers, json={"token": token})
    assert response.status_code == 204
    return headers


async def _run_inline(function, *args, **kwargs):
    return function(*args, **kwargs)


async def test_task_routes_accept_poll_cancel_and_rediscover_meeting_state(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "run_in_threadpool", _run_inline)
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
        asr_model_path=_prepared_model(tmp_path / "model"),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=settings.public_url) as client:
            headers = await _authorize(client, settings)
            meeting_id = seed_meeting(settings.data_dir, "Task routes")
            lock_fd = acquire_worker_lock(settings.data_dir)
            assert lock_fd is not None
            write_heartbeat(settings.data_dir, "idle")
            try:
                payload = {"meeting_id": meeting_id, "request_id": "api-request-001"}
                accepted = await client.post("/api/tasks", headers=headers, json=payload)
                retry = await client.post("/api/tasks", headers=headers, json=payload)
                assert accepted.status_code == 202
                assert retry.status_code == 202
                assert retry.json()["id"] == accepted.json()["id"]
                assert accepted.json()["request_id"] == payload["request_id"]
                assert accepted.json()["worker_state"] == "checking-worker"

                detail = (await client.get(f"/api/meetings/{meeting_id}")).json()
                assert detail["transcription"]["task"]["id"] == accepted.json()["id"]
                assert detail["transcription"]["generation"] is None

                claimed = claim_next_task(settings.data_dir, owner_id="api-test-worker")
                assert claimed and claimed["id"] == accepted.json()["id"]
                running = await client.get(f"/api/tasks/{accepted.json()['id']}")
                assert running.json()["status"] == "running"
                assert running.json()["worker_state"] == "healthy"
                stopping = await client.post(
                    f"/api/tasks/{accepted.json()['id']}/cancel", headers=headers, json={}
                )
                assert stopping.json()["status"] == "stopping"
                assert (
                    transcription_state(settings.data_dir, meeting_id)["task"]["status"]
                    == "stopping"
                )
            finally:
                os.close(lock_fd)


async def test_task_api_rejects_missing_worker_model_and_invalid_request(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "run_in_threadpool", _run_inline)
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
        asr_model_path=tmp_path / "missing-model",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=settings.public_url) as client:
            headers = await _authorize(client, settings)
            meeting_id = seed_meeting(settings.data_dir, "No model")
            unavailable_worker = await client.post(
                "/api/tasks",
                headers=headers,
                json={"meeting_id": meeting_id, "request_id": "missing-worker"},
            )
            assert unavailable_worker.status_code == 503
            assert unavailable_worker.json()["detail"]["code"] == "worker_unavailable"

            lock_fd = acquire_worker_lock(settings.data_dir)
            assert lock_fd is not None
            write_heartbeat(settings.data_dir, "idle")
            try:
                unavailable_model = await client.post(
                    "/api/tasks",
                    headers=headers,
                    json={"meeting_id": meeting_id, "request_id": "missing-model"},
                )
                invalid_request = await client.post(
                    "/api/tasks",
                    headers=headers,
                    json={"meeting_id": meeting_id, "request_id": "bad"},
                )
                assert unavailable_model.status_code == 503
                assert unavailable_model.json()["detail"]["code"] == "model_unavailable"
                assert invalid_request.status_code == 400
                assert invalid_request.json()["detail"]["code"] == "invalid_request_id"
            finally:
                os.close(lock_fd)
