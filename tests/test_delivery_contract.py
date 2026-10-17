from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from media_tools import require_media_tools

ROOT = Path(__file__).parents[1]
PIPELINE_PATH = ROOT / ".github" / "workflows" / "pipeline.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_pipeline_gates_pull_requests_main_and_version_tags():
    pipeline = load_yaml(PIPELINE_PATH)
    triggers = pipeline["on"]

    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["push"]["tags"] == ["v*"]
    assert pipeline["permissions"] == {"contents": "read"}

    quality = pipeline["jobs"]["quality"]
    check_step = next(step for step in quality["steps"] if step["name"] == "Run repository checks")
    assert check_step["run"] == "./scripts/check.sh"
    assert check_step["env"]["ASR_RUN_BROWSER_TESTS"] == "1"
    assert "container" in pipeline["jobs"]
    names = [step["name"] for step in quality["steps"]]
    media_step = quality["steps"][names.index("Install media tools")]
    assert "apt-get install" in media_step["run"]
    for tool in ("ffmpeg", "ffprobe"):
        assert f"command -v {tool}" in media_step["run"].splitlines()
    assert names.index("Install media tools") < names.index("Run repository checks")
    # Missing media tools must fail CI instead of silently skipping media tests.
    assert check_step["env"]["ASR_REQUIRE_MEDIA_TOOLS"] == "1"


def test_media_gate_skips_locally_but_fails_when_ci_requires_tools(monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("ASR_REQUIRE_MEDIA_TOOLS", raising=False)
    with pytest.raises(pytest.skip.Exception):
        require_media_tools()
    monkeypatch.setenv("ASR_REQUIRE_MEDIA_TOOLS", "1")
    with pytest.raises(pytest.fail.Exception):
        require_media_tools()


def test_container_job_runs_runtime_smoke_check_on_the_built_image():
    steps = load_yaml(PIPELINE_PATH)["jobs"]["container"]["steps"]
    build = next(step for step in steps if step["name"] == "Build container")
    smoke = next(step for step in steps if step["name"] == "Smoke-test container runtime")

    assert build["with"]["load"] is True
    assert steps.index(smoke) > steps.index(build)
    assert smoke["run"] == f"./scripts/container-smoke.sh {build['with']['tags']}"
    script = (ROOT / "scripts" / "container-smoke.sh").read_text(encoding="utf-8")
    assert "normalize_media" in script and "/healthz" in script
    assert "from torchcodec.decoders import AudioDecoder" in script


def test_startup_detects_gpu_prepares_model_and_preflights_before_services():
    script = (ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")

    build = script.index("compose_build")
    detect = script.index("--gpus all")
    model_prepare = script.index("python -m asr_en_vi.cli model prepare")
    runtime_check = script.index("python -m asr_en_vi.cli runtime check")
    start = script.index("compose_runtime up")

    assert "compose.gpu.yaml" in script
    assert "nvidia-smi" in script
    assert build < detect < model_prepare < runtime_check < start


def test_publish_waits_for_every_gate_and_has_only_required_write_permissions():
    publish = load_yaml(PIPELINE_PATH)["jobs"]["publish"]

    assert publish["if"] == "github.event_name == 'push'"
    assert publish["needs"] == ["quality", "container"]
    assert publish["permissions"] == {
        "contents": "read",
        "packages": "write",
        "attestations": "write",
        "id-token": "write",
    }

    build_step = next(
        step for step in publish["steps"] if step["name"] == "Build and publish container"
    )
    assert build_step["with"]["push"] is True
    assert build_step["with"]["platforms"] == "linux/amd64,linux/arm64"
    assert build_step["with"]["provenance"] == "mode=max"
    assert build_step["with"]["sbom"] is True
    assert any(step["name"] == "Attest published container" for step in publish["steps"])


def test_every_action_is_pinned_to_an_immutable_commit():
    pipeline = load_yaml(PIPELINE_PATH)
    action_ref = re.compile(r"^[^@]+@[0-9a-f]{40}$")

    used_actions = [
        step["uses"] for job in pipeline["jobs"].values() for step in job["steps"] if "uses" in step
    ]

    assert used_actions
    assert all(action_ref.fullmatch(action) for action in used_actions)


def test_dependabot_maintains_each_delivery_dependency_ecosystem():
    dependabot = load_yaml(DEPENDABOT_PATH)
    ecosystems = {update["package-ecosystem"] for update in dependabot["updates"]}

    assert ecosystems == {"uv", "github-actions", "docker"}
