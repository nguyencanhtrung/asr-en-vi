from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "offline-smoke.py"
SPEC = importlib.util.spec_from_file_location("offline_smoke_harness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
offline_smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = offline_smoke
SPEC.loader.exec_module(offline_smoke)


def test_project_names_are_unique_and_prefix_is_bounded():
    first = offline_smoke.unique_project_name("asr-offline-smoke")
    second = offline_smoke.unique_project_name("asr-offline-smoke")

    assert first.startswith("asr-offline-smoke-")
    assert second.startswith("asr-offline-smoke-")
    assert first != second
    assert len(first) <= 44
    with pytest.raises(offline_smoke.SmokeFailure):
        offline_smoke.unique_project_name("Unsafe/Project")
    with pytest.raises(offline_smoke.SmokeFailure):
        offline_smoke.unique_project_name("other-project")


def test_isolated_compose_removes_ports_build_and_pull_policy_without_changing_volumes():
    original = {
        "services": {
            "app": {
                "image": "example.invalid/asr:test",
                "build": {"context": "."},
                "pull_policy": "never",
                "ports": ["127.0.0.1:8765:8765"],
                "volumes": ["project_data:/var/lib/asr-en-vi/data"],
            },
            "worker": {
                "image": "example.invalid/asr:test",
                "build": {"context": "."},
                "volumes": ["project_data:/var/lib/asr-en-vi/data"],
            },
        },
        "volumes": {"data": {"name": "project_data"}},
    }

    isolated = offline_smoke.isolated_compose_document(original, "asr-offline-smoke-a1b2c3d4")

    assert original["services"]["app"]["ports"]
    assert isolated["services"]["app"]["ports"] == []
    assert "build" not in isolated["services"]["app"]
    assert "build" not in isolated["services"]["worker"]
    assert "pull_policy" not in isolated["services"]["app"]
    assert isolated["networks"]["default"]["internal"] is True
    assert isolated["volumes"] == original["volumes"]
    assert isolated["services"]["app"]["volumes"] == original["services"]["app"]["volumes"]
    assert isolated["name"] == "asr-offline-smoke-a1b2c3d4"


def test_resolved_compose_uses_gpu_overlay_and_offline_config_keeps_device_request(
    monkeypatch, tmp_path
):
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    device_request = {"count": -1, "capabilities": ["gpu"]}
    resolved = {
        "services": {
            "app": {
                "image": options.image,
                "build": {"context": "."},
                "pull_policy": "never",
                "ports": ["127.0.0.1:8765:8765"],
                "volumes": ["auth:/var/lib/asr-en-vi/auth"],
                "environment": {"ASR_PUBLIC_URL": harness.base_url},
            },
            "worker": {
                "image": options.image,
                "build": {"context": "."},
                "volumes": ["data:/var/lib/asr-en-vi/data"],
                "environment": {"ASR_DEVICE": "cuda"},
                "gpus": [device_request],
            },
        },
        "volumes": {"auth": {"name": "smoke_auth"}, "data": {"name": "smoke_data"}},
        "networks": {"default": {"driver": "bridge"}},
    }
    commands = []

    def command_double(command, **_kwargs):
        commands.append(command)
        return offline_smoke.subprocess.CompletedProcess(command, 0, json.dumps(resolved), "")

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    isolated_path = harness._write_isolated_compose()
    try:
        file_args = [
            commands[0][index + 1] for index, value in enumerate(commands[0][:-1]) if value == "-f"
        ]
        assert file_args == [str(offline_smoke.COMPOSE_FILE), str(offline_smoke.GPU_COMPOSE_FILE)]
        isolated = json.loads(isolated_path.read_text(encoding="utf-8"))
        assert isolated["services"]["worker"]["gpus"] == [device_request]
        assert isolated["services"]["app"]["volumes"] == resolved["services"]["app"]["volumes"]
        assert (
            isolated["services"]["worker"]["volumes"] == resolved["services"]["worker"]["volumes"]
        )
        assert (
            isolated["services"]["app"]["environment"] == resolved["services"]["app"]["environment"]
        )
        assert (
            isolated["services"]["worker"]["environment"]
            == resolved["services"]["worker"]["environment"]
        )
        assert isolated["volumes"] == resolved["volumes"]

        harness.container_python("app", "print('{}')", label="default config exec")
        default_exec_files = [
            commands[1][index + 1] for index, value in enumerate(commands[1][:-1]) if value == "-f"
        ]
        assert default_exec_files == [
            str(offline_smoke.COMPOSE_FILE),
            str(offline_smoke.GPU_COMPOSE_FILE),
        ]
        harness.container_python(
            "app", "print('{}')", label="isolated config exec", config_path=isolated_path
        )
        isolated_exec_files = [
            commands[2][index + 1] for index, value in enumerate(commands[2][:-1]) if value == "-f"
        ]
        assert isolated_exec_files == [str(isolated_path)]
    finally:
        isolated_path.unlink(missing_ok=True)


def test_cleanup_ownership_requires_exact_project_labels():
    project = "asr-offline-smoke-a1b2c3d4"
    container = {"Config": {"Labels": {"com.docker.compose.project": project}}}
    network = {"Labels": {"com.docker.compose.project": project}}
    foreign = {"Labels": {"com.docker.compose.project": "asr-en-vi"}}

    assert offline_smoke.owned_compose_resources(project, [container], [network]) is True
    assert offline_smoke.owned_compose_resources(project, [container, foreign], [network]) is False


def test_project_collision_preflight_uses_read_only_command_doubles(monkeypatch, tmp_path):
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    commands = []

    def command_double(command, **_kwargs):
        commands.append(command)
        return offline_smoke.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    harness._assert_project_unused()

    assert [command[1:3] for command in commands] == [
        ["ps", "--all"],
        ["network", "ls"],
        ["volume", "ls"],
    ]
    assert all(
        f"label=com.docker.compose.project={harness.project}" in command for command in commands
    )


def test_project_collision_preflight_stops_before_any_mutation(monkeypatch, tmp_path):
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    commands = []

    def command_double(command, **_kwargs):
        commands.append(command)
        output = "existing-volume-id\n" if command[1:3] == ["volume", "ls"] else ""
        return offline_smoke.subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    with pytest.raises(offline_smoke.SmokeFailure, match="already owns Docker volumes"):
        harness._assert_project_unused()

    assert len(commands) == 3
    assert all(command[1] in {"ps", "network", "volume"} for command in commands)


def test_source_or_pull_refuses_to_update_an_image_used_by_a_container(monkeypatch, tmp_path):
    options = offline_smoke.SmokeOptions(
        image="ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0-rc.1",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="pull",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    commands = []

    def command_double(command, **_kwargs):
        commands.append(command)
        return offline_smoke.subprocess.CompletedProcess(command, 0, "container-id\n", "")

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    with pytest.raises(offline_smoke.SmokeFailure, match="referenced by an existing container"):
        harness._assert_image_not_in_use()

    assert len(commands) == 1
    assert commands[0][1:3] == ["ps", "--all"]
    assert "ancestor=ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0-rc.1" in commands[0]


def test_embedded_container_python_snippets_compile():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    snippets = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        if isinstance(node.value.value, str) and any(
            isinstance(target, ast.Name) and target.id in {"script", "probe"}
            for target in node.targets
        ):
            snippets.append(node.value.value)

    assert len(snippets) >= 4
    for snippet in snippets:
        compile(snippet, "<offline-smoke-container-script>", "exec")


def test_redactor_removes_known_credentials_and_access_fragments():
    redactor = offline_smoke.Redactor()
    redactor.add("synthetic-private-session-cookie")

    result = redactor.clean(
        "Cookie: synthetic-private-session-cookie "
        "/access#another-session-value-12345678901234567890"
    )

    assert "synthetic-private-session-cookie" not in result
    assert "another-session-value" not in result
    assert "[REDACTED]" in result


def test_failed_non_sensitive_command_logs_bounded_redacted_stderr_without_stdout(
    monkeypatch, tmp_path
):
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    harness.log_handle = io.StringIO()
    secret = "synthetic-private-diagnostic-token"
    harness.redactor.add(secret)
    stderr = f"Authorization: Bearer {secret}\ncompose failure: " + ("x" * 1800)

    def command_double(command, **_kwargs):
        return offline_smoke.subprocess.CompletedProcess(
            command, 1, "private auth transcript stdout", stderr
        )

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    with pytest.raises(offline_smoke.SmokeFailure, match="exited with status 1"):
        harness.run_command(["docker", "compose", "up"], label="force-recreate")

    log = harness.log_handle.getvalue()
    assert "compose failure" in log
    assert "[REDACTED]" in log
    assert secret not in log
    assert "private auth transcript stdout" not in log
    diagnostic = next(
        line.split("stderr: ", 1)[1] for line in log.splitlines() if "stderr: " in line
    )
    assert len(diagnostic) <= offline_smoke.MAX_STDERR_DIAGNOSTIC_CHARS
    assert diagnostic.endswith("… [truncated]")


def test_failed_sensitive_command_keeps_output_suppressed(monkeypatch, tmp_path):
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    harness.log_handle = io.StringIO()
    sensitive = "secret fixture and transcript data"

    def command_double(command, **_kwargs):
        return offline_smoke.subprocess.CompletedProcess(command, 1, sensitive, sensitive)

    monkeypatch.setattr(offline_smoke.subprocess, "run", command_double)
    with pytest.raises(offline_smoke.SmokeFailure, match="exited with status 1"):
        harness.run_command(
            ["docker", "compose", "exec"], label="sensitive fixture read", sensitive_output=True
        )

    log = harness.log_handle.getvalue()
    assert "output suppressed" in log
    assert "stderr:" not in log
    assert sensitive not in log


def _valid_connected_provider_fixture():
    pin = {
        "provider": "chatgpt",
        "connection_version": 17,
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
    }
    return {
        "connection_status": "connected",
        "provider_view_status": "connected",
        "fixture_session_status": "connected",
        "client_id_valid": True,
        "direct_scope_present": True,
        "token_expiry_valid": True,
        "access_token_sha256": "a" * 64,
        "refresh_token_sha256": "b" * 64,
        "state_sha256": "c" * 64,
        "state_bytes": 400,
        "connection_version": 17,
        "selected_model": "gpt-6.1-sol",
        "selected_reasoning_effort": "high",
        "notes_task_pin": pin,
    }


def test_connected_provider_evidence_accepts_complete_local_fixture():
    fixture = _valid_connected_provider_fixture()
    assert offline_smoke.validate_connected_provider_fixture(fixture) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("connection_status", "reconnect_required"), ("direct_scope_present", False)],
)
def test_connected_provider_evidence_rejects_reconnect_required_or_missing_scope(field, value):
    fixture = _valid_connected_provider_fixture()
    fixture[field] = value

    with pytest.raises(
        offline_smoke.SmokeFailure,
        match="does not prove a valid connected provider session",
    ):
        offline_smoke.validate_connected_provider_fixture(fixture)


def test_seed_provider_fixture_executes_seed_and_reopen_scripts_locally(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    auth_dir = tmp_path / "auth"
    provider_dir = tmp_path / "provider"
    for directory in (data_dir, auth_dir, provider_dir):
        directory.mkdir()

    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )
    harness = offline_smoke.SmokeHarness(options)
    script_runs = []

    def run_locally(service, script, *, label, env_values=None, timeout=60, **_kwargs):
        assert service == "app"
        script_runs.append(label)
        environment = {
            "PATH": offline_smoke.os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(ROOT / "src"),
            "ASR_DATA_DIR": str(data_dir),
            "ASR_AUTH_DIR": str(auth_dir),
            "ASR_PROVIDER_DIR": str(provider_dir),
            "ASR_PUBLIC_URL": "http://127.0.0.1:8765",
        }
        environment.update(env_values or {})
        result = offline_smoke.subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        value = json.loads(result.stdout)
        assert isinstance(value, dict)
        return value

    monkeypatch.setattr(harness, "container_python", run_locally)

    fixture = harness._seed_provider_fixture()

    assert script_runs == [
        "seed valid synthetic connected provider session",
        "verify local connected provider session and credentials",
    ]
    assert fixture["connection_status"] == "connected"
    assert fixture["provider_view_status"] == "connected"
    assert fixture["fixture_session_status"] == "connected"
    assert fixture["notes_task_pin"] == {
        "provider": "chatgpt",
        "connection_version": 17,
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
    }


def _write_prepared_models(root: Path) -> None:
    asr = root / offline_smoke.ASR_MODEL_NAME
    diarization = root / offline_smoke.DIARIZATION_MODEL_NAME
    for relative in offline_smoke.ASR_REQUIRED_FILES:
        path = asr / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "tokenizer.json":
            path.write_text(json.dumps({"model": {"type": "BPE"}}), encoding="utf-8")
        elif relative == "config.json":
            path.write_text(
                json.dumps({"lang_ids": {}, "suppress_ids": [], "suppress_ids_begin": []}),
                encoding="utf-8",
            )
        elif relative == "preprocessor_config.json":
            path.write_text(
                json.dumps(
                    {
                        "feature_size": 80,
                        "sampling_rate": 16000,
                        "hop_length": 160,
                        "n_fft": 400,
                        "chunk_length": 30,
                    }
                ),
                encoding="utf-8",
            )
        else:
            path.write_bytes(b"prepared-asr-model-artifact")
    for relative in offline_smoke.DIARIZATION_REQUIRED_FILES:
        path = diarization / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"prepared-community-model-artifact")


def _write_short_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 48_000)


def test_input_validation_requires_prepared_models_and_short_local_wav(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    _write_prepared_models(models)
    audio = tmp_path / "synthetic.wav"
    _write_short_wav(audio)
    options = offline_smoke.SmokeOptions(
        image="asr-en-vi:local",
        models=models,
        audio=audio,
        output=tmp_path / "output",
        mode="offline",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )

    asr_dir, diarization_dir, duration_ms, audio_digest = offline_smoke.validate_inputs(options)

    assert asr_dir == models / offline_smoke.ASR_MODEL_NAME
    assert diarization_dir == models / offline_smoke.DIARIZATION_MODEL_NAME
    assert duration_ms == 3000
    assert len(audio_digest) == 64
    assert offline_smoke._artifact_identity(asr_dir)["file_count"] == len(
        offline_smoke.ASR_REQUIRED_FILES
    )


def test_pull_mode_rejects_nonpublic_registry_reference(tmp_path):
    options = offline_smoke.SmokeOptions(
        image="registry.example.invalid/asr-en-vi:v0.1.0-rc.1",
        models=tmp_path / "models",
        audio=tmp_path / "synthetic.wav",
        output=tmp_path / "output",
        mode="pull",
        project_prefix="asr-offline-smoke",
        task_timeout=60,
        startup_timeout=30,
    )

    with pytest.raises(offline_smoke.SmokeFailure, match="public ghcr.io"):
        offline_smoke.validate_inputs(options)


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/nguyencanhtrung/asr-en-vifoobar:v0.1.0-rc.1",
        "ghcr.io/nguyencanhtrung/asr-en-vi:latest",
        "ghcr.io/nguyencanhtrung/asr-en-vi@sha256:abcd",
    ],
)
def test_pull_mode_rejects_noncanonical_public_refs(image):
    with pytest.raises(offline_smoke.SmokeFailure):
        offline_smoke.validate_pull_image(image)


def test_pull_mode_accepts_versioned_public_tag_and_sha256_digest():
    offline_smoke.validate_pull_image("ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0-rc.1")
    offline_smoke.validate_pull_image("ghcr.io/nguyencanhtrung/asr-en-vi@sha256:" + "a" * 64)
