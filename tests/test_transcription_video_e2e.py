from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.runner import ModelConfigurationError, prepared_model_directory
from asr_en_vi.worker import is_healthy

# This opt-in proof has its own ASR_TEST_TIMEOUT_SECONDS deadline (default: 1 hour).
pytestmark = [pytest.mark.anyio, pytest.mark.slow, pytest.mark.timeout(0)]


async def _file_chunks(path: Path):
    with path.open("rb") as source:
        while chunk := await asyncio.to_thread(source.read, 1024 * 1024):
            yield chunk


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_video_import_worker_transcription_and_saved_transcript(tmp_path):
    video_value = os.environ.get("ASR_TEST_VIDEO")
    model_value = os.environ.get("ASR_MODEL_PATH")
    if not video_value or not model_value:
        pytest.skip("Set ASR_TEST_VIDEO and ASR_MODEL_PATH to run the local video proof.")

    video_path = Path(video_value).expanduser().resolve(strict=True)
    if not video_path.is_file():
        pytest.fail("ASR_TEST_VIDEO must point to a readable video recording.")
    try:
        model_path = prepared_model_directory(Path(model_value))
    except ModelConfigurationError as error:
        pytest.fail(f"ASR_MODEL_PATH must name a prepared local model directory: {error}")

    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
        max_upload_bytes=max(video_path.stat().st_size, 1),
        asr_model_path=model_path,
        asr_device=os.environ.get("ASR_DEVICE", "cpu"),
        asr_compute_type=os.environ.get("ASR_COMPUTE_TYPE", "int8"),
    )
    app = create_app(settings)
    worker_environment = os.environ.copy()
    worker_environment.update(
        {
            "ASR_DATA_DIR": str(settings.data_dir),
            "ASR_AUTH_DIR": str(settings.auth_dir),
            "ASR_MODEL_PATH": str(model_path),
            "ASR_DEVICE": settings.asr_device,
            "ASR_COMPUTE_TYPE": settings.asr_compute_type,
        }
    )

    async with app.router.lifespan_context(app):
        worker = subprocess.Popen(
            [sys.executable, "-m", "asr_en_vi.worker"],
            env=worker_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not is_healthy(settings.data_dir):
                if worker.poll() is not None:
                    pytest.fail("The transcription worker exited before becoming ready.")
                await asyncio.sleep(0.2)
            assert is_healthy(settings.data_dir), "The transcription worker did not become ready."

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url=settings.public_url) as client:
                state = AuthStore(settings.auth_dir).load()
                headers = {"Origin": settings.public_url}
                session = await client.post(
                    "/api/access/session", headers=headers, json={"token": state.token}
                )
                assert session.status_code == 204

                upload = await client.post(
                    "/api/uploads",
                    headers=headers,
                    json={"filename": video_path.name, "size_bytes": video_path.stat().st_size},
                )
                assert upload.status_code == 201
                upload_id = upload.json()["id"]
                transferred = await client.put(
                    f"/api/uploads/{upload_id}/content",
                    headers=headers,
                    content=_file_chunks(video_path),
                )
                assert transferred.status_code == 200
                completed_upload = await client.post(
                    f"/api/uploads/{upload_id}/complete", headers=headers, json={}
                )
                assert completed_upload.status_code == 200
                assert completed_upload.json()["status"] == "ready"

                created_meeting = await client.post(
                    "/api/meetings",
                    headers=headers,
                    json={
                        "upload_id": upload_id,
                        "title": f"Video proof: {video_path.stem}",
                        "language_hint": "en",
                    },
                )
                assert created_meeting.status_code == 201
                meeting_id = created_meeting.json()["id"]

                started = await client.post(
                    "/api/tasks",
                    headers=headers,
                    json={"meeting_id": meeting_id, "request_id": "video-proof-request-001"},
                )
                assert started.status_code == 202
                task_id = started.json()["id"]
                timeout = int(os.environ.get("ASR_TEST_TIMEOUT_SECONDS", "3600"))
                deadline = time.monotonic() + max(timeout, 1)
                task = started.json()
                while task["status"] in {"accepted", "running", "stopping"}:
                    if time.monotonic() >= deadline:
                        pytest.fail(f"Video transcription did not finish within {timeout} seconds.")
                    await asyncio.sleep(1)
                    response = await client.get(f"/api/tasks/{task_id}")
                    assert response.status_code == 200
                    task = response.json()

                assert task["status"] == "succeeded"
                assert task["result_scope"] == "transcript_only"
                meeting = (await client.get(f"/api/meetings/{meeting_id}")).json()
                generation = meeting["transcription"]["generation"]
                assert generation and generation["status"] == "complete"
                assert generation["segments"]
                expected_text = os.environ.get("ASR_EXPECTED_TEXT")
                if expected_text:
                    transcript = " ".join(
                        segment["text"].strip() for segment in generation["segments"]
                    )
                    assert " ".join(expected_text.casefold().split()) in " ".join(
                        transcript.casefold().split()
                    )
                ids = [segment["id"] for segment in generation["segments"]]
                assert len(ids) == len(set(ids))
                assert all(
                    segment["start_seconds"] <= segment["end_seconds"]
                    for segment in generation["segments"]
                )
                assert all("avg_logprob" in segment for segment in generation["segments"])
                assert all("no_speech_prob" in segment for segment in generation["segments"])
                assert all("compression_ratio" in segment for segment in generation["segments"])
        finally:
            if worker.poll() is None:
                worker.send_signal(signal.SIGTERM)
                try:
                    worker.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
