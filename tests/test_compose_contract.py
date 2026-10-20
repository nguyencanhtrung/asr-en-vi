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
    assert "provider:/var/lib/asr-en-vi/provider" in app["volumes"]
    assert "provider:/var/lib/asr-en-vi/provider" in worker["volumes"]
    assert app["environment"]["ASR_PROVIDER_DIR"] == "/var/lib/asr-en-vi/provider"
    assert worker["environment"]["ASR_PROVIDER_DIR"] == "/var/lib/asr-en-vi/provider"
    assert "--no-access-log" in app["command"]
    assert app["image"] == worker["image"]
    assert app["environment"]["ASR_MAX_UPLOAD_BYTES"] == "${ASR_MAX_UPLOAD_BYTES:-4294967296}"
    assert app["environment"]["ASR_MAX_RECORDING_SECONDS"] == (
        "${ASR_MAX_RECORDING_SECONDS:-14400}"
    )
    assert "ASR_MODEL_PATH" not in app["environment"]
    assert worker["environment"]["ASR_DEVICE"] == "${ASR_DEVICE:-auto}"
    assert worker["environment"]["ASR_GPU_MODEL_PATH"].endswith("whisper-large-v3}")
    assert worker["environment"]["ASR_CPU_MODEL_PATH"].endswith("whisper-small}")
    assert worker["environment"]["ASR_DIARIZATION_MODEL_PATH"].endswith(
        "speaker-diarization-community-1}"
    )
    assert app["environment"]["ASR_DIARIZATION_MODEL_PATH"].endswith(
        "speaker-diarization-community-1}"
    )
    assert "HF_TOKEN" not in app["environment"] and "HF_TOKEN" not in worker["environment"]
    assert "gpus" not in worker
    gpu_override = yaml.safe_load((ROOT / "compose.gpu.yaml").read_text(encoding="utf-8"))
    assert gpu_override["services"]["worker"]["gpus"] == "all"
    assert any(mount.endswith(":/models:ro") for mount in app["volumes"])
    assert any(mount.endswith(":/models:ro") for mount in worker["volumes"])
    assert app["healthcheck"]
    assert worker["healthcheck"]


def test_provider_volume_is_created_for_runtime_uid_and_default_server_suppresses_access_logs():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "/var/lib/asr-en-vi/provider" in dockerfile
    assert (
        "chmod 0700 /var/lib/asr-en-vi/data /var/lib/asr-en-vi/auth /var/lib/asr-en-vi/provider"
        in dockerfile
    )
    assert '"--no-access-log"]' in dockerfile
    assert "ARG OMP_VERSION=18.5.0" in dockerfile
    assert "b8413e6e085a423c7a9b1d7bc025c2af794923b6b6c57330a309639b6176c8a1" in dockerfile
    assert "1244860c58bb68a3a45390d4932e5c7983183ec8c12cb6848c1afd709de38a07" in dockerfile
    assert "COPY --from=omp-bin /usr/local/bin/omp /usr/local/bin/omp" in dockerfile


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
    assert "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04" in dockerfile
    assert "libpython3.12" in dockerfile
    assert "faster-whisper==1.2.1" in pyproject
    assert '"av>=11,<19"' in pyproject
    assert not (ROOT / "requirements-asr.txt").exists()
    assert "COPY src/ ./src/" in dockerfile
    assert "prototype" not in dockerfile
    assert "docs/" not in dockerfile
    assert "/models/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_example_environment_selects_hardware_profiles_automatically():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "ASR_DEVICE=auto" in example.splitlines()
    assert "ASR_GPU_MODEL_PATH=/models/whisper-large-v3" in example.splitlines()
    assert "ASR_CPU_MODEL_PATH=/models/whisper-small" in example.splitlines()
    assert "ASR_GPU_COMPUTE_TYPE=float16" in example.splitlines()
    assert "ASR_CPU_COMPUTE_TYPE=int8" in example.splitlines()
    assert (
        "ASR_DIARIZATION_MODEL_PATH=/models/speaker-diarization-community-1" in example.splitlines()
    )


def test_status_badge_sizes_only_its_dot_and_runtime_details_have_ui_targets():
    stylesheet = (ROOT / "src/asr_en_vi/web/shell.css").read_text(encoding="utf-8")
    markup = (ROOT / "src/asr_en_vi/web/shell.html").read_text(encoding="utf-8")
    script = (ROOT / "src/asr_en_vi/web/history.js").read_text(encoding="utf-8")

    assert ".saved-badge > span:first-child" in stylesheet
    assert ".saved-badge > span," not in stylesheet
    assert 'id="runtime-backend"' in markup
    assert 'id="runtime-model"' in markup
    assert "#runtime-backend" in script
    assert "#runtime-model" in script


def test_language_choice_is_presented_as_a_hint_not_an_output_constraint():
    markup = (ROOT / "src/asr_en_vi/web/shell.html").read_text(encoding="utf-8")
    script = (ROOT / "src/asr_en_vi/web/history.js").read_text(encoding="utf-8")

    assert markup.count("Gợi ý ngôn ngữ") >= 3
    assert "Ngôn ngữ chính" not in markup
    assert "`Gợi ý: ${" in script


def test_worker_grace_period_exceeds_runner_worst_case_stop_time():
    from asr_en_vi import worker as worker_module

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    grace = compose["services"]["worker"]["stop_grace_period"]
    worst_case = worker_module.RUNNER_TERM_GRACE_SECONDS + worker_module.RUNNER_KILL_GRACE_SECONDS

    assert grace.endswith("s")
    assert float(grace.removesuffix("s")) >= worst_case + 5


def test_start_preflight_maps_the_configured_container_diarization_path_to_the_host_mount():
    script = (ROOT / "scripts/start.sh").read_text(encoding="utf-8")

    assert "ASR_DIARIZATION_MODEL_PATH=" in script
    assert "${diarization_container_path#/models/}" in script
    assert "ASR_DIARIZATION_MODEL_PATH must be below /models" in script
    assert "embedding/pytorch_model.bin" in script
    assert "plda/xvec_transform.npz" in script
    assert "segmentation/pytorch_model.bin" in script


def test_claimed_task_starting_stage_has_a_vietnamese_label():
    script = (ROOT / "src/asr_en_vi/web/history.js").read_text(encoding="utf-8")
    labels = script.split("const TASK_STAGES = {", 1)[1].split("};", 1)[0]

    assert '    starting: "Đang bắt đầu",' in labels
