"""Local-only Community-1 child process and its newline-delimited JSON protocol."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

COMMUNITY_1_REQUIRED_FILES = (
    Path("config.yaml"),
    Path("embedding/pytorch_model.bin"),
    Path("plda/plda.npz"),
    Path("plda/xvec_transform.npz"),
    Path("segmentation/pytorch_model.bin"),
)
_GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


class DiarizationConfigurationError(RuntimeError):
    """The configured local Community-1 directory is missing or incomplete."""


def prepared_diarization_directory(path: Path) -> Path:
    model_path = Path(path).expanduser()
    try:
        resolved = model_path.resolve(strict=True)
    except OSError as error:
        raise DiarizationConfigurationError(
            "The local Community-1 model directory is unavailable."
        ) from error
    if not resolved.is_dir():
        raise DiarizationConfigurationError("The local Community-1 model directory is incomplete.")
    for relative_path in COMMUNITY_1_REQUIRED_FILES:
        try:
            candidate = (resolved / relative_path).resolve(strict=True)
            candidate.relative_to(resolved)
            if not candidate.is_file():
                raise OSError
            with candidate.open("rb") as model_file:
                is_lfs_pointer = model_file.read(len(_GIT_LFS_POINTER_PREFIX)).startswith(
                    _GIT_LFS_POINTER_PREFIX
                )
        except (OSError, ValueError):
            raise DiarizationConfigurationError(
                f"The local Community-1 model is missing {relative_path.as_posix()}."
            ) from None
        if is_lfs_pointer:
            raise DiarizationConfigurationError(
                f"The local Community-1 file {relative_path.as_posix()} is still a Git LFS pointer."
            )
    return resolved


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _finite(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return normalized if math.isfinite(normalized) else None


def diarize_file(
    *,
    model_path: Path,
    audio_path: Path,
    device: str,
    emit: Callable[[dict[str, Any]], None] = _emit,
) -> None:
    """Load one prepared local model, emit its turns, and release it when this process exits."""
    resolved_model = prepared_diarization_directory(model_path)
    resolved_audio = Path(audio_path).resolve(strict=True)
    if not resolved_audio.is_file():
        raise FileNotFoundError("The recording is unavailable.")

    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "PYANNOTE_METRICS_ENABLED": "0",
            "DO_NOT_TRACK": "1",
        }
    )
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HF_API_TOKEN"):
        os.environ.pop(name, None)
    import torch
    from pyannote.audio import Pipeline

    emit({"type": "stage", "stage": "loading_diarization_model"})
    pipeline = Pipeline.from_pretrained(str(resolved_model), token=False)
    if pipeline is None:
        raise RuntimeError("The prepared Community-1 pipeline could not be loaded.")
    selected_device = "cuda" if device == "cuda" else "cpu"
    pipeline.to(torch.device(selected_device))

    emit({"type": "stage", "stage": "diarizing"})
    output = pipeline(str(resolved_audio))
    annotations = (
        ("regular", output.speaker_diarization),
        ("exclusive", output.exclusive_speaker_diarization),
    )
    counts: dict[str, int] = {}
    for kind, annotation in annotations:
        count = 0
        for turn, _, speaker_label in annotation.itertracks(yield_label=True):
            start_seconds = _finite(turn.start)
            end_seconds = _finite(turn.end)
            if start_seconds is None or end_seconds is None or end_seconds <= start_seconds:
                raise RuntimeError("Community-1 returned an invalid speaker turn.")
            count += 1
            emit(
                {
                    "type": "turn",
                    "kind": kind,
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "speaker_id": str(speaker_label),
                }
            )
        counts[kind] = count
    emit(
        {
            "type": "complete",
            "regular_turn_count": counts["regular"],
            "exclusive_turn_count": counts["exclusive"],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-diarization-runner")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--device", required=True, choices=("cpu", "cuda", "auto"))
    args = parser.parse_args()
    try:
        diarize_file(
            model_path=args.model,
            audio_path=args.audio,
            device=args.device,
        )
    except DiarizationConfigurationError:
        _emit(
            {
                "type": "error",
                "code": "diarization_model_unavailable",
                "message": "The local Community-1 model is unavailable.",
            }
        )
        return 2
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _emit(
            {
                "type": "error",
                "code": "diarization_failed",
                "message": "Local diarization failed. Check the worker logs and try again.",
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
