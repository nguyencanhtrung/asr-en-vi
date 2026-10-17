from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_compose_separates_services_volumes_and_loopback_publish():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]
    worker = compose["services"]["worker"]

    assert app["ports"] == ["127.0.0.1:${ASR_PORT:-8765}:8765"]
    assert "ports" not in worker
    assert "data:/var/lib/asr-en-vi/data" in app["volumes"]
    assert "data:/var/lib/asr-en-vi/data" in worker["volumes"]
    assert "auth:/var/lib/asr-en-vi/auth" in app["volumes"]
    assert all("auth:" not in mount for mount in worker["volumes"])
    assert app["image"] == worker["image"]
    assert app["environment"]["ASR_MAX_UPLOAD_BYTES"] == "${ASR_MAX_UPLOAD_BYTES:-4294967296}"
    assert app["environment"]["ASR_MAX_RECORDING_SECONDS"] == (
        "${ASR_MAX_RECORDING_SECONDS:-14400}"
    )
    assert app["environment"]["ASR_MODEL_PATH"] == ("${ASR_MODEL_PATH:-/models/whisper-large-v3}")
    assert worker["environment"]["ASR_DEVICE"] == "${ASR_DEVICE:-cpu}"
    assert worker["environment"]["ASR_COMPUTE_TYPE"] == "${ASR_COMPUTE_TYPE:-int8}"
    assert any(mount.endswith(":/models:ro") for mount in app["volumes"])
    assert any(mount.endswith(":/models:ro") for mount in worker["volumes"])
    assert app["healthcheck"]
    assert worker["healthcheck"]


def test_image_build_context_is_allowlisted_and_excludes_user_owned_files():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert dockerignore[0] == "**"
    assert "!pyproject.toml" in dockerignore
    assert "!README.md" in dockerignore
    assert "!uv.lock" in dockerignore
    assert "!src/asr_en_vi/**" in dockerignore
    assert "COPY ." not in dockerfile
    assert "COPY pyproject.toml README.md uv.lock ./" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "faster-whisper==1.2.1" in pyproject
    assert '"av>=11,<19"' in pyproject
    assert not (ROOT / "requirements-asr.txt").exists()
    assert "COPY src/ ./src/" in dockerfile
    assert "prototype" not in dockerfile
    assert "docs/" not in dockerfile


def test_worker_grace_period_exceeds_runner_worst_case_stop_time():
    from asr_en_vi import worker as worker_module

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    grace = compose["services"]["worker"]["stop_grace_period"]
    worst_case = worker_module.RUNNER_TERM_GRACE_SECONDS + worker_module.RUNNER_KILL_GRACE_SECONDS

    assert grace.endswith("s")
    assert float(grace.removesuffix("s")) >= worst_case + 5


def test_claimed_task_starting_stage_has_a_vietnamese_label():
    script = (ROOT / "src/asr_en_vi/web/history.js").read_text(encoding="utf-8")
    labels = script.split("const TASK_STAGES = {", 1)[1].split("};", 1)[0]

    assert '    starting: "Đang bắt đầu",' in labels
