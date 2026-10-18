from __future__ import annotations

import builtins
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from seeding import prepare_diarization_model

from asr_en_vi import diarization_runner
from asr_en_vi.diarization_runner import (
    DIARIZATION_ERROR_MESSAGES,
    DiarizationConfigurationError,
    DiarizationPhaseError,
    diarize_file,
    main,
    preflight_diarization_model,
    prepared_diarization_directory,
    safe_diarization_error,
)


def _prepared_model(path: Path) -> Path:
    return prepare_diarization_model(path)


def _install_pipeline_modules(monkeypatch, pipeline):
    pyannote_package = ModuleType("pyannote")
    pyannote_package.__path__ = []
    pyannote_audio = ModuleType("pyannote.audio")
    pyannote_audio.Pipeline = SimpleNamespace(from_pretrained=lambda *_args, **_kwargs: pipeline)
    torch = ModuleType("torch")
    torch.device = lambda name: f"device:{name}"
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_package)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio)
    monkeypatch.setitem(sys.modules, "torch", torch)


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
            observed["audio"] = source
            return SimpleNamespace(
                speaker_diarization=Annotation(),
                exclusive_speaker_diarization=Annotation(),
            )

    class FakeAudioDecoder:
        def __init__(self, source):
            observed["audio_path"] = source

        def get_samples_played_in_range(self, *, start_seconds, stop_seconds):
            observed["decode_range"] = (start_seconds, stop_seconds)
            return SimpleNamespace(
                data=SimpleNamespace(numel=lambda: 16000),
                sample_rate=16000,
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
    torchcodec_package = ModuleType("torchcodec")
    torchcodec_package.__path__ = []
    torchcodec_decoders = ModuleType("torchcodec.decoders")
    torchcodec_decoders.AudioDecoder = FakeAudioDecoder
    torch = ModuleType("torch")
    torch.device = lambda name: f"device:{name}"
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_package)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio)
    monkeypatch.setitem(sys.modules, "torchcodec", torchcodec_package)
    monkeypatch.setitem(sys.modules, "torchcodec.decoders", torchcodec_decoders)
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
        "decode_range": (0.0, 1.0),
        "audio": str(audio_path.resolve()),
    }
    assert events[0] == {"type": "stage", "stage": "loading_diarization_model"}
    assert events[1] == {"type": "stage", "stage": "decoding_input"}
    assert events[2] == {"type": "stage", "stage": "diarizing"}
    assert events[3] == {
        "type": "turn",
        "kind": "regular",
        "start_seconds": 1.25,
        "end_seconds": 2.75,
        "speaker_id": "SPEAKER_00",
    }
    assert events[4]["kind"] == "exclusive"
    assert events[5] == {
        "type": "complete",
        "regular_turn_count": 1,
        "exclusive_turn_count": 1,
    }
    assert "HF_TOKEN" not in os.environ
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["PYANNOTE_METRICS_ENABLED"] == "0"


def test_runner_maps_audio_decoder_import_failure_to_a_stable_safe_error(monkeypatch):
    original_import = builtins.__import__

    def no_torchcodec(name, *args, **kwargs):
        if name == "torchcodec.decoders":
            raise OSError("native library path must stay in logs")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_torchcodec)

    with pytest.raises(DiarizationPhaseError) as raised:
        from asr_en_vi.diarization_runner import load_audio_decoder

        load_audio_decoder()

    assert raised.value.code == "diarization_decoder_unavailable"
    assert str(raised.value) == DIARIZATION_ERROR_MESSAGES[raised.value.code]
    assert "native library path" in str(raised.value.__cause__)


def test_runtime_preflight_loads_offline_pipeline_and_moves_to_selected_device(
    tmp_path, monkeypatch
):
    model = _prepared_model(tmp_path / "model")
    observed = {}

    class FakePipeline:
        def to(self, device):
            observed["device"] = device

    pipeline = FakePipeline()
    _install_pipeline_modules(monkeypatch, pipeline)
    monkeypatch.setattr(diarization_runner, "load_audio_decoder", lambda: object())

    preflight_diarization_model(model_path=model, device="cuda")

    assert observed == {"device": "device:cuda"}
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_runtime_preflight_cli_does_not_require_audio(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "model")
    calls = []
    monkeypatch.setattr(
        diarization_runner,
        "preflight_diarization_model",
        lambda **kwargs: calls.append(kwargs),
    )

    assert main(["--check-runtime", "--model", str(model), "--device", "cuda"]) == 0

    assert calls == [{"model_path": model, "device": "cuda"}]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_model_load_failure_uses_its_phase_code_and_hides_vendor_text(tmp_path, monkeypatch):
    model = _prepared_model(tmp_path / "model")

    class BrokenPipelineType:
        @staticmethod
        def from_pretrained(*_args, **_kwargs):
            raise RuntimeError("token=secret at /private/model/cache")

    pyannote_package = ModuleType("pyannote")
    pyannote_package.__path__ = []
    pyannote_audio = ModuleType("pyannote.audio")
    pyannote_audio.Pipeline = BrokenPipelineType
    torch = ModuleType("torch")
    torch.device = lambda name: name
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_package)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio)
    monkeypatch.setitem(sys.modules, "torch", torch)

    with pytest.raises(DiarizationPhaseError) as raised:
        diarization_runner._load_community_pipeline(model, "cpu")

    assert raised.value.code == "diarization_model_load_failed"
    assert str(raised.value) == DIARIZATION_ERROR_MESSAGES[raised.value.code]
    assert "token=secret" in str(raised.value.__cause__)


def test_cuda_move_failure_uses_cuda_phase_code(tmp_path, monkeypatch):
    model = _prepared_model(tmp_path / "model")

    class BrokenPipeline:
        def to(self, _device):
            raise RuntimeError("CUDA driver detail")

    _install_pipeline_modules(monkeypatch, BrokenPipeline())

    with pytest.raises(DiarizationPhaseError) as raised:
        diarization_runner._load_community_pipeline(model, "cuda")

    assert raised.value.code == "diarization_cuda_failed"
    assert str(raised.value) == DIARIZATION_ERROR_MESSAGES[raised.value.code]


def test_input_decode_failure_uses_its_phase_code(tmp_path):
    class BrokenDecoder:
        def __init__(self, _path):
            pass

        def get_samples_played_in_range(self, **_kwargs):
            raise RuntimeError("decoder internals with /private/path")

    with pytest.raises(DiarizationPhaseError) as raised:
        diarization_runner._validate_audio_decode(tmp_path / "recording.wav", BrokenDecoder)

    assert raised.value.code == "diarization_input_decode_failed"
    assert str(raised.value) == DIARIZATION_ERROR_MESSAGES[raised.value.code]


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        (
            "diarization_input_decode_failed",
            DIARIZATION_ERROR_MESSAGES["diarization_input_decode_failed"],
            "diarization_input_decode_failed",
        ),
        ("diarization_cuda_failed", "vendor detail with a local path", "diarization_failed"),
        ("unknown_vendor_code", "vendor detail", "diarization_failed"),
    ],
)
def test_child_error_allowlist_requires_known_code_and_exact_safe_message(code, message, expected):
    result_code, result_message = safe_diarization_error(code, message)

    assert result_code == expected
    assert result_message == DIARIZATION_ERROR_MESSAGES[expected]


def test_runner_emits_structured_safe_stderr_context_with_task_and_meeting_ids(
    tmp_path, monkeypatch, capsys
):
    model = _prepared_model(tmp_path / "model")
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio")

    def fail(**_kwargs):
        raise DiarizationPhaseError("diarization_input_decode_failed", "decoding_input")

    monkeypatch.setattr("asr_en_vi.diarization_runner.diarize_file", fail)
    diagnostic_id = "a" * 32
    meeting_id = "b" * 32
    assert (
        main(
            [
                "--model",
                str(model),
                "--audio",
                str(audio),
                "--device",
                "cpu",
                "--diagnostic-id",
                diagnostic_id,
                "--meeting-id",
                meeting_id,
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "type": "error",
        "code": "diarization_input_decode_failed",
        "message": DIARIZATION_ERROR_MESSAGES["diarization_input_decode_failed"],
    }
    context = json.loads(captured.err.splitlines()[-1])
    assert context == {
        "event": "diarization_error",
        "diagnostic_id": diagnostic_id,
        "task_id": diagnostic_id,
        "meeting_id": meeting_id,
        "stage": "decoding_input",
        "code": "diarization_input_decode_failed",
    }
    assert "Traceback" in captured.err
