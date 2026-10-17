from __future__ import annotations

import json

import huggingface_hub

from asr_en_vi import cli
from asr_en_vi.cli import main


def _prepared_model(path):
    path.mkdir()
    (path / "model.bin").write_bytes(b"model")
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


def test_model_check_fails_cleanly_when_local_model_is_missing(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "missing-model"
    monkeypatch.setenv("ASR_MODEL_PATH", str(missing))
    monkeypatch.setenv("ASR_DEVICE", "cpu")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "int8")

    assert main(["model", "check"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(missing) in captured.err
    assert "not prepared" in captured.err
    assert "Traceback" not in captured.err


def test_model_check_accepts_the_same_prepared_model_as_runtime(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "prepared-model")
    monkeypatch.setenv("ASR_MODEL_PATH", str(model))
    monkeypatch.setenv("ASR_DEVICE", "cpu")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "int8")

    assert main(["model", "check"]) == 0

    captured = capsys.readouterr()
    assert str(model) in captured.out
    assert "ready" in captured.out
    assert captured.err == ""


def test_runtime_check_rejects_cuda_when_no_gpu_is_visible(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "prepared-model")
    monkeypatch.setenv("ASR_MODEL_PATH", str(model))
    monkeypatch.setenv("ASR_DEVICE", "cuda")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(cli.ctypes, "CDLL", lambda _name: object())
    monkeypatch.setattr(cli.ctranslate2, "get_cuda_device_count", lambda: 0)

    assert main(["runtime", "check"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No NVIDIA GPU is visible" in captured.err


def test_runtime_check_rejects_missing_cuda_libraries(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "prepared-model")
    monkeypatch.setenv("ASR_MODEL_PATH", str(model))
    monkeypatch.setenv("ASR_DEVICE", "cuda")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "float16")

    def missing_library(name):
        raise OSError(f"missing {name}")

    monkeypatch.setattr(cli.ctranslate2, "get_cuda_device_count", lambda: 1)
    monkeypatch.setattr(cli.ctypes, "CDLL", missing_library)

    assert main(["runtime", "check"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "CUDA runtime library is unavailable" in captured.err


def test_runtime_check_accepts_cuda_model_device_and_compute_type(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "prepared-model")
    monkeypatch.setenv("ASR_MODEL_PATH", str(model))
    monkeypatch.setenv("ASR_DEVICE", "cuda")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(cli.ctypes, "CDLL", lambda _name: object())
    monkeypatch.setattr(cli.ctranslate2, "get_cuda_device_count", lambda: 1)
    monkeypatch.setattr(
        cli.ctranslate2,
        "get_supported_compute_types",
        lambda _device: {"float16", "float32", "int8_float16"},
    )

    assert main(["runtime", "check"]) == 0

    captured = capsys.readouterr()
    assert str(model) in captured.out
    assert "NVIDIA GPU is ready" in captured.out
    assert "float16" in captured.out
    assert captured.err == ""


def test_model_prepare_downloads_the_automatically_selected_cpu_model(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "whisper-small"
    monkeypatch.setenv("ASR_DEVICE", "auto")
    monkeypatch.setenv("ASR_CPU_MODEL_PATH", str(target))
    monkeypatch.delenv("ASR_MODEL_PATH", raising=False)
    monkeypatch.delenv("ASR_COMPUTE_TYPE", raising=False)
    monkeypatch.setattr(cli.ctranslate2, "get_cuda_device_count", lambda: 0)
    monkeypatch.setattr(
        cli.ctranslate2, "get_supported_compute_types", lambda _device: {"int8", "float32"}
    )
    downloaded = []

    def download(*, repo_id, local_dir):
        downloaded.append((repo_id, local_dir))
        _prepared_model(local_dir)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", download)

    assert main(["model", "prepare"]) == 0
    assert downloaded == [("Systran/faster-whisper-small", target.resolve())]
    assert "ready" in capsys.readouterr().out
