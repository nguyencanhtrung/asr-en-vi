from __future__ import annotations

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
