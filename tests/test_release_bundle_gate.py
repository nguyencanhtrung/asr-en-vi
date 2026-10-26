import importlib.util
import subprocess
from pathlib import Path

import pytest

from asr_en_vi import cli

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "release_bundle", ROOT / "scripts/prepare-release-bundle.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_bundle_gate_uses_actual_version_and_schema_contract(tmp_path, monkeypatch):
    calls = []

    class StopAfterVersion(Exception):
        pass

    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            arguments = command[command.index("-m") + 2 :]
            code = cli.main(arguments)
            if code:
                raise subprocess.CalledProcessError(code, command)
            return subprocess.CompletedProcess(command, code)
        raise StopAfterVersion

    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(StopAfterVersion):
        module.prepare("synthetic-image", tmp_path, "0.1.0")
    assert len(calls) == 2
