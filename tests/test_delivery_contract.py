from __future__ import annotations

import re
from pathlib import Path

import yaml

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
