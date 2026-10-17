"""Local-only faster-whisper child process and its newline-delimited JSON protocol."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

_REQUIRED_MODEL_FILES = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "preprocessor_config.json",
)


class ModelConfigurationError(RuntimeError):
    """The configured local model path is missing or is not a converted Whisper model."""


def prepared_model_directory(path: Path) -> Path:
    model_path = Path(path).expanduser()
    try:
        resolved = model_path.resolve(strict=True)
    except OSError as error:
        raise ModelConfigurationError("The local model directory is unavailable.") from error
    if not resolved.is_dir():
        raise ModelConfigurationError("The local model path must be a directory.")
    if any(not (resolved / filename).is_file() for filename in _REQUIRED_MODEL_FILES):
        raise ModelConfigurationError("The local model directory is incomplete.")
    try:
        tokenizer_config = json.loads((resolved / "tokenizer.json").read_text(encoding="utf-8"))
        model_config = json.loads((resolved / "config.json").read_text(encoding="utf-8"))
        preprocessor_config = json.loads(
            (resolved / "preprocessor_config.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelConfigurationError("The local model configuration is invalid.") from error
    if not isinstance(tokenizer_config, dict) or not isinstance(
        tokenizer_config.get("model"), dict
    ):
        raise ModelConfigurationError("The local model tokenizer is invalid.")
    if not isinstance(model_config, dict) or any(
        key not in model_config for key in ("lang_ids", "suppress_ids", "suppress_ids_begin")
    ):
        raise ModelConfigurationError("The local model configuration is incomplete.")
    if not isinstance(preprocessor_config, dict):
        raise ModelConfigurationError("The local model preprocessor configuration is invalid.")
    for key in ("feature_size", "sampling_rate", "hop_length", "n_fft", "chunk_length"):
        value = preprocessor_config.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ModelConfigurationError(
                "The local model preprocessor configuration is incomplete."
            )
    if preprocessor_config["sampling_rate"] != 16000:
        raise ModelConfigurationError("The local model must use a 16 kHz preprocessor.")
    return resolved


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _finite_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return normalized if math.isfinite(normalized) else None


def transcribe_file(
    *,
    model_path: Path,
    audio_path: Path,
    language: str,
    device: str,
    compute_type: str,
    emit: Callable[[dict[str, Any]], None] = _emit,
) -> None:
    """Load one prepared local model, transcribe one local file and emit measured results."""
    resolved_model = prepared_model_directory(model_path)
    resolved_audio = Path(audio_path).resolve(strict=True)
    if not resolved_audio.is_file():
        raise FileNotFoundError("The recording is unavailable.")
    if language not in {"en", "vi"}:
        raise ValueError("The transcription language must be en or vi.")

    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    from faster_whisper import WhisperModel

    _emit_with = emit
    _emit_with({"type": "stage", "stage": "loading_model"})
    model = WhisperModel(
        str(resolved_model),
        device=device,
        compute_type=compute_type,
        local_files_only=True,
    )
    _emit_with({"type": "stage", "stage": "transcribing"})
    segments, info = model.transcribe(
        str(resolved_audio),
        language=language,
        beam_size=5,
        vad_filter=False,
    )
    segment_count = 0
    for segment in segments:
        segment_count += 1
        _emit_with(
            {
                "type": "segment",
                "id": uuid.uuid4().hex,
                "start_seconds": _finite_or_none(segment.start),
                "end_seconds": _finite_or_none(segment.end),
                "text": str(segment.text),
                "avg_logprob": _finite_or_none(segment.avg_logprob),
                "no_speech_prob": _finite_or_none(segment.no_speech_prob),
                "compression_ratio": _finite_or_none(segment.compression_ratio),
            }
        )
    _emit_with(
        {
            "type": "complete",
            "segment_count": segment_count,
            "language_probability": _finite_or_none(info.language_probability),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-runner")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--language", required=True, choices=("en", "vi"))
    parser.add_argument("--device", required=True, choices=("cpu", "cuda", "auto"))
    parser.add_argument("--compute-type", required=True)
    args = parser.parse_args()
    try:
        transcribe_file(
            model_path=args.model,
            audio_path=args.audio,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
        )
    except ModelConfigurationError:
        _emit(
            {
                "type": "error",
                "code": "model_unavailable",
                "message": "The local ASR model is unavailable.",
            }
        )
        return 2
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _emit(
            {
                "type": "error",
                "code": "transcription_failed",
                "message": "Local transcription failed. Check the worker logs and try again.",
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
