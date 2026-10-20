"""Authenticated notes API and assets owned by the notes integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from asr_en_vi.chatgpt import ChatGPTError, ChatGPTProvider
from asr_en_vi.config import Settings
from asr_en_vi.notes import (
    accept_notes_task,
    export_note,
    get_note,
    get_notes_source,
    notes_state,
    update_note,
)
from asr_en_vi.tasks import TaskError
from asr_en_vi.worker import is_healthy as worker_is_healthy

WEB_DIR = Path(__file__).parent / "web"


async def _json_object(
    request: Request, *, required: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    try:
        payload = await request.json()
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_json", "message": "Provide a valid JSON object."},
        ) from None
    allowed = required | (optional or set())
    if not isinstance(payload, dict) or not required <= set(payload) or not set(payload) <= allowed:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request", "message": "The JSON fields are invalid."},
        )
    return payload


def _raise_task_error(error: TaskError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    ) from None


def _raise_provider_error(error: ChatGPTError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.public_message},
    ) from None


def install_notes_routes(
    app: FastAPI, settings: Settings, chatgpt_provider: ChatGPTProvider
) -> None:
    @app.get("/assets/notes.js", include_in_schema=False)
    async def notes_js() -> FileResponse:
        return FileResponse(WEB_DIR / "notes.js", media_type="text/javascript")

    @app.get("/assets/notes.css", include_in_schema=False)
    async def notes_css() -> FileResponse:
        return FileResponse(WEB_DIR / "notes.css", media_type="text/css")

    @app.post("/api/meetings/{meeting_id}/notes-runs", status_code=202)
    async def start_notes_run(meeting_id: str, request: Request) -> dict[str, object]:
        payload = await _json_object(
            request,
            required={
                "request_id",
                "expected_generation_id",
                "expected_source_version",
                "expected_metadata_version",
            },
            optional={"output_language"},
        )
        worker_ready = worker_is_healthy(settings.data_dir)
        try:
            result = await run_in_threadpool(
                accept_notes_task,
                settings.data_dir,
                provider=chatgpt_provider,
                meeting_id=meeting_id,
                request_id=payload["request_id"],
                expected_generation_id=payload["expected_generation_id"],
                expected_source_version=payload["expected_source_version"],
                expected_metadata_version=payload["expected_metadata_version"],
                output_language=payload.get("output_language", "en"),
                worker_ready=worker_ready,
            )
            return result
        except TaskError as error:
            _raise_task_error(error)
        except ChatGPTError as error:
            _raise_provider_error(error)

    @app.get("/api/meetings/{meeting_id}/notes")
    async def read_meeting_notes(meeting_id: str) -> dict[str, object]:
        try:
            return await run_in_threadpool(notes_state, settings.data_dir, meeting_id)
        except TaskError as error:
            _raise_task_error(error)

    @app.get("/api/notes/{note_id}")
    async def read_note(note_id: str) -> dict[str, object]:
        try:
            return await run_in_threadpool(get_note, settings.data_dir, note_id)
        except TaskError as error:
            _raise_task_error(error)

    @app.patch("/api/notes/{note_id}")
    async def edit_note(note_id: str, request: Request) -> dict[str, object]:
        payload = await _json_object(request, required={"expected_edit_version", "markdown"})
        try:
            return await run_in_threadpool(
                update_note,
                settings.data_dir,
                note_id,
                expected_edit_version=payload["expected_edit_version"],
                markdown=payload["markdown"],
            )
        except TaskError as error:
            _raise_task_error(error)

    @app.get("/api/notes/{note_id}/export")
    async def export_saved_note(note_id: str) -> Response:
        try:
            markdown = await run_in_threadpool(export_note, settings.data_dir, note_id)
        except TaskError as error:
            _raise_task_error(error)
        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="meeting-notes.md"'},
        )

    @app.get("/api/notes-sources/{source_id}")
    async def read_notes_source(source_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(get_notes_source, settings.data_dir, source_id)
        except TaskError as error:
            _raise_task_error(error)
