"""Isolated ChatGPT notes worker child; stdout carries bounded JSON events only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from asr_en_vi.chatgpt import ChatGPTError, ChatGPTProvider
from asr_en_vi.notes import load_notes_task_input
from asr_en_vi.notes_document import (
    LEGACY_ENGLISH_PROMPT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    NotesDocumentError,
    render_markdown,
)
from asr_en_vi.tasks import TaskError


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)


def run_notes_task(data_dir: Path, task_id: str, owner_id: str) -> int:
    try:
        task, snapshot = load_notes_task_input(data_dir, task_id, owner_id=owner_id)
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
                    "message": "ChatGPT connection storage is unavailable.",
                }
            )
            return 1
        _emit({"type": "stage", "stage": "generating_notes"})
        provider = ChatGPTProvider(Path(provider_dir), callback_url="")
        document = provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=task["notes_connection_version"],
            model=task["notes_model"],
            reasoning_effort=task["notes_reasoning_effort"],
            output_language=task["notes_output_language"],
        )
        markdown = render_markdown(
            document, snapshot, output_language=task["notes_output_language"]
        )
        _emit({"type": "result", "markdown": markdown})
        return 0
    except ChatGPTError as error:
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
                "message": "ChatGPT returned notes that did not match the saved transcript.",
            }
        )
        return 1
    except Exception:
        # Do not log exception text because it can contain prompt or provider data.
        print(
            json.dumps(
                {"event": "notes_error", "task_id": task_id, "code": "notes_failed"},
                separators=(",", ":"),
            ),
            file=sys.stderr,
            flush=True,
        )
        _emit(
            {
                "type": "error",
                "code": "notes_failed",
                "message": "Notes generation failed. Check the worker logs.",
            }
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-notes-runner")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--owner-id", required=True)
    arguments = parser.parse_args()
    return run_notes_task(arguments.data_dir, arguments.task_id, arguments.owner_id)


if __name__ == "__main__":
    raise SystemExit(main())
