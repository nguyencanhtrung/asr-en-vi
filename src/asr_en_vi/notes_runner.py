"""Isolated notes worker child for the pinned provider; stdout carries bounded JSON events only."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from asr_en_vi.antigravity import AntigravityError, AntigravityProvider
from asr_en_vi.chatgpt import ChatGPTError, ChatGPTProvider
from asr_en_vi.notes import load_notes_task_input
from asr_en_vi.notes_document import (
    LEGACY_ENGLISH_PROMPT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    NotesDocumentError,
    build_citations,
    render_markdown,
)
from asr_en_vi.safe_logging import emit_safe_log
from asr_en_vi.tasks import TaskError

_PROVIDER_LABELS = {"chatgpt": "ChatGPT", "antigravity": "Google Antigravity"}


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)


def _emit_progress(event: dict[str, Any]) -> None:
    """Forward only bounded notes-stage measurements from the provider-neutral pipeline."""
    allowed_stages = {
        "preparing_source",
        "generating",
        "chunking",
        "merging",
        "repairing",
        "rendering",
    }
    allowed_units = {"phase", "calls", "chunks", "repairs", "recoveries"}
    stage = event.get("stage")
    current = event.get("current")
    total = event.get("total")
    unit = event.get("unit")
    if (
        not isinstance(stage, str)
        or stage not in allowed_stages
        or isinstance(current, bool)
        or not isinstance(current, int)
        or current < 0
        or (
            total is not None
            and (isinstance(total, bool) or not isinstance(total, int) or total < current)
        )
        or not isinstance(unit, str)
        or unit not in allowed_units
    ):
        raise ValueError("invalid notes progress event")
    payload = {"type": "progress", "stage": stage, "current": current, "total": total, "unit": unit}
    _emit(payload)


def run_notes_task(data_dir: Path, task_id: str, owner_id: str) -> int:
    provider_label = "The notes provider"
    stage = "starting_notes"
    try:
        task, snapshot = load_notes_task_input(data_dir, task_id, owner_id=owner_id)
        provider_label = _PROVIDER_LABELS.get(task["notes_provider"], provider_label)
        legacy_english_task = (
            task["notes_prompt_version"] == LEGACY_ENGLISH_PROMPT_VERSION
            and task["notes_output_language"] == "en"
        )
        if (task["notes_prompt_version"] != PROMPT_VERSION and not legacy_english_task) or task[
            "notes_schema_version"
        ] != SCHEMA_VERSION:
            _emit(
                {
                    "type": "error",
                    "code": "notes_contract_changed",
                    "message": "The notes contract changed before the task started.",
                }
            )
            return 1
        provider_dir = os.environ.get("ASR_PROVIDER_DIR")
        if not provider_dir:
            _emit(
                {
                    "type": "error",
                    "code": "provider_storage_unavailable",
                    "message": f"{provider_label} connection storage is unavailable.",
                }
            )
            return 1
        provider: ChatGPTProvider | AntigravityProvider
        if task["notes_provider"] == "chatgpt":
            provider = ChatGPTProvider(Path(provider_dir), callback_url="")
        elif task["notes_provider"] == "antigravity":
            provider = AntigravityProvider(Path(provider_dir))
        else:
            _emit(
                {
                    "type": "error",
                    "code": "notes_provider_unsupported",
                    "message": "The notes provider saved with this task is not supported.",
                }
            )
            return 1
        stage = "generating_notes"
        _emit({"type": "stage", "stage": stage})
        coverage: dict[str, Any] = {}
        document = provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=task["notes_connection_version"],
            model=task["notes_model"],
            reasoning_effort=task["notes_reasoning_effort"],
            output_language=task["notes_output_language"],
            on_coverage=coverage.update,
            on_progress=_emit_progress,
        )
        _emit_progress({"stage": "rendering", "current": 0, "total": 1, "unit": "phase"})
        markdown = render_markdown(
            document, snapshot, output_language=task["notes_output_language"]
        )
        citations = build_citations(
            document, snapshot, output_language=task["notes_output_language"]
        )
        _emit_progress({"stage": "rendering", "current": 1, "total": 1, "unit": "phase"})
        _emit(
            {"type": "result", "markdown": markdown, "coverage": coverage, "citations": citations}
        )
        return 0
    except (ChatGPTError, AntigravityError) as error:
        _emit({"type": "error", "code": error.code, "message": error.public_message})
        return 1
    except TaskError as error:
        _emit({"type": "error", "code": error.code, "message": error.message})
        return 1
    except NotesDocumentError:
        _emit(
            {
                "type": "error",
                "code": "notes_invalid_output",
                "message": (
                    f"{provider_label} returned notes that did not match the saved transcript."
                ),
            }
        )
        return 1
    except Exception:
        # Do not log exception text because it can contain prompt or provider data.
        emit_safe_log(event="notes_error", stage=stage, code="notes_failed")
        _emit(
            {
                "type": "error",
                "code": "notes_failed",
                "message": "Notes generation failed. Check the worker logs.",
            }
        )
        return 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(prog="asr-en-vi-notes-runner")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--owner-id", required=True)
    arguments = parser.parse_args()
    return run_notes_task(arguments.data_dir, arguments.task_id, arguments.owner_id)


if __name__ == "__main__":
    raise SystemExit(main())
