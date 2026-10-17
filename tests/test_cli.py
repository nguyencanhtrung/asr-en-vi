from __future__ import annotations

import json

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

    assert main(["model", "check"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(missing) in captured.err
    assert "not prepared" in captured.err
    assert "Traceback" not in captured.err


def test_model_check_accepts_the_same_prepared_model_as_runtime(tmp_path, monkeypatch, capsys):
    model = _prepared_model(tmp_path / "prepared-model")
    monkeypatch.setenv("ASR_MODEL_PATH", str(model))

    assert main(["model", "check"]) == 0

    captured = capsys.readouterr()
    assert str(model) in captured.out
    assert "ready" in captured.out
    assert captured.err == ""
