from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from asr_studio import antigravity
from asr_studio.antigravity import (
    _CONTEXT_AUTOLOAD_MARKERS,
    ANTIGRAVITY_PROVIDER_ID,
    OMP_VERSION,
    RPC_SYSTEM_PROMPT,
    AntigravityError,
    AntigravityProvider,
    OmpRpcAdapter,
    _RpcClient,
)

_RUN_CONTRACT = os.environ.get("ASR_RUN_OMP_CONTRACT") == "1"
pytestmark = pytest.mark.skipif(
    not _RUN_CONTRACT,
    reason="set ASR_RUN_OMP_CONTRACT=1 to run the real OMP contract",
)

if _RUN_CONTRACT:
    _omp_executable = shutil.which("omp")
    if _omp_executable is None:
        pytest.fail("ASR_RUN_OMP_CONTRACT=1 requires the omp executable on PATH.")
    _version = subprocess.run(
        [_omp_executable, "--version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    _version_output = _version.stdout.strip()
    if _version.returncode != 0:
        pytest.fail(
            "ASR_RUN_OMP_CONTRACT=1 could not read omp --version: "
            f"{(_version.stderr or _version.stdout).strip()!r}"
        )
    if _version_output != f"omp/{OMP_VERSION}":
        pytest.fail(f"OMP contract requires omp/{OMP_VERSION}; found {_version_output!r}.")
else:
    _omp_executable = "omp"


class ContractOmpRpcAdapter(OmpRpcAdapter):
    @property
    def environment(self) -> dict[str, str]:
        environment = super().environment
        environment["OPENAI_API_KEY"] = "sk-omp-contract-dummy"
        return environment


def _adapter(directory: Path) -> ContractOmpRpcAdapter:
    return ContractOmpRpcAdapter(directory, executable=_omp_executable)


def _prompt_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_prompt_text(item) for item in value)
    raise AssertionError(f"unexpected system prompt value: {value!r}")


def _state(adapter: ContractOmpRpcAdapter) -> dict[str, Any]:
    with _RpcClient(adapter) as client:
        state = client.request({"type": "get_state"})
    assert isinstance(state, dict)
    return state


def test_clean_startup_state_is_pinned(tmp_path):
    state = _state(_adapter(tmp_path / "clean"))

    assert state["dumpTools"] == []
    system_prompt = state["systemPrompt"]
    assert isinstance(system_prompt, list)
    assert len(system_prompt) == 2
    assert all(isinstance(item, str) for item in system_prompt)
    assert system_prompt[0] == RPC_SYSTEM_PROMPT
    assert "coding assistant" not in _prompt_text(system_prompt)


def test_context_files_above_adapter_directory_are_not_loaded(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    sentinel = "OMP_PARENT_CONTEXT_MUST_NOT_REACH_WORKSPACE"
    for filename in ("AGENTS.md", "CLAUDE.md"):
        (parent / filename).write_text(sentinel, encoding="utf-8")

    adapter = _adapter(parent / "provider" / "omp")
    state = _state(adapter)

    assert (adapter.workspace_dir / ".git").is_dir()
    assert sentinel not in _prompt_text(state["systemPrompt"])


@pytest.mark.parametrize("location", ("workspace", "agent"))
def test_context_files_inside_isolation_root_fail_closed(tmp_path, monkeypatch, location):
    adapter = _adapter(tmp_path / location)
    adapter.prepare()
    target = adapter.workspace_dir if location == "workspace" else adapter.agent_dir
    sentinel = f"OMP_{location.upper()}_CONTEXT_SENTINEL"
    (target / "AGENTS.md").write_text(sentinel, encoding="utf-8")

    observed_prompts: list[Any] = []
    original_check = antigravity._system_prompt_contains_context

    def observe_prompt(system_prompt: Any) -> bool:
        observed_prompts.append(system_prompt)
        return original_check(system_prompt)

    monkeypatch.setattr(antigravity, "_system_prompt_contains_context", observe_prompt)
    with pytest.raises(AntigravityError) as failure, _RpcClient(adapter):
        pass

    assert failure.value.code == "omp_invalid_runtime"
    assert len(observed_prompts) == 1
    prompt_text = _prompt_text(observed_prompts[0])
    assert sentinel in prompt_text
    normalized_prompt = prompt_text.casefold()
    assert all(marker.casefold() in normalized_prompt for marker in _CONTEXT_AUTOLOAD_MARKERS)


def test_unknown_model_frame_maps_to_model_unavailable(tmp_path):
    frames: list[dict[str, Any]] = []
    adapter = _adapter(tmp_path / "unknown-model")
    with _RpcClient(adapter) as client, pytest.raises(AntigravityError) as failure:
        client.request(
            {
                "type": "set_model",
                "provider": ANTIGRAVITY_PROVIDER_ID,
                "modelId": "omp-contract-unknown-model",
            },
            frame_handler=frames.append,
        )

    frame = next(frame for frame in frames if frame.get("command") == "set_model")
    assert frame["type"] == "response"
    assert frame["command"] == "set_model"
    assert frame["success"] is False
    assert isinstance(frame["error"], str)
    assert failure.value.code == "model_unavailable"


@pytest.mark.parametrize("level", ("high", "medium"))
def test_set_thinking_level_is_confirmed_by_get_state(tmp_path, level):
    with _RpcClient(_adapter(tmp_path / f"thinking-{level}")) as client:
        client.request({"type": "set_thinking_level", "level": level})
        state = client.request({"type": "get_state"})

    assert state["thinkingLevel"] == level


def test_logout_without_credential_and_disconnect_report_contract(tmp_path):
    assert _adapter(tmp_path / "logout").logout() is True

    provider = AntigravityProvider(
        tmp_path / "provider",
        adapter=_adapter(tmp_path / "provider-omp"),
    )
    provider.ensure()
    assert provider.disconnect() == {
        "status": "disconnected",
        "remote_revocation_confirmed": False,
    }
