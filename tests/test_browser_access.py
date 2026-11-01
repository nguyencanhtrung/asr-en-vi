from __future__ import annotations

import logging
import os
import shutil
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from asr_studio.app import create_app
from asr_studio.auth import AuthStore
from asr_studio.config import Settings


@pytest.mark.browser
def test_access_fragment_is_removed_before_http_exchange_and_cookie_is_httponly(tmp_path, caplog):
    if os.environ.get("ASR_RUN_BROWSER_TESTS") != "1":
        pytest.skip("set ASR_RUN_BROWSER_TESTS=1 to run the real-browser access test")
    chrome_path = os.environ.get("CHROME_BIN") or shutil.which("google-chrome")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen()
    port = server_socket.getsockname()[1]
    public_url = f"http://127.0.0.1:{port}"
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url=public_url,
    )
    caplog.set_level(logging.INFO)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            log_config=None,
            log_level="info",
            access_log=True,
        )
    )
    server_thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
    )
    server_thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.025)
        assert server.started, "test server did not start"

        state = AuthStore(settings.auth_dir).load()
        link = f"{public_url}/access#{state.token}"
        exchange_requests: list[tuple[str, str]] = []
        with sync_playwright() as playwright:
            launch_options = {"executable_path": chrome_path} if chrome_path else {}
            browser = playwright.chromium.launch(headless=True, **launch_options)
            context = browser.new_context()
            page = context.new_page()
            page.on(
                "request",
                lambda request: (
                    exchange_requests.append((request.url, request.post_data or ""))
                    if request.url.endswith("/api/access/session")
                    else None
                ),
            )
            page.goto(link, wait_until="domcontentloaded")
            page.wait_for_url(f"{public_url}/", timeout=10_000)

            assert page.url == f"{public_url}/"
            assert awaitable_evaluate(page, "window.location.hash") == ""
            assert awaitable_evaluate(page, "document.cookie") == ""
            assert awaitable_evaluate(page, "Object.keys(localStorage).length") == 0
            assert awaitable_evaluate(page, "Object.keys(sessionStorage).length") == 0
            assert len(exchange_requests) == 1
            request_url, request_body = exchange_requests[0]
            assert state.token not in request_url
            assert state.token in request_body
            cookie = next(
                cookie for cookie in context.cookies() if cookie["name"] == "asr_studio_session"
            )
            assert cookie["httpOnly"] is True
            assert cookie["sameSite"] == "Strict"
            assert cookie["expires"] == -1
            assert "Không có cuộc họp nào được lưu" in page.locator("main").inner_text()
            assert "/api/access/session" in caplog.text
            assert state.token not in caplog.text
            browser.close()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)
        server_socket.close()


def awaitable_evaluate(page, expression: str):
    """Keep the browser assertions synchronous while evaluating page state."""
    return page.evaluate(expression)
