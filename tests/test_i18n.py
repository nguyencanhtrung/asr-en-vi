from __future__ import annotations

import json
import os
import re
import shutil
import socket
import threading
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "asr_en_vi" / "web"
VIETNAMESE = re.compile(r"[À-ỹ]")
PLACEHOLDER = re.compile(r"\{\w+\}")
TRANSLATED_ATTRIBUTES = {"aria-label", "title", "placeholder", "content"}


def english_table() -> dict[str, str]:
    source = (WEB_DIR / "i18n.js").read_text(encoding="utf-8")
    table = re.search(r"function englishTable\(\) \{\s*return (\{.*?\n\s*\});", source, re.S)
    return json.loads(table.group(1))


class _PageStrings(HTMLParser):
    """Collects the strings i18n.js translates in static markup: text nodes and a few attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.found: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.found.update(value for name, value in attrs if name in TRANSLATED_ATTRIBUTES and value)

    def handle_data(self, data):
        if text := " ".join(data.split()):
            self.found.add(text)


def ui_strings() -> set[str]:
    found: set[str] = set()
    for page in ("shell.html", "access.html"):
        parser = _PageStrings()
        parser.feed((WEB_DIR / page).read_text(encoding="utf-8"))
        found |= parser.found
    for script in WEB_DIR.glob("*.js"):
        for literal in re.findall(r'\bt\("((?:[^"\\]|\\.)*)"', script.read_text(encoding="utf-8")):
            found.add(json.loads(f'"{literal}"'))
    return found


def test_every_vietnamese_ui_string_has_english_with_the_same_placeholders():
    table = english_table()
    strings = ui_strings()

    assert sorted(s for s in strings if VIETNAMESE.search(s) and s not in table) == []
    assert sorted(set(table) - strings) == [], "unused English entries"
    assert [
        vi
        for vi, en in table.items()
        if sorted(PLACEHOLDER.findall(vi)) != sorted(PLACEHOLDER.findall(en))
    ] == []
    assert [en for en in table.values() if VIETNAMESE.search(en)] == []


@pytest.mark.browser
def test_language_toggle_switches_workspace_and_access_page_to_english(tmp_path):
    if os.environ.get("ASR_RUN_BROWSER_TESTS") != "1":
        pytest.skip("set ASR_RUN_BROWSER_TESTS=1 to run the real-browser language test")
    chrome_path = os.environ.get("CHROME_BIN") or shutil.which("google-chrome")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen()
    port = server_socket.getsockname()[1]
    public_url = f"http://127.0.0.1:{port}"
    settings = Settings(
        data_dir=tmp_path / "data", auth_dir=tmp_path / "auth", public_url=public_url
    )
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), log_config=None, log_level="warning", access_log=False)
    )
    server_thread = threading.Thread(
        target=server.run, kwargs={"sockets": [server_socket]}, daemon=True
    )
    server_thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.025)
        assert server.started, "test server did not start"

        state = AuthStore(settings.auth_dir).load()
        with sync_playwright() as playwright:
            launch_options = {"executable_path": chrome_path} if chrome_path else {}
            browser = playwright.chromium.launch(headless=True, **launch_options)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            page.goto(f"{public_url}/access")
            toggle = page.locator("[data-lang-toggle]")
            expect(toggle).to_have_text("EN")
            expect(page.locator("#access-title")).to_have_text("Mở không gian làm việc")
            toggle.click()
            expect(page.locator("html")).to_have_attribute("lang", "en")
            expect(page.locator("#access-title")).to_have_text("Open the workspace")
            expect(toggle).to_have_text("VI")

            page.goto("about:blank")  # a hash-only change would not reload /access
            page.goto(f"{public_url}/access#{state.token}")
            page.wait_for_url(f"{public_url}/")
            expect(page.locator("#open-calendar")).to_have_text("Calendar")
            expect(page.locator("#history-search")).to_have_attribute(
                "placeholder", "Search meetings by name…"
            )
            expect(page.locator(".cal-today").first).to_have_text("Today")
            expect(page.locator("#sidebar-empty")).to_be_visible()
            visible = page.locator("body").inner_text()
            assert VIETNAMESE.findall(visible) == [], visible

            page.locator("[data-lang-toggle]").click()
            expect(page.locator("#open-calendar")).to_have_text("Lịch")
            expect(page.locator("[data-lang-toggle]")).to_have_text("EN")
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)
