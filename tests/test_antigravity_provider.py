# ruff: noqa: E501 -- the embedded fake OMP script keeps its JSON frames readable.
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from asr_en_vi.antigravity import (
    ANTIGRAVITY_PROVIDER_ID,
    AntigravityError,
    AntigravityProvider,
    LoginInteraction,
    OmpRpcAdapter,
    _system_prompt_contains_context,
    omp_runtime_contract,
)


class FakeAntigravityAdapter:
    def __init__(self, *, needs_input: bool = False) -> None:
        self.needs_input = needs_input
        self.answers: list[str] = []
        self.verify_calls: list[str] = []
        self.logout_calls = 0
        self.login_release = threading.Event()
        self.models = [
            {
                "provider": ANTIGRAVITY_PROVIDER_ID,
                "id": "gemini-3-pro-high",
                "name": "Gemini 3 Pro High",
            },
            {"provider": "google", "id": "gemini-api", "name": "Wrong provider"},
        ]

    def login(self, interaction: LoginInteraction) -> None:
        interaction.publish(
            {
                "authorization_url": "https://accounts.google.com/o/oauth2/auth?state=test",
                "instructions": "Continue in your browser.",
            }
        )
        if self.needs_input:
            interaction.publish({"input_request_id": "ui-1", "input_prompt": "Paste code"})
            self.answers.append(interaction.wait_for_answer(5))
        while not self.login_release.wait(0.01):
            if interaction.cancel_event.is_set():
                raise AntigravityError(409, "login_cancelled", "cancelled")

    def list_models(self):
        return self.models

    def verify(self, model: str):
        self.verify_calls.append(model)
        return {"ok": True}

    def logout(self):
        self.logout_calls += 1
        return True


def wait_for_status(provider: AntigravityProvider, session_id: str, expected: str) -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        session = provider.login_session(session_id)
        if session["status"] == expected:
            return session
        time.sleep(0.01)
    raise AssertionError(f"session did not become {expected}")


def test_login_catalog_preference_verification_restart_and_disconnect(tmp_path):
    adapter = FakeAntigravityAdapter()
    provider = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    provider.ensure()

    started = provider.start_login()
    assert started["status"] in {"pending", "connected"}
    assert started.get("authorization_url") == (
        "https://accounts.google.com/o/oauth2/auth?state=test"
    )
    adapter.login_release.set()
    wait_for_status(provider, started["id"], "connected")
    assert provider.provider_view() == {
        "id": "antigravity",
        "status": "connected",
        "account": {"label": "Google Antigravity"},
        "connection_version": 1,
        "verification": None,
    }

    catalog = provider.list_models()
    assert catalog == {
        "models": [{"id": "gemini-3-pro-high", "display_name": "Gemini 3 Pro High"}],
        "selected_model": None,
    }
    assert provider.set_preference("gemini-3-pro-high") == {
        "provider": "antigravity",
        "model": "gemini-3-pro-high",
    }
    verified = provider.verify("gemini-3-pro-high")
    assert verified["output"] == {"ok": True}
    assert adapter.verify_calls == ["gemini-3-pro-high"]

    restarted = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    restarted.ensure()
    assert restarted.provider_view()["status"] == "connected"
    assert restarted.list_models()["selected_model"] == "gemini-3-pro-high"

    assert restarted.disconnect() == {
        "status": "disconnected",
        "remote_revocation_confirmed": True,
    }
    assert adapter.logout_calls == 1
    assert restarted.provider_view()["status"] == "disconnected"


def test_login_can_request_non_secret_code_and_be_cancelled(tmp_path):
    adapter = FakeAntigravityAdapter(needs_input=True)
    provider = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    provider.ensure()

    started = provider.start_login()
    deadline = time.monotonic() + 2
    while not provider.login_session(started["id"])["input_prompt"]:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    provider.submit_login_input(started["id"], "redirect-code")
    adapter.login_release.set()
    wait_for_status(provider, started["id"], "connected")
    assert adapter.answers == ["redirect-code"]

    adapter.login_release.clear()
    pending = provider.start_login()
    cancelled = provider.cancel_login(pending["id"])
    assert cancelled["status"] == "cancelled"


def test_login_persists_connection_before_publishing_connected_session(tmp_path, monkeypatch):
    adapter = FakeAntigravityAdapter()
    provider = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    provider.ensure()
    original_write = provider.store._write
    statuses_at_write: list[str] = []

    def record_session_status_before_write(state):
        statuses_at_write.extend(session.status for session in provider._sessions.values())
        original_write(state)

    monkeypatch.setattr(provider.store, "_write", record_session_status_before_write)
    started = provider.start_login()
    adapter.login_release.set()

    connected = wait_for_status(provider, started["id"], "connected")

    assert statuses_at_write == ["pending"]
    assert connected["status"] == "connected"
    assert provider.provider_view()["status"] == "connected"


def test_login_store_failure_becomes_failed_session(tmp_path, monkeypatch):
    adapter = FakeAntigravityAdapter()
    provider = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    provider.ensure()

    def fail_write(state):
        raise OSError("private storage failure")

    monkeypatch.setattr(provider.store, "_write", fail_write)
    started = provider.start_login()
    adapter.login_release.set()

    failed = wait_for_status(provider, started["id"], "failed")

    assert failed["error"] == {
        "code": "provider_unavailable",
        "message": "Google Antigravity could not be reached.",
    }
    assert "private storage failure" not in str(failed)
    assert provider.provider_view()["status"] == "disconnected"


def test_runner_contract_is_isolated_and_disables_agent_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/personal/claude")
    monkeypatch.setenv("OPENAI_API_KEY", "personal-secret")
    adapter = OmpRpcAdapter(tmp_path / "omp", executable="/usr/local/bin/omp")
    adapter.prepare()
    contract = omp_runtime_contract(tmp_path / "omp")

    for flag in (
        "--no-ui",
        "--no-session",
        "--no-tools",
        "--no-lsp",
        "--no-pty",
        "--no-extensions",
        "--no-skills",
        "--no-rules",
    ):
        assert flag in contract["command"]
    assert contract["version"] == "18.5.0"
    assert "CLAUDE_CONFIG_DIR" not in adapter.environment
    assert "OPENAI_API_KEY" not in adapter.environment
    assert adapter.environment["HOME"] == str(adapter.home_dir)
    config = adapter.config_path.read_text(encoding="utf-8")
    assert "compaction:\n  enabled: false" in config
    assert "retry:\n  enabled: false\n  modelFallback: false" in config
    assert "mcp:\n  enabled: false" in config
    assert "memory:\n  backend: off" in config
    assert (adapter.workspace_dir / ".git").is_dir()
    assert os.stat(adapter.directory).st_mode & 0o777 == 0o700
    assert os.stat(adapter.config_path).st_mode & 0o777 == 0o600


def test_invalid_model_and_disconnected_catalog_fail_without_calling_adapter(tmp_path):
    adapter = FakeAntigravityAdapter()
    provider = AntigravityProvider(tmp_path / "provider", adapter=adapter)
    provider.ensure()

    with pytest.raises(AntigravityError) as disconnected:
        provider.list_models()
    assert disconnected.value.code == "provider_disconnected"
    with pytest.raises(AntigravityError) as invalid:
        provider.verify("bad model with spaces")
    assert invalid.value.code == "invalid_model"


def test_real_rpc_transport_handles_login_catalog_and_synthetic_inference(tmp_path):
    executable = tmp_path / "fake-omp"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

agent_dir = Path(os.environ["PI_CODING_AGENT_DIR"])
authenticated = agent_dir / "authenticated"
if sys.argv[1:4] == ["auth-broker", "login", "google-antigravity"]:
    print("Open this URL in your browser:", flush=True)
    print("https://accounts.google.com/auth", flush=True)
    print("Complete the sign-in in your browser.", flush=True)
    answer = input("Paste the authorization code (or full redirect URL): ")
    if answer != "test-code":
        raise SystemExit(3)
    agent_dir.mkdir(parents=True, exist_ok=True)
    authenticated.write_text("ok", encoding="utf-8")
    raise SystemExit(0)
if sys.argv[1:4] == ["auth-broker", "logout", "google-antigravity"]:
    authenticated.unlink(missing_ok=True)
    raise SystemExit(0)
if not authenticated.exists():
    print("No models available. Use /login.", file=sys.stderr, flush=True)
    raise SystemExit(1)
required = {
    "--mode", "rpc", "--no-ui", "--no-session", "--no-tools", "--no-lsp",
    "--no-pty", "--no-extensions", "--no-skills", "--no-rules",
}
if not required.issubset(set(sys.argv[1:])):
    raise SystemExit(2)
print(json.dumps({"type": "ready"}), flush=True)
for line in sys.stdin:
    command = json.loads(line)
    request_id = command.get("id")
    command_type = command.get("type")
    data = None
    if command_type == "get_state":
        data = {"dumpTools": [], "autoCompactionEnabled": False}
    elif command_type == "get_available_models":
        data = {"models": [{"provider": "google-antigravity", "id": "gemini-test", "name": "Gemini Test"}]}
    elif command_type == "set_model":
        data = {"provider": "google-antigravity", "id": command["modelId"], "name": "Gemini Test"}
    elif command_type == "prompt":
        print(json.dumps({"id": request_id, "type": "response", "command": "prompt", "success": True, "data": {"agentInvoked": True}}), flush=True)
        print(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "{\\\"ok\\\":true}"}]}}), flush=True)
        print(json.dumps({"type": "prompt_result", "id": request_id, "agentInvoked": True, "status": "completed", "sessionSettled": True}), flush=True)
        continue
    print(json.dumps({"id": request_id, "type": "response", "command": command_type, "success": True, "data": data}), flush=True)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    adapter = OmpRpcAdapter(tmp_path / "omp", executable=str(executable))
    events = []
    interaction = LoginInteraction(threading.Event(), time.time() + 10, events.append)

    login_thread = threading.Thread(target=adapter.login, args=(interaction,))
    login_thread.start()
    deadline = time.monotonic() + 2
    while not any("input_prompt" in event for event in events):
        assert time.monotonic() < deadline
        time.sleep(0.01)
    interaction.answer("test-code")
    login_thread.join(timeout=2)
    assert not login_thread.is_alive()
    assert events[0]["authorization_url"] == "https://accounts.google.com/auth"
    assert adapter.list_models()[0]["id"] == "gemini-test"
    assert adapter.verify("gemini-test") == {"ok": True}
    assert adapter.logout() is True


def test_rpc_context_discovery_stops_before_planted_parent_instructions(tmp_path):
    parent = tmp_path / "project"
    parent.mkdir()
    marker = "PARENT_CONTEXT_MUST_NOT_REACH_OMP"
    (parent / "AGENTS.md").write_text(marker, encoding="utf-8")
    executable = tmp_path / "fake-omp-context-discovery"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

current = Path.cwd()
loaded = []
while True:
    for name in ("AGENTS.md", "CLAUDE.md"):
        candidate = current / name
        if candidate.is_file():
            loaded.append(candidate.read_text(encoding="utf-8"))
    if (current / ".git").exists() or current.parent == current:
        break
    current = current.parent
system_prompt = ["base OMP prompt", "isolated workspace prompt"]
if loaded:
    system_prompt.append("<repo-rules> Context files above auto-loaded: " + " ".join(loaded))
print(json.dumps({"type": "ready"}), flush=True)
for line in sys.stdin:
    command = json.loads(line)
    command_type = command.get("type")
    data = None
    if command_type == "get_state":
        data = {"dumpTools": [], "systemPrompt": system_prompt}
    elif command_type == "get_available_models":
        data = {"models": [{"provider": "google-antigravity", "id": "gemini-test", "name": "Gemini Test"}]}
    print(json.dumps({
        "id": command.get("id"), "type": "response", "command": command_type,
        "success": True, "data": data,
    }), flush=True)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    adapter = OmpRpcAdapter(parent / "provider" / "omp", executable=str(executable))

    assert adapter.list_models()[0]["id"] == "gemini-test"
    assert (adapter.workspace_dir / ".git").is_dir()


@pytest.mark.parametrize(
    "system_prompt",
    [
        "prefix <repo-rules> planted context suffix",
        "Context files above auto-loaded: /parent/AGENTS.md",
        ["base OMP prompt", "prefix <repo-rules> planted context suffix"],
        ["base OMP prompt", ["Context files above auto-loaded: /parent/AGENTS.md"]],
    ],
)
def test_rpc_rejects_auto_loaded_context_markers(tmp_path, system_prompt):
    executable = tmp_path / "fake-omp-context-leak"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys

system_prompt = __SYSTEM_PROMPT__
print(json.dumps({"type": "ready"}), flush=True)
for line in sys.stdin:
    command = json.loads(line)
    data = {"dumpTools": [], "systemPrompt": system_prompt} if command.get("type") == "get_state" else None
    print(json.dumps({
        "id": command.get("id"), "type": "response", "command": command.get("type"),
        "success": True, "data": data,
    }), flush=True)
""".replace("__SYSTEM_PROMPT__", repr(system_prompt)),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    adapter = OmpRpcAdapter(tmp_path / "omp-context-leak", executable=str(executable))

    with pytest.raises(AntigravityError) as failure:
        adapter.list_models()

    assert failure.value.code == "omp_invalid_runtime"


def test_rpc_rejects_malformed_or_oversized_system_prompt_shapes():
    deeply_nested = "safe"
    for _ in range(9):
        deeply_nested = [deeply_nested]

    for system_prompt in (
        {"text": "private malformed prompt"},
        ["safe", 7],
        deeply_nested,
        ["x" * (256 * 1024 + 1)],
    ):
        with pytest.raises(AntigravityError) as failure:
            _system_prompt_contains_context(system_prompt)

        assert failure.value.code == "omp_invalid_runtime"
        assert "private malformed prompt" not in str(failure.value)


def test_connection_ui_exposes_antigravity_login_model_and_verification_controls():
    root = Path(__file__).parents[1]
    markup = (root / "src/asr_en_vi/web/shell.html").read_text(encoding="utf-8")
    script = (root / "src/asr_en_vi/web/antigravity.js").read_text(encoding="utf-8")

    for element_id in (
        "antigravity-sign-in",
        "antigravity-login-link",
        "antigravity-input-form",
        "antigravity-model",
        "antigravity-verify",
        "antigravity-disconnect",
    ):
        assert f'id="{element_id}"' in markup
        assert f"#{element_id}" in script
    assert "/api/providers/antigravity/login-sessions" in script
    assert "/api/providers/antigravity/models" in script
    assert "/api/providers/antigravity/verify" in script


@pytest.mark.parametrize(
    ("diagnostic", "expected_code", "expected_status"),
    [
        (
            "OAuth refresh token revoked",
            "reconnect_required",
            "reconnect_required",
        ),
        (
            "OAuth error: Token has been expired",
            "reconnect_required",
            "reconnect_required",
        ),
        ("OMP internal startup failure", "provider_unavailable", "connected"),
    ],
)
def test_rpc_startup_failure_classifies_auth_without_exposing_diagnostics(
    tmp_path, diagnostic, expected_code, expected_status
):
    executable = tmp_path / "fake-omp-startup-failure"
    executable.write_text(
        """#!/usr/bin/env python3
import sys
sys.stderr.write("x" * 70000 + __DIAGNOSTIC__ + " secret=private-startup-value")
sys.stderr.flush()
raise SystemExit(1)
""".replace("__DIAGNOSTIC__", repr(diagnostic)),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    adapter = OmpRpcAdapter(tmp_path / "omp-startup-failure", executable=str(executable))
    provider = AntigravityProvider(tmp_path / "provider-startup-failure", adapter=adapter)
    provider.ensure()
    with provider.store.locked(write=True) as state:
        state["connection_status"] = "connected"
        state["connection_version"] = 7
        state["verification"] = {"model": "gemini-test"}

    with pytest.raises(AntigravityError) as failure:
        provider.verify("gemini-test")

    assert failure.value.code == expected_code
    assert "private-startup-value" not in str(failure.value)
    assert "private-startup-value" not in failure.value.public_message
    assert provider.provider_view()["status"] == expected_status
    with provider.store.locked() as state:
        if expected_status == "reconnect_required":
            assert state["connection_version"] == 8
            assert state["verification"] is None
        else:
            assert state["connection_version"] == 7
            assert state["verification"] == {"model": "gemini-test"}


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_status"),
    [
        (
            {
                "httpStatus": 403,
                "code": "invalid_grant",
                "message": "refresh token revoked; secret=private-rpc-value",
            },
            "reconnect_required",
            "reconnect_required",
        ),
        (
            {"httpStatus": 429, "code": "quota_exceeded", "message": "try later"},
            "provider_quota",
            "connected",
        ),
        (
            {
                "httpStatus": 403,
                "code": "model_access_denied",
                "provider": "google-antigravity",
                "model": "gemini-restricted",
                "message": "selected model is not entitled for this account",
            },
            "model_unavailable",
            "connected",
        ),
        (
            {
                "httpStatus": 403,
                "code": "permission_denied",
                "provider": "google-antigravity",
                "model": "gemini-restricted",
                "message": "access denied; secret=private-rpc-value",
            },
            "provider_unavailable",
            "connected",
        ),
        (
            {
                "httpStatus": 403,
                "code": "forbidden",
                "provider": "google-antigravity",
                "model": "gemini-test",
                "message": "unknown provider failure; secret=private-rpc-value",
            },
            "provider_unavailable",
            "connected",
        ),
    ],
)
def test_synthetic_inference_classifies_structured_errors_safely(
    tmp_path, error, expected_code, expected_status
):
    executable = tmp_path / "fake-omp-inference-error"
    error_json = json.dumps(error, separators=(",", ":"))
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys

error = __ERROR__
print(json.dumps({"type": "ready"}), flush=True)
for line in sys.stdin:
    command = json.loads(line)
    request_id = command.get("id")
    command_type = command.get("type")
    if command_type == "get_state":
        data = {"dumpTools": []}
    elif command_type in {"set_auto_compaction", "set_auto_retry", "set_model"}:
        data = {}
    elif command_type == "prompt":
        print(json.dumps({
            "type": "response", "id": request_id, "command": "prompt",
            "success": True, "data": {"agentInvoked": True},
        }), flush=True)
        print(json.dumps({
            "type": "prompt_result", "id": request_id, "status": "failed",
            "error": error,
        }), flush=True)
        break
    else:
        data = None
    print(json.dumps({
        "type": "response", "id": request_id, "command": command_type,
        "success": True, "data": data,
    }), flush=True)
""".replace("__ERROR__", error_json),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    adapter = OmpRpcAdapter(tmp_path / "omp-inference-error", executable=str(executable))
    provider = AntigravityProvider(tmp_path / "provider-inference-error", adapter=adapter)
    provider.ensure()
    with provider.store.locked(write=True) as state:
        state["connection_status"] = "connected"
        state["connection_version"] = 3

    with pytest.raises(AntigravityError) as failure:
        provider.verify("gemini-test")

    assert failure.value.code == expected_code
    assert "private-rpc-value" not in str(failure.value)
    assert "private-rpc-value" not in failure.value.public_message
    assert provider.provider_view()["status"] == expected_status
    with provider.store.locked() as state:
        assert state["connection_version"] == (4 if expected_status == "reconnect_required" else 3)
