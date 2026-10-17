from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from seeding import prepare_diarization_model

from asr_en_vi.diarization_runner import (
    DiarizationConfigurationError,
    diarize_file,
    prepared_diarization_directory,
)


def _prepared_model(path: Path) -> Path:
    return prepare_diarization_model(path)


def test_runner_requires_a_prepared_local_community_directory(tmp_path):
    with pytest.raises(DiarizationConfigurationError):
        prepared_diarization_directory(tmp_path / "community-1")

    model = _prepared_model(tmp_path / "prepared")
    assert prepared_diarization_directory(model) == model.resolve()

    (model / "embedding/pytorch_model.bin").write_text(
        "version https://git-lfs.github.com/spec/v1\n", encoding="ascii"
    )
    with pytest.raises(DiarizationConfigurationError, match="Git LFS pointer"):
        prepared_diarization_directory(model)


def test_runner_loads_local_pipeline_with_telemetry_and_network_disabled(tmp_path, monkeypatch):
    model_dir = _prepared_model(tmp_path / "model")
    audio_path = tmp_path / "recording.m4a"
    audio_path.write_bytes(b"local audio")
    observed = {}

    class Annotation:
        def itertracks(self, *, yield_label):
            assert yield_label is True
            return iter([(SimpleNamespace(start=1.25, end=2.75), "track", "SPEAKER_00")])

    class FakePipeline:
        def to(self, device):
            observed["device"] = device
            return self

        def __call__(self, source):
            observed["audio_path"] = source
            return SimpleNamespace(
                speaker_diarization=Annotation(),
                exclusive_speaker_diarization=Annotation(),
            )

    class FakePipelineType:
        @staticmethod
        def from_pretrained(source, *, token):
            observed["model_path"] = source
            observed["token"] = token
            return FakePipeline()

    pyannote_package = ModuleType("pyannote")
    pyannote_package.__path__ = []
    pyannote_audio = ModuleType("pyannote.audio")
    pyannote_audio.Pipeline = FakePipelineType
    torch = ModuleType("torch")
    torch.device = lambda name: f"device:{name}"
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_package)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setenv("HF_TOKEN", "setup-only-token")
    events = []

    diarize_file(
        model_path=model_dir,
        audio_path=audio_path,
        device="cuda",
        emit=events.append,
    )

    assert observed == {
        "model_path": str(model_dir.resolve()),
        "token": False,
        "device": "device:cuda",
        "audio_path": str(audio_path.resolve()),
    }
    assert events[0] == {"type": "stage", "stage": "loading_diarization_model"}
    assert events[1] == {"type": "stage", "stage": "diarizing"}
    assert events[2] == {
        "type": "turn",
        "kind": "regular",
        "start_seconds": 1.25,
        "end_seconds": 2.75,
        "speaker_id": "SPEAKER_00",
    }
    assert events[3]["kind"] == "exclusive"
    assert events[4] == {
        "type": "complete",
        "regular_turn_count": 1,
        "exclusive_turn_count": 1,
    }
    assert "HF_TOKEN" not in os.environ
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["PYANNOTE_METRICS_ENABLED"] == "0"
