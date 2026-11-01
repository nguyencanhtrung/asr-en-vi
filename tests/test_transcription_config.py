from __future__ import annotations

from pathlib import Path

import pytest

from asr_en_vi.config import Settings


def test_settings_read_local_model_device_and_compute_type(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ASR_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("ASR_MODEL_PATH", str(tmp_path / "prepared-model"))
    monkeypatch.setenv("ASR_DEVICE", "cuda")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "float16")

    settings = Settings.from_env()

    assert settings.asr_model_path == tmp_path / "prepared-model"
    assert settings.asr_device == "cuda"
    assert settings.asr_compute_type == "float16"


def test_settings_read_upload_chunk_bytes_and_keep_the_64_mib_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ASR_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("ASR_UPLOAD_CHUNK_BYTES", "4096")

    assert Settings.from_env().upload_chunk_bytes == 4096
    monkeypatch.delenv("ASR_UPLOAD_CHUNK_BYTES")
    assert Settings.from_env().upload_chunk_bytes == 64 * 1024**2


def test_settings_reject_upload_chunks_above_the_edge_safe_default(tmp_path):
    with pytest.raises(ValueError, match="upload_chunk_bytes"):
        Settings(
            data_dir=tmp_path / "data",
            auth_dir=tmp_path / "auth",
            upload_chunk_bytes=64 * 1024**2 + 1,
        )


def test_settings_default_to_automatic_hardware_specific_profiles(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ASR_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("ASR_MODEL_PATH", raising=False)
    monkeypatch.delenv("ASR_COMPUTE_TYPE", raising=False)
    monkeypatch.setenv("ASR_GPU_MODEL_PATH", str(tmp_path / "large"))
    monkeypatch.setenv("ASR_CPU_MODEL_PATH", str(tmp_path / "small"))

    settings = Settings.from_env()

    assert settings.asr_device == "auto"
    assert settings.asr_model_path is None
    assert settings.asr_compute_type is None
    assert settings.asr_gpu_model_path == tmp_path / "large"
    assert settings.asr_cpu_model_path == tmp_path / "small"
    assert settings.asr_gpu_compute_type == "float16"
    assert settings.asr_cpu_compute_type == "int8"
    assert settings.diarization_model_path == Path("/models/speaker-diarization-community-1")


def test_settings_read_local_diarization_model_directory(monkeypatch, tmp_path):
    path = tmp_path / "community-1"
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ASR_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("ASR_DIARIZATION_MODEL_PATH", str(path))

    assert Settings.from_env().diarization_model_path == path


@pytest.mark.parametrize(
    ("name", "value"),
    [("ASR_DEVICE", "remote"), ("ASR_COMPUTE_TYPE", "unknown")],
)
def test_settings_reject_unsupported_asr_options(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ASR_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        Settings.from_env()
