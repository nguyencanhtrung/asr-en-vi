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
    assert app["healthcheck"]
    assert worker["healthcheck"]


def test_image_build_context_is_allowlisted_and_excludes_user_owned_files():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerignore[0] == "**"
    assert "!pyproject.toml" in dockerignore
    assert "!README.md" in dockerignore
    assert "!uv.lock" in dockerignore
    assert "!src/asr_en_vi/**" in dockerignore
    assert "COPY ." not in dockerfile
    assert "COPY src/ ./src/" in dockerfile
    assert "prototype" not in dockerfile
    assert "docs/" not in dockerfile
