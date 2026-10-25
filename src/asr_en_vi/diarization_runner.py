"""Local-only Community-1 child process and its newline-delimited JSON protocol."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
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
DIARIZATION_ERROR_MESSAGES = {
    "diarization_decoder_unavailable": (
        "The local audio decoder is unavailable. "
        "Check the application's audio runtime dependencies."
    ),
    "diarization_model_load_failed": (
        "The local Community-1 model could not be loaded. "
        "Check that the gated model assets are complete and readable."
    ),
    "diarization_cuda_failed": (
        "Community-1 could not run on the selected CUDA device. "
        "Check the CUDA runtime or select CPU."
    ),
    "diarization_input_decode_failed": (
        "The meeting recording could not be decoded. Re-upload a valid audio file and retry."
    ),
    "diarization_failed": "Local diarization failed. Check the worker logs and try again.",
}
_SAFE_CONTEXT_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


class DiarizationConfigurationError(RuntimeError):
    """The configured local Community-1 directory is missing or incomplete."""


class DiarizationPhaseError(RuntimeError):
    """A failure at a known diarization phase with a stable, safe code."""

    def __init__(self, code: str, stage: str) -> None:
        if code not in DIARIZATION_ERROR_MESSAGES:
            code = "diarization_failed"
        self.code = code
        self.stage = stage
        super().__init__(DIARIZATION_ERROR_MESSAGES[code])


def safe_diarization_error(code: object, message: object) -> tuple[str, str]:
    """Return a child error only when its code and exact message are allowlisted."""
    if isinstance(code, str) and isinstance(message, str):
        expected_message = DIARIZATION_ERROR_MESSAGES.get(code)
        if expected_message is not None and message == expected_message:
            return code, expected_message
    fallback_code = "diarization_failed"
    return fallback_code, DIARIZATION_ERROR_MESSAGES[fallback_code]


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


def _set_offline_environment() -> None:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "PYANNOTE_METRICS_ENABLED": "0",
            "DO_NOT_TRACK": "1",
            "ORT_DISABLE_TELEMETRY": "1",
        }
    )
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HF_API_TOKEN"):
        os.environ.pop(name, None)


def load_audio_decoder():
    """Load torchcodec's decoder without exposing native loader errors to users."""
    try:
        from torchcodec.decoders import AudioDecoder
    except (ImportError, OSError, RuntimeError) as error:
        raise DiarizationPhaseError(
            "diarization_decoder_unavailable", "loading_audio_decoder"
        ) from error
    return AudioDecoder


def _load_community_pipeline(model_path: Path, device: str):
    try:
        resolved_model = prepared_diarization_directory(model_path)
        import torch
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained(str(resolved_model), token=False)
        if pipeline is None:
            raise RuntimeError("Community-1 did not return a pipeline")
    except Exception as error:
        raise DiarizationPhaseError(
            "diarization_model_load_failed", "loading_diarization_model"
        ) from error

    selected_device = "cuda" if device == "cuda" else "cpu"
    stage = (
        "moving_diarization_model_to_cuda"
        if selected_device == "cuda"
        else "moving_diarization_model_to_cpu"
    )
    try:
        pipeline.to(torch.device(selected_device))
    except Exception as error:
        code = (
            "diarization_cuda_failed"
            if selected_device == "cuda"
            else "diarization_model_load_failed"
        )
        raise DiarizationPhaseError(code, stage) from error
    return pipeline, selected_device


def preflight_diarization_model(*, model_path: Path, device: str) -> None:
    """Load local Community-1 offline and move it to the selected device."""
    _set_offline_environment()
    load_audio_decoder()
    _load_community_pipeline(model_path, device)


def _validate_audio_decode(audio_path: Path, decoder_type) -> None:
    """Decode a bounded prefix so long meetings are not copied into worker memory."""
    try:
        samples = decoder_type(str(audio_path)).get_samples_played_in_range(
            start_seconds=0.0,
            stop_seconds=1.0,
        )
        waveform = samples.data
        sample_rate = samples.sample_rate
        if (
            waveform is None
            or waveform.numel() < 1
            or isinstance(sample_rate, bool)
            or not isinstance(sample_rate, int)
            or sample_rate < 1
        ):
            raise ValueError("Audio decoder returned invalid samples")
    except Exception as error:
        raise DiarizationPhaseError("diarization_input_decode_failed", "decoding_input") from error


def diarize_file(
    *,
    model_path: Path,
    audio_path: Path,
    device: str,
    emit: Callable[[dict[str, Any]], None] = _emit,
) -> None:
    """Load one prepared local model, emit its turns, and release it when this process exits."""
    stage = "loading_audio_decoder"
    try:
        _set_offline_environment()
        emit({"type": "stage", "stage": "loading_diarization_model"})
        decoder_type = load_audio_decoder()
        pipeline, _ = _load_community_pipeline(model_path, device)

        stage = "decoding_input"
        try:
            resolved_audio = Path(audio_path).resolve(strict=True)
            if not resolved_audio.is_file():
                raise FileNotFoundError("The recording is unavailable")
        except OSError as error:
            raise DiarizationPhaseError("diarization_input_decode_failed", stage) from error
        emit({"type": "stage", "stage": "decoding_input"})
        _validate_audio_decode(resolved_audio, decoder_type)

        emit({"type": "stage", "stage": "diarizing"})
        stage = "diarizing"
        try:
            output = pipeline(str(resolved_audio))
        except Exception as error:
            raise DiarizationPhaseError("diarization_failed", stage) from error
    except DiarizationPhaseError:
        raise
    except Exception as error:
        raise DiarizationPhaseError("diarization_failed", stage) from error

    try:
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
    except Exception as error:
        raise DiarizationPhaseError("diarization_failed", "collecting_result") from error


def _safe_context_id(value: str) -> str:
    return value if _SAFE_CONTEXT_ID.fullmatch(value) else "unknown"


def _write_error_context(*, diagnostic_id: str, meeting_id: str, stage: str, code: str) -> None:
    context = {
        "event": "diarization_error",
        "diagnostic_id": _safe_context_id(diagnostic_id),
        "task_id": _safe_context_id(diagnostic_id),
        "meeting_id": _safe_context_id(meeting_id),
        "stage": stage,
        "code": code,
    }
    sys.stderr.write(json.dumps(context, separators=(",", ":")) + "\n")
    sys.stderr.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asr-en-vi-diarization-runner")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--device", required=True, choices=("cpu", "cuda", "auto"))
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--diagnostic-id", default="unknown")
    parser.add_argument("--meeting-id", default="unknown")
    args = parser.parse_args(argv)
    try:
        if args.check_runtime:
            preflight_diarization_model(model_path=args.model, device=args.device)
        else:
            if args.audio is None:
                parser.error("--audio is required unless --check-runtime is used")
            diarize_file(
                model_path=args.model,
                audio_path=args.audio,
                device=args.device,
            )
    except DiarizationPhaseError as error:
        traceback.print_exc(file=sys.stderr)
        code, message = safe_diarization_error(error.code, error.args[0])
        _write_error_context(
            diagnostic_id=args.diagnostic_id,
            meeting_id=args.meeting_id,
            stage=error.stage,
            code=code,
        )
        _emit({"type": "error", "code": code, "message": message})
        return 1
    except Exception:
        traceback.print_exc(file=sys.stderr)
        code, message = safe_diarization_error(None, None)
        _write_error_context(
            diagnostic_id=args.diagnostic_id,
            meeting_id=args.meeting_id,
            stage="unknown",
            code=code,
        )
        _emit({"type": "error", "code": code, "message": message})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
