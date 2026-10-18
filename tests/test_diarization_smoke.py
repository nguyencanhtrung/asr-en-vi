from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest

from asr_en_vi.config import Settings
from asr_en_vi.diarization_runner import (
    DiarizationConfigurationError,
    diarize_file,
    prepared_diarization_directory,
)


def test_local_community1_real_audio_smoke():
    """Exercise the gated model only with explicit opt-in and local assets."""
    if os.environ.get("ASR_RUN_DIARIZATION_SMOKE") != "1":
        pytest.skip("set ASR_RUN_DIARIZATION_SMOKE=1 to opt in to the local model smoke")

    settings = Settings.from_env()
    try:
        model_path = prepared_diarization_directory(settings.diarization_model_path)
    except DiarizationConfigurationError:
        pytest.skip("local gated Community-1 model assets are not available")

    audio_value = os.environ.get("ASR_DIARIZATION_SMOKE_AUDIO")
    if not audio_value:
        pytest.skip("set ASR_DIARIZATION_SMOKE_AUDIO to a local 5-10 second WAV file")
    audio_path = Path(audio_value).expanduser().resolve(strict=True)
    with wave.open(str(audio_path), "rb") as recording:
        duration_seconds = recording.getnframes() / recording.getframerate()
    if not 5 <= duration_seconds <= 10:
        pytest.fail("ASR_DIARIZATION_SMOKE_AUDIO must contain 5 to 10 seconds of audio")

    device = os.environ.get("ASR_DIARIZATION_SMOKE_DEVICE", settings.asr_device)
    if device == "auto":
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device not in {"cpu", "cuda"}:
        pytest.fail("ASR_DIARIZATION_SMOKE_DEVICE must be cpu or cuda")

    events: list[dict[str, object]] = []
    diarize_file(
        model_path=model_path,
        audio_path=audio_path,
        device=device,
        emit=events.append,
    )

    complete = next((event for event in events if event.get("type") == "complete"), None)
    assert complete is not None
    assert isinstance(complete.get("regular_turn_count"), int)
    assert isinstance(complete.get("exclusive_turn_count"), int)
