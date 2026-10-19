from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from media_tools import require_media_tools

ROOT = Path(__file__).parents[1]
PIPELINE_PATH = ROOT / ".github" / "workflows" / "pipeline.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
COMMUNITY_1_FILES = (
    "config.yaml",
    "embedding/pytorch_model.bin",
    "plda/plda.npz",
    "plda/xvec_transform.npz",
    "segmentation/pytorch_model.bin",
)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_start(
    tmp_path: Path,
    model_files: tuple[str, ...] = (),
    model_overrides: dict[str, bytes] | None = None,
    fail_install_check: bool = False,
) -> subprocess.CompletedProcess[str]:
    model_root = tmp_path / "models"
    model_directory = model_root / "speaker-diarization-community-1"
    for relative_path in model_files:
        target = model_directory / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"model data")
    for relative_path, content in (model_overrides or {}).items():
        target = model_directory / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    stub_directory = tmp_path / "bin"
    stub_directory.mkdir()
    command_log = tmp_path / "docker.log"
    _write_executable(
        stub_directory / "docker",
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> "$DOCKER_LOG"\n'
        'case "$*" in *"asr_en_vi.cli installation check"*) '
        '[ "${FAIL_INSTALL_CHECK:-0}" != 1 ] || exit 1 ;; esac\n'
        'if [ "$1" = compose ] && [ "$4" = config ]; then\n'
        "  printf '%s\\n' \\\n"
        f"    'ASR_DEVICE=cpu' 'ASR_MODEL_HOST_PATH={model_root}' \\\n"
        "    'ASR_DIARIZATION_MODEL_PATH=/models/speaker-diarization-community-1'\n"
        "fi\n",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{stub_directory}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(command_log)
    environment["FAIL_INSTALL_CHECK"] = "1" if fail_install_check else "0"
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / "start.sh")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    result.docker_log = command_log.read_text(encoding="utf-8")
    return result


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
    container = load_yaml(PIPELINE_PATH)["jobs"]["container"]
    steps = container["steps"]
    build = next(step for step in steps if step["name"] == "Build container")
    smoke = next(step for step in steps if step["name"] == "Smoke-test container runtime")

    assert container["timeout-minutes"] >= 30
    assert build["with"]["load"] is True
    assert build["with"]["cache-from"] == "type=gha,scope=container"
    assert "cache-to" not in build["with"]
    assert steps.index(smoke) > steps.index(build)
    assert smoke["run"] == f"./scripts/container-smoke.sh {build['with']['tags']}"
    script = (ROOT / "scripts" / "container-smoke.sh").read_text(encoding="utf-8")
    assert "normalize_media" in script and "/healthz" in script
    assert "from torchcodec.decoders import AudioDecoder" in script
    assert "AudioDecoder(target).get_all_samples()" in script
    assert "decoded.data.numel() > 0" in script
    assert 'print("torchcodec decode ok")' in script


def test_startup_detects_gpu_prepares_model_and_preflights_before_services():
    script = (ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")

    model_gate = script.index("for required_model_file")
    build = script.index("compose_build build")
    detect = script.index("docker run --rm --gpus all")
    model_prepare = script.index("python -m asr_en_vi.cli model prepare")
    runtime_check = script.index("python -m asr_en_vi.cli runtime check")
    start = script.index("compose_runtime up")

    assert "compose.gpu.yaml" in script
    assert "nvidia-smi" in script
    assert model_gate < build < detect < model_prepare < runtime_check < start


def test_startup_rejects_incomplete_community_model_before_image_build(tmp_path):
    result = _run_start(tmp_path)

    assert result.returncode != 0
    assert "compose -f compose.yaml build" not in result.docker_log
    guidance = result.stdout + result.stderr
    assert "accept the Community-1 conditions" in guidance
    assert "hf auth login" in guidance
    assert "git clone https://hf.co/pyannote/speaker-diarization-community-1" in guidance
    assert "anonymous" not in guidance.casefold()


def test_startup_checks_complete_community_model_then_preflights_before_services(tmp_path):
    result = _run_start(tmp_path, COMMUNITY_1_FILES)

    assert result.returncode == 0, result.stdout + result.stderr
    commands = result.docker_log
    build = commands.index("compose -f compose.yaml build")
    model_prepare = commands.index("python -m asr_en_vi.cli model prepare")
    runtime_check = commands.index("python -m asr_en_vi.cli runtime check")
    services = commands.index("compose -f compose.yaml up")
    install_check = commands.index("python -m asr_en_vi.cli installation check")
    access_link = commands.index("python -m asr_en_vi.cli access show")
    assert build < model_prepare < runtime_check < services < install_check < access_link


def test_startup_does_not_print_access_link_when_app_cannot_see_worker_or_models(tmp_path):
    result = _run_start(tmp_path, COMMUNITY_1_FILES, fail_install_check=True)

    assert result.returncode != 0
    assert "python -m asr_en_vi.cli installation check" in result.docker_log
    assert "python -m asr_en_vi.cli access show" not in result.docker_log


def test_startup_rejects_git_lfs_pointer_before_image_build(tmp_path):
    result = _run_start(
        tmp_path,
        COMMUNITY_1_FILES,
        {
            "embedding/pytorch_model.bin": (
                b"version https://git-lfs.github.com/spec/v1\n"
                b"oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
                b"size 10\n"
            )
        },
    )

    assert result.returncode != 0
    assert "unresolved Git LFS pointer" in result.stderr
    assert "hf auth login --add-to-git-credential" in result.stderr
    assert "compose -f compose.yaml build" not in result.docker_log


def test_repository_checks_have_shell_syntax_and_pytest_timeout_guardrails():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    check_script = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
    e2e_test = (ROOT / "tests" / "test_transcription_video_e2e.py").read_text(encoding="utf-8")
    pytest_config = project["tool"]["pytest"]["ini_options"]

    assert any(
        dependency.startswith("pytest-timeout")
        for dependency in project["dependency-groups"]["dev"]
    )
    assert pytest_config["timeout"] == 300
    assert pytest_config["timeout_method"] == "thread"
    assert "./scripts/check-shell-syntax.sh" in check_script
    assert "pytest.mark.timeout(0)" in e2e_test


def test_shell_syntax_gate_propagates_a_script_failure(tmp_path):
    scripts_root = tmp_path / "scripts"
    scripts_root.mkdir()
    _write_executable(scripts_root / "valid.sh", "#!/bin/sh\necho valid\n")
    _write_executable(scripts_root / "broken.sh", "#!/bin/sh\necho 'unterminated\n")

    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / "check-shell-syntax.sh"), str(scripts_root)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "syntax error" in result.stderr.casefold() or "unterminated" in result.stderr.casefold()


def test_platform_images_publish_only_on_version_tags_with_native_runners():
    jobs = load_yaml(PIPELINE_PATH)["jobs"]
    publish_platform = jobs["publish-platform"]
    expected_platforms = {
        "linux/amd64": {"runner": "ubuntu-24.04", "artifact": "amd64"},
        "linux/arm64": {"runner": "ubuntu-24.04-arm", "artifact": "arm64"},
    }

    assert publish_platform["if"] == "startsWith(github.ref, 'refs/tags/v')"
    assert publish_platform["needs"] == ["quality", "container"]
    assert publish_platform["timeout-minutes"] >= 60
    assert publish_platform["permissions"] == {"contents": "read", "packages": "write"}
    assert publish_platform["strategy"]["fail-fast"] is False
    matrix_entries = publish_platform["strategy"]["matrix"]["include"]
    assert {
        entry["platform"]: {"runner": entry["runner"], "artifact": entry["artifact"]}
        for entry in matrix_entries
    } == expected_platforms
    assert all("qemu" not in str(step).casefold() for step in publish_platform["steps"])

    build_step = next(
        step
        for step in publish_platform["steps"]
        if step["name"] == "Build and push platform image"
    )
    assert build_step["with"]["platforms"] == "${{ matrix.platform }}"
    assert "push-by-digest=true" in build_step["with"]["outputs"]
    assert "name-canonical=true" in build_step["with"]["outputs"]
    assert "push=true" in build_step["with"]["outputs"]
    assert "cache-to" not in build_step["with"]
    assert build_step["with"]["cache-from"] == "type=gha,scope=container"
    assert build_step["with"]["provenance"] == "mode=max"
    assert build_step["with"]["sbom"] is True

    export_digest = next(
        step for step in publish_platform["steps"] if step["name"] == "Export image digest"
    )
    assert '"${{ steps.publish.outputs.digest }}"' in export_digest["run"]
    assert 'touch "${RUNNER_TEMP}/digests/${digest#sha256:}"' in export_digest["run"]
    upload_digest = next(
        step for step in publish_platform["steps"] if step["name"] == "Upload image digest"
    )
    assert upload_digest["with"]["name"] == "digest-${{ matrix.artifact }}"
    assert upload_digest["with"]["if-no-files-found"] == "error"


def test_manifest_publish_waits_for_platform_images_and_attests_manifest_digest():
    jobs = load_yaml(PIPELINE_PATH)["jobs"]
    publish_platform = jobs["publish-platform"]
    publish = jobs["publish"]
    version_tag_condition = "startsWith(github.ref, 'refs/tags/v')"

    assert publish_platform["if"] == version_tag_condition
    assert publish["if"] == version_tag_condition
    assert publish["needs"] == ["publish-platform"]
    assert publish["timeout-minutes"] >= 15
    assert publish["permissions"] == {
        "contents": "read",
        "packages": "write",
        "attestations": "write",
        "id-token": "write",
    }

    download_digests = next(
        step for step in publish["steps"] if step["name"] == "Download image digests"
    )
    assert download_digests["with"]["pattern"] == "digest-*"
    assert download_digests["with"]["merge-multiple"] is True

    manifest = next(
        step
        for step in publish["steps"]
        if step["name"] == "Create and publish multi-platform manifest"
    )
    assert manifest["id"] == "publish"
    assert manifest["working-directory"] == "${{ runner.temp }}/digests"
    assert manifest["env"]["IMAGE_TAGS_JSON"] == "${{ steps.metadata.outputs.json }}"
    assert "docker buildx imagetools create" in manifest["run"]
    assert '.tags | map("-t " + .)' in manifest["run"]
    assert "$(printf '${{ env.IMAGE_NAME }}@sha256:%s ' *)" in manifest["run"]
    assert "--metadata-file" in manifest["run"]
    assert 'echo "digest=${digest}" >> "${GITHUB_OUTPUT}"' in manifest["run"]

    attest = next(step for step in publish["steps"] if step["name"] == "Attest published container")
    assert attest["with"]["subject-name"] == "${{ env.IMAGE_NAME }}"
    assert attest["with"]["subject-digest"] == "${{ steps.publish.outputs.digest }}"
    assert attest["with"]["push-to-registry"] is True

    metadata = next(step for step in publish["steps"] if step.get("id") == "metadata")
    assert metadata["with"]["tags"].splitlines() == [
        "type=sha,format=long",
        "type=ref,event=tag",
        "type=semver,pattern={{version}}",
        "type=semver,pattern={{major}}.{{minor}}",
        "type=raw,value=latest",
    ]


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
