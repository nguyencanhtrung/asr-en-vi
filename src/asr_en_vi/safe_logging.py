"""Fixed-shape diagnostics for default runtime and worker logs."""

from __future__ import annotations

import json
import sys
from typing import TextIO

_SAFE_EVENTS = frozenset(
    {
        "child_stderr",
        "diarization_error",
        "notes_error",
        "publishing_error",
        "runner_error",
        "runtime_error",
        "startup_error",
        "transcription_error",
        "worker_error",
    }
)
_SAFE_STAGES = frozenset(
    {
        "child_process",
        "collecting_result",
        "decoding_input",
        "diarizing",
        "generating_notes",
        "loading_audio_decoder",
        "loading_diarization_model",
        "loading_model",
        "model_preparation",
        "publishing",
        "runtime_check",
        "selecting_runtime",
        "starting_diarization",
        "starting_notes",
        "starting_runner",
        "startup_model_validation",
        "transcribing",
        "unknown",
        "worker_startup",
    }
)
_SAFE_CODES = frozenset(
    {
        "child_stderr_suppressed",
        "diarization_cuda_failed",
        "diarization_decoder_unavailable",
        "diarization_failed",
        "diarization_input_decode_failed",
        "diarization_model_load_failed",
        "installation_failed",
        "internal_error",
        "model_unavailable",
        "notes_failed",
        "notes_publication_failed",
        "notes_runner_protocol_error",
        "notes_timeout",
        "publication_failed",
        "recording_unavailable",
        "runner_protocol_error",
        "runner_start_failed",
        "runtime_unavailable",
        "transcription_failed",
        "worker_already_running",
    }
)
_FALLBACK_EVENT = "runtime_error"
_FALLBACK_STAGE = "unknown"
_FALLBACK_CODE = "internal_error"


def emit_safe_log(
    *,
    event: str,
    stage: str,
    code: str,
    stream: TextIO | None = None,
) -> None:
    """Emit only allowlisted values; never interpolate exception or user data."""
    payload = {
        "event": event if event in _SAFE_EVENTS else _FALLBACK_EVENT,
        "stage": stage if stage in _SAFE_STAGES else _FALLBACK_STAGE,
        "code": code if code in _SAFE_CODES else _FALLBACK_CODE,
    }
    target = sys.stderr if stream is None else stream
    target.write(json.dumps(payload, separators=(",", ":")) + "\n")
    target.flush()
