from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
IMAGE = "ghcr.io/example/asr@sha256:" + "a" * 64


@pytest.mark.parametrize("failure", ["", "pull", "version", "revision"])
def test_published_image_gate_uses_anonymous_digest_and_stops_on_mismatch(tmp_path, failure):
    workflow = yaml.safe_load((ROOT / ".github/workflows/pipeline.yml").read_text())
    steps = workflow["jobs"]["publish-platform"]["steps"]
    gate = next(step for step in steps if step["name"] == "Verify public platform image")
    names = [step["name"] for step in steps]
    assert names.index("Build and push platform image") < names.index(gate["name"])
    assert names.index(gate["name"]) < names.index("Export image digest")
    assert gate["env"]["PUBLISHED_IMAGE"] == (
        "${{ env.IMAGE_NAME }}@${{ steps.publish.outputs.digest }}"
    )
    source = tmp_path / "src/asr_en_vi"
    source.mkdir(parents=True)
    shutil.copyfile(ROOT / "src/asr_en_vi/storage.py", source / "storage.py")
    trace = tmp_path / "trace.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "record = {'args': args}\n"
        "if args[0] == 'pull':\n"
        "    config = pathlib.Path(os.environ['DOCKER_CONFIG'])\n"
        "    assert config.is_dir() and not list(config.iterdir())\n"
        "    record['anonymous_config'] = str(config)\n"
        "with open(os.environ['TRACE'], 'a') as output:\n"
        "    output.write(json.dumps(record) + '\\n')\n"
        "failure = os.environ['FAILURE']\n"
        "if args[0] == 'pull':\n"
        "    sys.exit(1 if failure == 'pull' else 0)\n"
        "elif args[0] == 'run':\n"
        "    assert '--pull=never' in args and '--expect-version' in args\n"
        "    assert args[args.index('--expect-version') + 1] == '0.1.0'\n"
        "    if failure == 'version': sys.exit(1)\n"
        "    from asr_en_vi.cli import main\n"
        "    sys.exit(main(args[args.index('-m') + 2:]))\n"
        "elif args[:2] == ['image', 'inspect']:\n"
        "    print('wrong' if failure == 'revision' else os.environ['GITHUB_SHA'])\n"
        "else:\n"
        "    sys.exit(99)\n"
    )
    docker.chmod(0o755)
    (tmp_path / "scripts").mkdir()
    smoke = tmp_path / "scripts/container-smoke.sh"
    smoke.write_text('#!/bin/sh\nset -eu\nprintf "%s" "$1" > smoke-image.txt\n')
    smoke.chmod(0o755)
    inherited_config = tmp_path / "signed-in-config"
    inherited_config.mkdir()
    (inherited_config / "config.json").write_text('{"auths":{"example":{}}}')

    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", gate["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "DOCKER_CONFIG": str(inherited_config),
            "PUBLISHED_IMAGE": IMAGE,
            "GITHUB_REF_NAME": "v0.1.0",
            "GITHUB_SHA": "b" * 40,
            "TRACE": str(trace),
            "FAILURE": failure,
            "PYTHONPATH": str(ROOT / "src"),
        },
        capture_output=True,
        text=True,
    )
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    assert all(IMAGE in call["args"] for call in calls)
    assert not Path(calls[0]["anonymous_config"]).exists()
    assert (inherited_config / "config.json").is_file()
    if failure:
        assert result.returncode != 0
        assert not (tmp_path / "smoke-image.txt").exists()
        assert len(calls) == {"pull": 1, "version": 2, "revision": 3}[failure]
    else:
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "smoke-image.txt").read_text() == IMAGE
