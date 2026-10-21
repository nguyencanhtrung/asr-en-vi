from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings

pytestmark = pytest.mark.browser
WEB_ROOT = Path(__file__).parents[1] / "src" / "asr_en_vi" / "web"


class LiveServer:
    def __init__(self, tmp_path):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self.url = f"http://127.0.0.1:{self.port}"
        self.settings = Settings(
            data_dir=tmp_path / "data",
            auth_dir=tmp_path / "auth",
            public_url=self.url,
        )
        self.sock = None
        self.server = None
        self.thread = None

    def start(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", self.port))
        sock.listen()
        self.sock = sock
        self.server = uvicorn.Server(
            uvicorn.Config(
                create_app(self.settings),
                log_config=None,
                log_level="warning",
                access_log=False,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [sock]},
            daemon=True,
        )
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.025)
        assert self.server.started, "test server did not start"

    def stop(self):
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=5)
        if self.sock:
            self.sock.close()

    @property
    def access_link(self):
        state = AuthStore(self.settings.auth_dir).load()
        return f"{self.url}/access#{state.token}"


class MockProviderApi:
    def __init__(self):
        self.status = "disconnected"
        self.account_label = "Tài khoản kiểm thử"
        self.verification = None
        self.preferences = {"provider": None, "models": {}, "reasoning_effort": "default"}
        self.models = [
            {
                "id": "gpt-6.1-sol",
                "display_name": "GPT 6.1 Sol",
                "reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
            },
            {
                "id": "gpt-6-luna",
                "display_name": "GPT 6 Luna",
                "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"],
            },
            {
                "id": "gpt-5.6-luna",
                "display_name": "GPT-5.6 Luna",
                "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"],
            },
        ]
        self.poll_statuses: list[str] = []
        self.next_expiry_seconds = 600
        self.login_start_error = None
        self.next_poll_error = None
        self.next_preference_error = None
        self.next_verification_401 = False
        self.provider_failure_operation = None
        self.provider_failure_code = "provider_auth_error"
        self.remote_revocation_confirmed = False
        self.sessions: dict[str, dict[str, str]] = {}
        self.session_count = 0
        self.antigravity_status = "disconnected"
        self.antigravity_session = None
        self.antigravity_polls = ["pending", "connected"]
        self.antigravity_selected_model = None
        self.antigravity_effort = "high"
        self.antigravity_verification = None
        self.antigravity_failure_operation = None
        self.antigravity_failure_code = "reconnect_required"
        self.antigravity_models = [
            {"id": "gemini-3-pro-high", "display_name": "Gemini 3 Pro High"},
            {"id": "claude-sonnet-test", "display_name": "Claude Sonnet Test"},
        ]
        self.calls: list[tuple[str, str, dict | None]] = []

    def fail_provider_operation(self, route, operation):
        if self.provider_failure_operation != operation:
            return False
        self.provider_failure_operation = None
        self.status = "reconnect_required"
        self.fulfill(
            route,
            {
                "detail": {
                    "code": self.provider_failure_code,
                    "message": "ChatGPT could not authenticate the current account.",
                }
            },
            status=409,
        )
        return True

    @staticmethod
    def fulfill(route, payload, status=200):
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        )

    def provider_payload(self):
        connected = self.status != "disconnected"
        return {
            "providers": [
                {
                    "id": "chatgpt",
                    "status": self.status,
                    "account": {"label": self.account_label} if connected else None,
                    "connection_version": 1 if connected else 0,
                    "verification": self.verification,
                },
                {
                    "id": "antigravity",
                    "status": self.antigravity_status,
                    "account": {"label": "Google Antigravity"}
                    if self.antigravity_status != "disconnected"
                    else None,
                    "connection_version": 1 if self.antigravity_status != "disconnected" else 0,
                    "verification": self.antigravity_verification,
                },
            ]
        }

    def route(self, route):
        request = route.request
        method = request.method
        path = urlparse(request.url).path
        body = request.post_data_json if request.post_data else None
        self.calls.append((method, path, body))

        if method == "GET" and path == "/api/providers":
            self.fulfill(route, self.provider_payload())
            return
        if method == "POST" and path == "/api/providers/antigravity/login-sessions":
            expires = datetime.now(UTC) + timedelta(minutes=10)
            self.antigravity_session = {
                "id": "antigravity-session",
                "status": "pending",
                "expires_at": expires.isoformat(),
                "error": None,
                "authorization_url": "https://accounts.google.com/o/oauth2/auth?state=test",
                "instructions": "Continue with Google.",
                "input_prompt": None,
            }
            self.fulfill(route, self.antigravity_session, status=201)
            return
        if path == "/api/providers/antigravity/login-sessions/antigravity-session":
            if self.antigravity_session is None:
                self.fulfill(
                    route,
                    {
                        "detail": {
                            "code": "login_session_not_found",
                            "message": "Antigravity sign-in session not found.",
                        }
                    },
                    status=404,
                )
                return
            if method == "DELETE":
                self.antigravity_session["status"] = "cancelled"
                self.fulfill(route, self.antigravity_session)
                return
            if method == "GET":
                status = self.antigravity_polls.pop(0) if self.antigravity_polls else "connected"
                self.antigravity_session["status"] = status
                if status == "connected":
                    self.antigravity_status = "connected"
                    self.antigravity_session.pop("authorization_url", None)
                    self.antigravity_session.pop("instructions", None)
                    self.antigravity_session.pop("input_prompt", None)
                self.fulfill(route, self.antigravity_session)
                return
        if method == "GET" and path == "/api/providers/antigravity/models":
            if self.antigravity_failure_operation == "models":
                self.antigravity_failure_operation = None
                self.antigravity_status = "reconnect_required"
                self.fulfill(
                    route,
                    {"detail": {"code": "reconnect_required", "message": "Reconnect."}},
                    status=409,
                )
                return
            self.fulfill(
                route,
                {
                    "models": self.antigravity_models,
                    "selected_model": self.antigravity_selected_model,
                    "reasoning_effort": self.antigravity_effort,
                },
            )
            return
        if method == "PUT" and path == "/api/providers/antigravity/preference":
            if self.antigravity_failure_operation == "preference":
                self.antigravity_failure_operation = None
                self.antigravity_status = (
                    "disconnected"
                    if self.antigravity_failure_code == "provider_disconnected"
                    else "reconnect_required"
                )
                self.antigravity_verification = None
                self.fulfill(
                    route,
                    {"detail": {"code": self.antigravity_failure_code, "message": "Reconnect."}},
                    status=409,
                )
                return
            self.antigravity_selected_model = body["model"]
            self.antigravity_effort = body.get("reasoning_effort", self.antigravity_effort)
            self.fulfill(
                route,
                {
                    "provider": "antigravity",
                    "model": self.antigravity_selected_model,
                    "reasoning_effort": self.antigravity_effort,
                },
            )
            return
        if method == "POST" and path == "/api/providers/antigravity/verify":
            if self.antigravity_failure_operation == "verify":
                self.antigravity_failure_operation = None
                self.antigravity_status = "reconnect_required"
                self.antigravity_verification = None
                self.fulfill(
                    route,
                    {"detail": {"code": "reconnect_required", "message": "Reconnect."}},
                    status=409,
                )
                return
            self.antigravity_verification = {
                "model": body["model"],
                "verified_at": "2026-10-18T04:30:00Z",
                "output": {"ok": True},
            }
            self.fulfill(route, self.antigravity_verification)
            return
        if method == "DELETE" and path == "/api/providers/antigravity/connection":
            self.antigravity_status = "disconnected"
            self.antigravity_verification = None
            self.fulfill(
                route,
                {"status": "disconnected", "remote_revocation_confirmed": False},
            )
            return
        if method == "GET" and path == "/api/notes-preferences":
            self.fulfill(route, self.preferences)
            return
        if method == "GET" and path == "/api/providers/chatgpt/models":
            if self.fail_provider_operation(route, "models"):
                return
            selected = self.preferences["models"].get("chatgpt")
            self.fulfill(route, {"models": self.models, "selected_model": selected})
            return
        if method == "POST" and path == "/api/providers/chatgpt/login-sessions":
            if self.login_start_error:
                error = self.login_start_error
                self.login_start_error = None
                self.fulfill(route, {"detail": error}, status=503)
                return
            pending_sessions = [
                session for session in self.sessions.values() if session["status"] == "pending"
            ]
            for pending in pending_sessions:
                pending["status"] = "cancelled"
            self.session_count += 1
            session_id = f"test-session-{self.session_count}"
            expires = datetime.now(UTC) + timedelta(seconds=self.next_expiry_seconds)
            self.sessions[session_id] = {"status": "pending", "expires_at": expires.isoformat()}
            self.next_expiry_seconds = 600
            started = {
                "id": session_id,
                "status": "pending",
                "authorization_url": "https://auth.openai.com/api/accounts/authorize?client_id=dynamic_agent_client&state=ui-test-state",
                "expires_at": expires.isoformat(),
            }
            if pending_sessions:
                started["replaced_previous"] = True
            self.fulfill(route, started)
            return
        if path.startswith("/api/providers/chatgpt/login-sessions/"):
            session_id = path.rsplit("/", 1)[-1]
            session = self.sessions.get(session_id)
            if not session:
                self.fulfill(
                    route,
                    {
                        "detail": {
                            "code": "SESSION_NOT_FOUND",
                            "message": "Không tìm thấy phiên đăng nhập.",
                        }
                    },
                    status=404,
                )
                return
            if method == "DELETE":
                session["status"] = "cancelled"
                self.fulfill(
                    route,
                    {
                        "id": session_id,
                        "status": "cancelled",
                        "expires_at": session["expires_at"],
                        "error": None,
                    },
                )
                return
            if method == "GET":
                if self.next_poll_error:
                    error = self.next_poll_error
                    self.next_poll_error = None
                    self.fulfill(route, {"detail": error}, status=503)
                    return
                status = self.poll_statuses.pop(0) if self.poll_statuses else session["status"]
                session["status"] = status
                if status == "connected":
                    self.status = "connected"
                    self.preferences["provider"] = "chatgpt"
                self.fulfill(
                    route,
                    {
                        "id": session_id,
                        "status": status,
                        "expires_at": session["expires_at"],
                        "error": None,
                    },
                )
                return
        if method == "PUT" and path == "/api/notes-preferences":
            if self.fail_provider_operation(route, "save"):
                return
            if self.next_preference_error:
                error = self.next_preference_error
                self.next_preference_error = None
                self.fulfill(route, {"detail": error}, status=503)
                return
            assert body == {
                "provider": "chatgpt",
                "model": body["model"],
                "reasoning_effort": body["reasoning_effort"],
            }
            self.preferences = {
                "provider": "chatgpt",
                "models": {"chatgpt": body["model"]},
                "reasoning_effort": body["reasoning_effort"],
            }
            self.fulfill(route, self.preferences)
            return
        if method == "POST" and path == "/api/providers/chatgpt/verify":
            if self.fail_provider_operation(route, "verify"):
                return
            if self.next_verification_401:
                self.next_verification_401 = False
                self.fulfill(
                    route,
                    {"detail": "Phiên truy cập workspace không còn hợp lệ."},
                    status=401,
                )
                return
            verified_at = "2026-10-18T04:30:00Z"
            self.verification = {
                "model": body["model"],
                "reasoning_effort": body["reasoning_effort"],
                "verified_at": verified_at,
            }
            self.fulfill(
                route,
                {
                    "model": body["model"],
                    "reasoning_effort": body["reasoning_effort"],
                    "verified_at": verified_at,
                    "output": {"ok": True},
                },
            )
            return
        if method == "DELETE" and path == "/api/providers/chatgpt/connection":
            self.status = "disconnected"
            self.verification = None
            self.fulfill(
                route,
                {
                    "status": "disconnected",
                    "remote_revocation_confirmed": self.remote_revocation_confirmed,
                },
            )
            return
        route.fallback()


@pytest.fixture
def browser_runtime(tmp_path):
    if os.environ.get("ASR_RUN_BROWSER_TESTS") != "1":
        pytest.skip("set ASR_RUN_BROWSER_TESTS=1 to run the real-browser connection tests")
    chrome_path = os.environ.get("CHROME_BIN") or "/usr/bin/google-chrome"
    if not Path(chrome_path).exists() and not shutil.which(chrome_path):
        pytest.skip("Chromium is not installed")

    live = LiveServer(tmp_path)
    live.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=chrome_path)
            yield live, browser
            browser.close()
    finally:
        live.stop()


def signed_in_page(browser, live, *, color_scheme="light", viewport=None, api=None):
    api = api or MockProviderApi()
    context = browser.new_context(color_scheme=color_scheme, viewport=viewport)
    context.add_init_script(
        """(() => {
          window.__openedAuthorizationUrls = [];
          window.open = () => {
            const popup = {
              closed: false,
              opener: null,
              document: { title: "", body: { textContent: "" } },
              location: { replace: url => window.__openedAuthorizationUrls.push(url) },
              close() { this.closed = true; },
            };
            return popup;
          };
        })();"""
    )
    context.route("**/api/providers**", api.route)
    context.route("**/api/notes-preferences", api.route)

    page = context.new_page()
    page.goto(live.access_link, wait_until="domcontentloaded")
    page.wait_for_url(live.url + "/")
    expect(page.locator("#connections-launcher")).to_be_visible()
    return context, page, api


def open_connection_dialog(page):
    page.locator("#connections-launcher").click()
    expect(page.locator("#connections-dialog")).to_be_visible()


def test_chatgpt_login_model_verification_and_disconnect(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(
        browser,
        live,
        color_scheme="light",
        viewport={"width": 1280, "height": 900},
    )
    api.preferences = {"provider": None, "models": {"chatgpt": "gpt-6.1-sol"}}
    api.poll_statuses = ["pending", "connected"]
    expect(page.locator("#connections-launcher")).to_have_attribute("data-state", "disconnected")
    assert page.evaluate("document.documentElement.dataset.theme") == "light"

    open_connection_dialog(page)
    expect(page.get_by_role("button", name="Continue with ChatGPT")).to_be_visible()
    page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()
    expect(page.locator("#connection-status")).to_have_text("Đã kết nối", timeout=8000)
    expect(page.locator("#connection-account")).to_have_text("Tài khoản kiểm thử")
    authorization_urls = page.evaluate("window.__openedAuthorizationUrls")
    assert len(authorization_urls) == 1
    assert "auth.openai.com" in authorization_urls[0]
    assert "id_token_hint" not in authorization_urls[0]
    assert any(
        method == "POST" and path == "/api/providers/chatgpt/login-sessions" and body == {}
        for method, path, body in api.calls
    )

    page.locator("#connection-model").select_option("gpt-6-luna")
    page.get_by_role("button", name="Lưu mô hình và effort").click()
    expect(page.locator("#connection-model-status")).to_contain_text("Đã lưu GPT 6 Luna")
    assert api.preferences == {
        "provider": "chatgpt",
        "models": {"chatgpt": "gpt-6-luna"},
        "reasoning_effort": "default",
    }
    assert any(
        method == "PUT"
        and path == "/api/notes-preferences"
        and body
        == {
            "provider": "chatgpt",
            "model": "gpt-6-luna",
            "reasoning_effort": "default",
        }
        for method, path, body in api.calls
    )

    expect(page.locator("#connection-verification-title")).to_have_text(
        "Kiểm tra bằng dữ liệu tổng hợp"
    )
    expect(page.locator("#connection-verify")).to_be_enabled()
    expect(page.locator(".connection-usage-link")).to_have_attribute(
        "href", "https://chatgpt.com/settings/usage"
    )
    page.get_by_role("button", name="Chạy kiểm tra bằng dữ liệu tổng hợp").click()
    expect(page.locator("#connection-verification-result")).to_contain_text(
        "Đã xác minh GPT 6 Luna"
    )
    verify_calls = [call for call in api.calls if call[1] == "/api/providers/chatgpt/verify"]
    assert len(verify_calls) == 1
    assert verify_calls[0] == (
        "POST",
        "/api/providers/chatgpt/verify",
        {"model": "gpt-6-luna", "reasoning_effort": "default"},
    )
    assert not any("/responses" in path for _, path, _ in api.calls)

    page.get_by_role("button", name="Ngắt kết nối ChatGPT").click()
    expect(page.locator("#connection-disconnect-confirm")).to_be_visible()
    expect(page.locator("#connection-disconnect-confirm")).to_contain_text(
        "thu hồi quyền truy cập từ xa"
    )
    page.get_by_role("button", name="Ngắt kết nối", exact=True).click()
    expect(page.locator("#connection-status")).to_have_text("Chưa kết nối")
    expect(page.locator("#connection-message")).to_contain_text("chưa xác nhận thu hồi quyền từ xa")
    expect(page.locator("#connections-launcher")).to_have_attribute(
        "aria-label", "Kết nối ChatGPT: chưa kết nối"
    )
    assert any(
        method == "DELETE" and path == "/api/providers/chatgpt/connection"
        for method, path, _ in api.calls
    )
    context.close()


def test_antigravity_login_catalog_verification_and_disconnect(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    open_connection_dialog(page)

    expect(page.get_by_role("heading", name="Google Antigravity")).to_be_visible()
    page.get_by_role("button", name="Kết nối Google Antigravity").click()
    expect(page.locator("#antigravity-login-link")).to_be_visible()
    expect(page.locator("#antigravity-login-link")).to_have_attribute(
        "href", "https://accounts.google.com/o/oauth2/auth?state=test"
    )
    expect(page.locator("#antigravity-status")).to_have_text("Đã kết nối", timeout=8000)
    expect(page.locator("#antigravity-account")).to_have_text("Google Antigravity")

    page.locator("#antigravity-model").select_option("gemini-3-pro-high")
    expect(page.locator("#antigravity-effort")).to_have_value("high")
    page.locator("#antigravity-effort").select_option("medium")
    page.get_by_role("button", name="Lưu mô hình Antigravity").click()
    expect(page.locator("#antigravity-model-status")).to_contain_text("Đã lưu Gemini 3 Pro High")
    expect(page.locator("#antigravity-model-status")).to_contain_text("mức suy nghĩ Medium")
    assert api.antigravity_effort == "medium"
    assert (
        "PUT",
        "/api/providers/antigravity/preference",
        {"model": "gemini-3-pro-high", "reasoning_effort": "medium"},
    ) in api.calls
    page.get_by_role("button", name="Chạy kiểm tra model đã chọn").click()
    expect(page.locator("#antigravity-verification-result")).to_contain_text(
        "Đã xác minh Gemini 3 Pro High"
    )
    assert api.antigravity_selected_model == "gemini-3-pro-high"
    assert (
        "POST",
        "/api/providers/antigravity/verify",
        {"model": "gemini-3-pro-high"},
    ) in api.calls

    page.get_by_role("button", name="Ngắt kết nối Antigravity").click()
    expect(page.locator("#antigravity-status")).to_have_text("Chưa kết nối")
    expect(page.locator("#antigravity-message")).to_contain_text("vô hiệu hóa credential OMP")
    context.close()


@pytest.mark.parametrize(
    ("operation", "error_code", "expected_status", "expected_error"),
    [
        (
            "models",
            "reconnect_required",
            "Cần kết nối lại",
            "Phiên Google Antigravity không còn hiệu lực. Hãy kết nối lại.",
        ),
        (
            "verify",
            "reconnect_required",
            "Cần kết nối lại",
            "Phiên Google Antigravity không còn hiệu lực. Hãy kết nối lại.",
        ),
        (
            "preference",
            "reconnect_required",
            "Cần kết nối lại",
            "Phiên Google Antigravity không còn hiệu lực. Hãy kết nối lại.",
        ),
        (
            "preference",
            "provider_disconnected",
            "Chưa kết nối",
            "Hãy kết nối Google Antigravity trước.",
        ),
    ],
)
def test_antigravity_reconnect_error_refreshes_status_and_hides_stale_controls(
    browser_runtime, operation, error_code, expected_status, expected_error
):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.antigravity_status = "connected"
    api.antigravity_selected_model = "gemini-3-pro-high"
    api.antigravity_failure_code = error_code
    if operation == "models":
        api.antigravity_failure_operation = operation
    open_connection_dialog(page)

    if operation == "verify":
        expect(page.locator("#antigravity-status")).to_have_text("Đã kết nối")
        api.antigravity_failure_operation = operation
        page.get_by_role("button", name="Chạy kiểm tra model đã chọn").click()
    elif operation == "preference":
        expect(page.locator("#antigravity-status")).to_have_text("Đã kết nối")
        api.antigravity_failure_operation = operation
        page.locator("#antigravity-model").select_option("claude-sonnet-test")
        page.get_by_role("button", name="Lưu mô hình Antigravity").click()

    expect(page.locator("#antigravity-status")).to_have_text(expected_status)
    expect(page.get_by_role("button", name="Kết nối Google Antigravity")).to_be_visible()
    expect(page.locator("#antigravity-model-section")).to_be_hidden()
    expect(page.locator("#antigravity-verification-section")).to_be_hidden()
    expect(page.locator("#antigravity-error-message")).to_have_text(expected_error)
    assert sum(method == "GET" and path == "/api/providers" for method, path, _ in api.calls) >= 2
    context.close()


def test_restored_antigravity_login_missing_on_server_expires_locally(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    page.evaluate(
        "([id, expiresAt]) => sessionStorage.setItem("
        "'asr.antigravity.pendingLogin', JSON.stringify({id, expiresAt}))",
        ["antigravity-session", future],
    )
    page.reload(wait_until="domcontentloaded")
    open_connection_dialog(page)

    expect(page.get_by_role("button", name="Kết nối Google Antigravity")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('asr.antigravity.pendingLogin')") is None
    assert any(
        method == "GET" and path.endswith("/antigravity-session") for method, path, _ in api.calls
    )
    context.close()


def test_missing_antigravity_login_can_be_cancelled_without_sticking(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.antigravity_polls = ["pending"] * 10
    open_connection_dialog(page)
    page.get_by_role("button", name="Kết nối Google Antigravity").click()
    expect(page.locator("#antigravity-cancel")).to_be_visible()

    # Drop the session only for the cancel request; a background poll seeing
    # 404 first would finish the login and hide the button before the click.
    def drop_session_on_cancel(route):
        if route.request.method == "DELETE":
            api.antigravity_session = None
        route.fallback()

    context.route("**/antigravity-session", drop_session_on_cancel)
    page.locator("#antigravity-cancel").click()

    expect(page.get_by_role("button", name="Kết nối Google Antigravity")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('asr.antigravity.pendingLogin')") is None
    assert any(
        method == "DELETE" and path.endswith("/antigravity-session")
        for method, path, _ in api.calls
    )
    context.close()


def test_expired_restored_antigravity_login_is_discarded_without_polling(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    expired = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    page.evaluate(
        "([id, expiresAt]) => sessionStorage.setItem("
        "'asr.antigravity.pendingLogin', JSON.stringify({id, expiresAt}))",
        ["antigravity-session", expired],
    )
    api.calls.clear()
    page.reload(wait_until="domcontentloaded")
    open_connection_dialog(page)

    expect(page.get_by_role("button", name="Kết nối Google Antigravity")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('asr.antigravity.pendingLogin')") is None
    assert not any(path.endswith("/antigravity-session") for _, path, _ in api.calls)
    context.close()


def test_login_cancel_expiry_and_api_errors(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.next_poll_error = {
        "code": "STATUS_TEMPORARILY_UNAVAILABLE",
        "message": "Chưa đọc được trạng thái đăng nhập. Hãy thử lại.",
    }
    open_connection_dialog(page)
    page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(page.locator("#connection-error-message")).to_have_text(
        "Chưa đọc được trạng thái đăng nhập. Hãy thử lại.", timeout=6000
    )
    expect(page.get_by_role("button", name="Kiểm tra trạng thái lại")).to_be_visible()
    page.get_by_role("button", name="Kiểm tra trạng thái lại").click()
    expect(page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()
    page.get_by_role("button", name="Hủy đăng nhập").click()
    expect(page.locator("#connection-message")).to_have_text("Đã hủy đăng nhập ChatGPT.")
    assert any(
        method == "DELETE" and path.endswith("test-session-1") for method, path, _ in api.calls
    )

    api.next_expiry_seconds = -1
    page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(page.locator("#connection-message")).to_contain_text("đã hết hạn")
    expect(page.get_by_role("button", name="Continue with ChatGPT")).to_be_visible()

    api.login_start_error = {
        "code": "SIGN_IN_TEMPORARILY_UNAVAILABLE",
        "message": "Dịch vụ đăng nhập hiện chưa khả dụng. Hãy thử lại sau.",
    }
    page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(page.locator("#connection-error-message")).to_have_text(
        "Dịch vụ đăng nhập hiện chưa khả dụng. Hãy thử lại sau."
    )
    expect(page.locator("#connection-error")).to_be_visible()
    context.close()


@pytest.mark.parametrize("model_id", ["gpt-5.6-luna", "gpt-6-luna"])
def test_luna_effort_is_saved_and_used_for_verification(browser_runtime, model_id):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.status = "connected"
    api.preferences = {
        "provider": "chatgpt",
        "models": {"chatgpt": model_id},
        "reasoning_effort": "default",
    }

    open_connection_dialog(page)
    expect(page.locator("#connection-model")).to_have_value(model_id)
    expect(page.locator("#connection-effort")).to_be_enabled()
    page.locator("#connection-effort").select_option("max")
    page.get_by_role("button", name="Lưu mô hình và effort").click()
    expect(page.locator("#connection-model-status")).to_contain_text("effort max")
    assert api.preferences["reasoning_effort"] == "max"

    page.get_by_role("button", name="Chạy kiểm tra bằng dữ liệu tổng hợp").click()
    expect(page.locator("#connection-verification-result")).to_contain_text("effort max")
    assert (
        "POST",
        "/api/providers/chatgpt/verify",
        {"model": model_id, "reasoning_effort": "max"},
    ) in api.calls

    page.locator("#connections-close").click()
    open_connection_dialog(page)
    expect(page.locator("#connection-effort")).to_have_value("max")
    context.close()


def test_unavailable_model_is_preserved_and_dialog_is_accessible_on_mobile(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(
        browser,
        live,
        color_scheme="dark",
        viewport={"width": 320, "height": 740},
    )
    api.status = "connected"
    api.preferences = {"provider": "chatgpt", "models": {"chatgpt": "gpt-retired"}}
    api.models = [{"id": "gpt-current", "display_name": "GPT Current"}]
    api.next_preference_error = {
        "code": "PREFERENCE_WRITE_UNAVAILABLE",
        "message": "Chưa lưu được lựa chọn model. Hãy thử lại.",
    }
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert (
        page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        == 0
    )

    open_connection_dialog(page)
    expect(page.locator("#connection-status")).to_have_text("Đã kết nối")
    expect(page.locator("#connection-model option").first).to_have_text(
        "gpt-retired — không khả dụng với tài khoản này"
    )
    expect(page.get_by_role("button", name="Lưu mô hình")).to_be_disabled()
    expect(page.locator("#connection-verify")).to_be_disabled()
    page.keyboard.press("Tab")
    assert page.locator("#connections-dialog").evaluate(
        "dialog => dialog.contains(document.activeElement)"
    )
    focus_style = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    assert focus_style == "solid"

    page.locator("#connection-model").select_option("gpt-current")
    page.get_by_role("button", name="Lưu mô hình").click()
    expect(page.locator("#connection-error-message")).to_have_text(
        "Chưa lưu được lựa chọn model. Hãy thử lại."
    )
    assert api.preferences["models"]["chatgpt"] == "gpt-retired"
    assert page.locator("#connection-model").input_value() == "gpt-current"

    page.keyboard.press("Escape")
    expect(page.locator("#connections-dialog")).to_be_hidden()
    expect(page.locator("#connections-launcher")).to_be_focused()
    assert (
        page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        == 0
    )
    context.close()


@pytest.mark.parametrize(
    ("operation", "error_code"),
    [
        ("models", "provider_auth_error"),
        ("save", "provider_auth_error"),
        ("verify", "provider_auth_error"),
        ("models", "reconnect_required"),
        ("models", "subscription_sharing_invalid_user"),
        ("models", "chatpass_v2_scope_not_authorized"),
        ("verify", "chatpass_v2_invalid_authorization_context"),
    ],
)
def test_provider_reconnect_error_refreshes_status_without_replaying_verify(
    browser_runtime, operation, error_code
):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.status = "connected"
    api.preferences = {"provider": "chatgpt", "models": {"chatgpt": "gpt-6.1-sol"}}
    api.provider_failure_operation = operation
    api.provider_failure_code = error_code
    open_connection_dialog(page)
    if operation != "models":
        expect(page.locator("#connection-status")).to_have_text("Đã kết nối")

    if operation == "save":
        page.locator("#connection-model").select_option("gpt-6-luna")
        page.get_by_role("button", name="Lưu mô hình").click()
    elif operation == "verify":
        page.get_by_role("button", name="Chạy kiểm tra bằng dữ liệu tổng hợp").click()

    expect(page.locator("#connection-status")).to_have_text("Cần đăng nhập lại")
    expect(page.get_by_role("button", name="Continue with ChatGPT")).to_be_visible()
    expect(page.get_by_role("button", name="Continue with ChatGPT")).to_be_enabled()
    expect(page.locator("#connection-error-message")).to_have_text(
        "ChatGPT không chấp nhận thông tin đăng nhập hiện tại. Hãy kết nối lại tài khoản."
        if error_code in {"provider_auth_error", "subscription_sharing_invalid_user"}
        else "Tài khoản chưa cấp quyền dùng gói ChatGPT. Hãy kết nối lại và cấp quyền cần thiết."
        if error_code == "chatpass_v2_scope_not_authorized"
        else (
            "Cấu hình cấp quyền ChatGPT không hợp lệ. "
            "Hãy kiểm tra cấu hình kết nối trước khi đăng nhập lại."
        )
        if error_code == "chatpass_v2_invalid_authorization_context"
        else "Tài khoản ChatGPT cần đăng nhập lại trước khi tiếp tục."
    )
    assert any(method == "GET" and path == "/api/providers" for method, path, _ in api.calls)
    verify_calls = [call for call in api.calls if call[1] == "/api/providers/chatgpt/verify"]
    assert len(verify_calls) == (1 if operation == "verify" else 0)
    context.close()


def test_local_auth_401_does_not_mark_provider_reconnect(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    api.status = "connected"
    api.preferences = {"provider": "chatgpt", "models": {"chatgpt": "gpt-6.1-sol"}}
    open_connection_dialog(page)
    expect(page.locator("#connection-status")).to_have_text("Đã kết nối")
    provider_reads_before = sum(
        method == "GET" and path == "/api/providers" for method, path, _ in api.calls
    )
    api.next_verification_401 = True

    page.get_by_role("button", name="Chạy kiểm tra bằng dữ liệu tổng hợp").click()
    expect(page.locator("#connection-error-message")).to_have_text(
        "Phiên truy cập workspace không còn hợp lệ."
    )
    expect(page.locator("#connection-status")).to_have_text("Đã kết nối")
    expect(page.get_by_role("button", name="Continue with ChatGPT")).to_be_hidden()
    provider_reads_after = sum(
        method == "GET" and path == "/api/providers" for method, path, _ in api.calls
    )
    assert provider_reads_after == provider_reads_before
    context.close()


def test_pending_login_survives_reload_and_can_be_cancelled(browser_runtime):
    live, browser = browser_runtime
    context, page, api = signed_in_page(browser, live)
    open_connection_dialog(page)
    page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()
    page.reload(wait_until="domcontentloaded")
    open_connection_dialog(page)
    expect(page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()
    page.get_by_role("button", name="Hủy đăng nhập").click()
    expect(page.locator("#connection-message")).to_have_text("Đã hủy đăng nhập ChatGPT.")
    assert api.session_count == 1
    assert page.evaluate("sessionStorage.getItem('asr.chatgpt.pendingLogin')") is None
    context.close()


def test_separate_browser_profiles_replace_pending_login_and_show_notice(browser_runtime):
    live, browser = browser_runtime
    api = MockProviderApi()
    first_context, first_page, _ = signed_in_page(browser, live, api=api)
    open_connection_dialog(first_page)
    first_page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(first_page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()
    first_id = json.loads(
        first_page.evaluate("sessionStorage.getItem('asr.chatgpt.pendingLogin')")
    )["id"]

    second_context, second_page, _ = signed_in_page(browser, live, api=api)
    open_connection_dialog(second_page)
    second_page.get_by_role("button", name="Continue with ChatGPT").click()
    expect(second_page.get_by_role("button", name="Hủy đăng nhập")).to_be_visible()

    expect(second_page.locator("#connection-message")).to_have_text(
        "Đã thay thế phiên đăng nhập đang chờ. Hãy tiếp tục ở cửa sổ ChatGPT mới; "
        "phản hồi từ cửa sổ cũ sẽ bị bỏ qua."
    )
    second_id = json.loads(
        second_page.evaluate("sessionStorage.getItem('asr.chatgpt.pendingLogin')")
    )["id"]
    assert second_id != first_id
    assert api.sessions[first_id]["status"] == "cancelled"
    assert api.sessions[second_id]["status"] == "pending"

    first_storage = first_page.evaluate("sessionStorage.getItem('asr.chatgpt.pendingLogin')")
    assert not first_storage or json.loads(first_storage)["id"] == first_id
    assert (
        json.loads(second_page.evaluate("sessionStorage.getItem('asr.chatgpt.pendingLogin')"))["id"]
        == second_id
    )
    first_context.close()
    second_context.close()
