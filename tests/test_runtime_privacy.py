from __future__ import annotations

import json
import sys

from asr_en_vi import notes_runner, worker
from asr_en_vi.runtime import RuntimeConfigurationError
from asr_en_vi.safe_logging import emit_safe_log


def test_safe_log_allowlist_never_echoes_untrusted_values(capsys):
    emit_safe_log(
        event="provider exception token=secret",
        stage="/private/model",
        code="raw exception /private/recording",
    )

    captured = capsys.readouterr()
    assert json.loads(captured.err) == {
        "event": "runtime_error",
        "stage": "unknown",
        "code": "internal_error",
    }
    assert "token=secret" not in captured.err
    assert "/private/model" not in captured.err
    assert "/private/recording" not in captured.err


def test_notes_runner_generic_failure_omits_task_and_exception_text(tmp_path, monkeypatch, capsys):
    task_id = "a" * 32

    def fail(*_args, **_kwargs):
        raise RuntimeError("notes exception token=secret /private/recording")

    monkeypatch.setattr(notes_runner, "load_notes_task_input", fail)

    assert notes_runner.run_notes_task(tmp_path, task_id, "owner") == 1

    captured = capsys.readouterr()
    assert json.loads(captured.err) == {
        "event": "notes_error",
        "stage": "starting_notes",
        "code": "notes_failed",
    }
    assert task_id not in captured.err
    assert "notes exception" not in captured.err
    assert "token=secret" not in captured.err
    assert "/private/recording" not in captured.err


def test_worker_startup_failure_uses_fixed_code_and_stage(monkeypatch, capsys):
    def fail(_settings):
        raise RuntimeConfigurationError("worker startup token=secret /private/model")

    monkeypatch.setattr(worker, "run_worker", fail)
    monkeypatch.setattr(sys, "argv", ["asr-en-vi-worker"])

    assert worker.main() == 1

    captured = capsys.readouterr()
    assert json.loads(captured.err) == {
        "event": "worker_error",
        "stage": "worker_startup",
        "code": "runtime_unavailable",
    }
    assert "token=secret" not in captured.err
    assert "/private/model" not in captured.err
