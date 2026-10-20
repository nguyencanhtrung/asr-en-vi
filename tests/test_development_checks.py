from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check-environment.py"


def load_preflight():
    spec = importlib.util.spec_from_file_location("environment_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_classifies_timeout_without_hanging_the_suite(monkeypatch):
    module = load_preflight()

    def run(*args, **kwargs):
        assert kwargs["timeout"] == 1
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(module.subprocess, "run", run)
    result = module.check(["async-file"], 1)
    assert result["status"] == "blocked"
    assert result["category"] == "test_environment"
    assert result["checks"] == [
        {"probe": "async-file", "status": "blocked", "detail": "deadline exceeded"}
    ]


def test_cache_probe_detects_unusable_path_and_accepts_writable_cache(tmp_path):
    unusable = tmp_path / "file"
    unusable.write_text("not a directory")
    for directory, expected in ((tmp_path / "cache", 0), (unusable / "cache", 1)):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--cache-only"],
            env={**os.environ, "UV_CACHE_DIR": str(directory)},
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        assert result.returncode == expected, result.stderr
        value = json.loads(result.stdout)
        assert value["status"] == ("pass" if expected == 0 else "blocked")


def test_workflow_gate_propagates_linter_failure(tmp_path):
    executable = tmp_path / "actionlint"
    executable.write_text('#!/bin/sh\nprintf "invalid workflow expression\\n" >&2\nexit 7\n')
    executable.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", str(ROOT / "scripts" / "check-workflows.sh")],
        env={**os.environ, "PATH": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7
    assert "invalid workflow expression" in result.stderr


def test_workflow_gate_fails_when_linter_is_missing(tmp_path):
    result = subprocess.run(
        ["/bin/sh", str(ROOT / "scripts" / "check-workflows.sh")],
        env={**os.environ, "PATH": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "actionlint is required" in result.stderr
