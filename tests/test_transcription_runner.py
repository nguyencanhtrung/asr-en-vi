from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from asr_en_vi import runner
from asr_en_vi.runner import ModelConfigurationError, prepared_model_directory, transcribe_file


def _prepared_model(path: Path) -> Path:
    path.mkdir()
    (path / "model.bin").write_bytes(b"local model")
    (path / "config.json").write_text(
        json.dumps({"lang_ids": [], "suppress_ids": [], "suppress_ids_begin": []}),
        encoding="utf-8",
    )
    (path / "tokenizer.json").write_text(json.dumps({"model": {"type": "BPE"}}), encoding="utf-8")
    (path / "preprocessor_config.json").write_text(
        json.dumps(
            {
                "feature_size": 128,
                "sampling_rate": 16000,
                "hop_length": 160,
                "n_fft": 400,
                "chunk_length": 30,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_runner_requires_a_prepared_local_model_directory(tmp_path):
    with pytest.raises(ModelConfigurationError):
        prepared_model_directory(tmp_path / "hub-model-name")

    model = _prepared_model(tmp_path / "prepared")
    assert prepared_model_directory(model) == model.resolve()


def test_model_validation_rejects_vocabulary_fallback_and_bad_preprocessor(tmp_path):
    legacy_model = _prepared_model(tmp_path / "legacy")
    (legacy_model / "tokenizer.json").unlink()
    (legacy_model / "vocabulary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelConfigurationError):
        prepared_model_directory(legacy_model)

    malformed_model = _prepared_model(tmp_path / "malformed")
    (malformed_model / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelConfigurationError):
        prepared_model_directory(malformed_model)


def test_runner_reports_traceback_to_stderr_without_exposing_it_in_protocol(
    tmp_path, monkeypatch, capsys
):
    model_dir = _prepared_model(tmp_path / "model")
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"audio")

    def fail_transcription(**_kwargs):
        raise RuntimeError("diagnostic traceback sentinel")

    monkeypatch.setattr(runner, "transcribe_file", fail_transcription)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "asr-en-vi-runner",
            "--model",
            str(model_dir),
            "--audio",
            str(audio),
            "--device",
            "cpu",
            "--compute-type",
            "int8",
        ],
    )

    assert runner.main() == 1
    captured = capsys.readouterr()
    assert "Traceback (most recent call last)" in captured.err
    assert "diagnostic traceback sentinel" in captured.err
    assert '"code":"transcription_failed"' in captured.out
    assert "diagnostic traceback sentinel" not in captured.out


def test_runner_loads_local_only_and_emits_timestamps_and_uncertainty_measures(
    tmp_path, monkeypatch
):
    model_dir = _prepared_model(tmp_path / "model")
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"audio")
    observed: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, model_path, **kwargs):
            observed["model_path"] = model_path
            observed["kwargs"] = kwargs

        def transcribe(self, audio_path, **kwargs):
            observed["audio_path"] = audio_path
            observed["transcribe_kwargs"] = kwargs
            return iter(
                [
                    SimpleNamespace(
                        start=1.125,
                        end=2.75,
                        text=" Xin chào.",
                        avg_logprob=-0.45,
                        no_speech_prob=0.08,
                        compression_ratio=1.2,
                    )
                ]
            ), SimpleNamespace(language_probability=0.97)

    fake_package = ModuleType("faster_whisper")
    fake_package.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_package)
    events = []

    transcribe_file(
        model_path=model_dir,
        audio_path=audio,
        device="cpu",
        compute_type="int8",
        emit=events.append,
    )

    assert observed["model_path"] == str(model_dir.resolve())
    assert observed["kwargs"] == {
        "device": "cpu",
        "compute_type": "int8",
        "local_files_only": True,
    }
    assert observed["audio_path"] == str(audio.resolve())
    assert observed["transcribe_kwargs"] == {
        "language": None,
        "task": "transcribe",
        "multilingual": True,
        "beam_size": 5,
        "vad_filter": False,
    }
    assert events[0] == {"type": "stage", "stage": "loading_model"}
    assert events[1] == {"type": "stage", "stage": "transcribing"}
    segment = events[2]
    assert segment["type"] == "segment"
    assert len(segment["id"]) == 32
    assert segment["start_seconds"] == 1.125
    assert segment["end_seconds"] == 2.75
    assert segment["avg_logprob"] == -0.45
    assert segment["no_speech_prob"] == 0.08
    assert segment["compression_ratio"] == 1.2
    assert events[3] == {
        "type": "complete",
        "segment_count": 1,
        "language_probability": 0.97,
    }
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
