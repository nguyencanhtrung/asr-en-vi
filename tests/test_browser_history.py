from __future__ import annotations

import json
import os
import re
import shutil
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright
from seeding import seed_meeting

from asr_en_vi import routes as routes_module
from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.runtime import RuntimeProfile, write_runtime_profile
from asr_en_vi.worker import acquire_worker_lock, write_heartbeat

pytestmark = pytest.mark.browser

# Far ahead of UTC so any date arithmetic done in local time would drift a day.
TIMEZONE = "Pacific/Kiritimati"
# Keep the UTC offset explicit (+14:00 is Kiritimati's, i.e. 2026-10-17 10:00 local):
# Chromium versions parse a timezone-naive string differently (UTC vs context-local),
# which shifted "today" by a day on newer Chrome.
FIXED_NOW = "2026-10-17T10:00:00+14:00"


class LiveServer:
    def __init__(self, tmp_path):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self.url = f"http://127.0.0.1:{self.port}"
        self.settings = Settings(
            data_dir=tmp_path / "data", auth_dir=tmp_path / "auth", public_url=self.url
        )
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
                create_app(self.settings), log_config=None, log_level="warning", access_log=False
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.025)
        assert self.server.started, "test server did not start"

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.sock.close()

    @property
    def access_link(self):
        return f"{self.url}/access#{AuthStore(self.settings.auth_dir).load().token}"


@pytest.fixture
def live(tmp_path):
    if os.environ.get("ASR_RUN_BROWSER_TESTS") != "1":
        pytest.skip("set ASR_RUN_BROWSER_TESTS=1 to run the real-browser history tests")
    server = LiveServer(tmp_path)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def signed_in(live):
    """Factory for authenticated (context, page) pairs in a chosen timezone and clock."""
    with sync_playwright() as playwright:
        chrome_path = os.environ.get("CHROME_BIN") or shutil.which("google-chrome")
        launch = {"executable_path": chrome_path} if chrome_path else {}
        browser = playwright.chromium.launch(headless=True, **launch)

        def make(timezone=TIMEZONE, now=FIXED_NOW):
            context = browser.new_context(timezone_id=timezone)
            first = context.new_page()
            first.clock.set_fixed_time(now)
            first.goto(live.access_link, wait_until="domcontentloaded")
            first.wait_for_url(f"{live.url}/", timeout=10_000)
            return context, first

        yield make
        browser.close()


@pytest.fixture
def browser_context(signed_in):
    return signed_in()


def open_page(context, live, path="/", now=FIXED_NOW):
    page = context.new_page()
    page.clock.set_fixed_time(now)
    page.goto(f"{live.url}{path}", wait_until="domcontentloaded")
    return page


def test_history_search_calendar_navigation_and_return(live, browser_context):
    context, page = browser_context
    data_dir = live.settings.data_dir
    seed_meeting(data_dir, "Delta year end", "2025-12-31")
    seed_meeting(data_dir, "Epsilon new year", "2026-01-01")
    seed_meeting(data_dir, "Gamma planning", "2026-10-09")
    alpha = seed_meeting(data_dir, "Alpha review", "2026-10-14", duration_seconds=720)
    beta = seed_meeting(data_dir, "Beta sync", "2026-10-14", duration_seconds=5025)
    seed_meeting(data_dir, "Zeta undated")
    seed_meeting(data_dir, "Leap day", "2024-02-29")
    page.goto(f"{live.url}/", wait_until="domcontentloaded")

    recent = page.locator("#recent-list a")
    expect(recent).to_have_count(3)
    assert [t.strip() for t in page.locator("#recent-list .link-title").all_inner_texts()] == [
        "Beta sync",
        "Alpha review",
        "Gamma planning",
    ]
    # Date and recording length only; there is no start time to show.
    assert page.locator("#recent-list .link-date").all_inner_texts() == [
        "14/10/2026 · 1 giờ 24 phút",
        "14/10/2026 · 12 phút",
        "09/10/2026 · 1 giây",
    ]

    search = page.get_by_label("Tìm cuộc họp theo tên")
    search.fill("LEAP")
    expect(recent).to_have_count(1)
    expect(recent.first).to_contain_text("Leap day")
    expect(recent.first.locator(".link-date")).to_have_text("29/02/2024 · 1 giây")
    search.fill("không tồn tại")
    expect(page.locator("#search-empty")).to_be_visible()
    expect(page.locator("#sidebar-empty")).to_be_hidden()
    search.fill("")
    expect(recent).to_have_count(3)

    # Open from the recent list, then browse the calendar.
    recent.filter(has_text="Alpha review").click()
    page.wait_for_url(f"{live.url}/meetings/{alpha}")
    expect(page.locator("#meeting-title")).to_have_text("Alpha review")
    expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-14")
    page.get_by_role("button", name="Mở lịch").click()
    large = page.locator("#large-calendar")
    expect(page.locator("#calendar-title")).to_be_visible()
    expect(large.locator(".cal-title")).to_have_text("Tháng 10 · 2026")
    expect(page.locator("#mini-calendar .cal-title")).to_have_text("Tháng 10 · 2026")

    # Monday-first: 1 Oct 2026 is a Thursday, so the grid starts on 28 Sep.
    expect(large.locator(".cal-weekdays span").first).to_have_text("T2")
    expect(large.locator(".cal-weekdays span").last).to_have_text("CN")
    expect(large.locator(".cal-day").first).to_have_attribute("data-date", "2026-09-28")
    expect(large.locator(".cal-day.is-today")).to_have_attribute("data-date", "2026-10-17")
    expect(large.locator('.cal-day[data-date="2026-10-14"] .cal-count')).to_have_text("2")
    expect(page.locator('#mini-calendar .cal-day[data-date="2026-10-14"] .cal-count')).to_have_text(
        "2"
    )
    expect(large.locator(".cal-summary")).to_have_text("3 cuộc họp trong tháng")
    expect(large.locator(".cal-undated-count")).to_have_text("1")

    large.locator('.cal-day[data-date="2026-10-14"]').click()
    expect(page.locator("#day-panel-title")).to_have_text("14/10/2026")
    expect(page.locator("#day-panel-count")).to_have_text("2")
    expect(page.locator("#day-panel-list a")).to_have_count(2)
    assert not any(":" in text for text in page.locator("#day-panel-list a").all_inner_texts()), (
        "date-only meetings must not show a start time"
    )

    large.locator(".cal-undated").click()
    expect(page.locator("#day-panel-title")).to_have_text("Chưa đặt ngày")
    expect(page.locator("#day-panel-list a")).to_have_text(["Zeta undatedChưa đặt ngày · 1 giây"])

    large.get_by_role("button", name="Hôm nay").click()
    expect(page.locator("#day-panel-title")).to_have_text("17/10/2026")
    expect(page.locator("#day-panel-empty")).to_be_visible()

    # Month/year navigation across the year boundary and a leap year.
    large.locator(".cal-month").select_option("11")
    large.locator(".cal-year").fill("2025")
    large.locator(".cal-year").press("Enter")
    expect(large.locator(".cal-title")).to_have_text("Tháng 12 · 2025")
    expect(page.locator("#mini-calendar .cal-title")).to_have_text("Tháng 12 · 2025")
    expect(large.locator('.cal-day[data-date="2025-12-31"]')).not_to_have_class("is-outside")
    large.get_by_label("Tháng sau").click()
    expect(large.locator(".cal-title")).to_have_text("Tháng 1 · 2026")
    expect(large.locator(".cal-day").first).to_have_attribute("data-date", "2025-12-29")
    expect(large.locator('.cal-day[data-date="2026-01-01"] .cal-count')).to_have_text("1")
    large.get_by_label("Tháng trước").click()
    large.get_by_label("Tháng trước").click()
    expect(large.locator(".cal-title")).to_have_text("Tháng 11 · 2025")
    expect(large.locator(".cal-summary")).to_have_text("Không có cuộc họp trong tháng này.")
    large.locator(".cal-month").select_option("1")
    large.locator(".cal-year").fill("2024")
    large.locator(".cal-year").press("Enter")
    expect(large.locator('.cal-day[data-date="2024-02-29"]')).not_to_have_class("is-outside")
    expect(large.locator('.cal-day[data-date="2024-02-29"] .cal-count')).to_have_text("1")
    large.locator(".cal-year").fill("2026")
    large.locator(".cal-year").press("Enter")
    expect(large.locator('.cal-day[data-date="2026-03-01"]')).to_have_class("cal-day is-outside")
    expect(large.locator(".cal-day[data-date='2026-02-29']")).to_have_count(0)

    # Keyboard: arrows move the selected day and keep focus on it.
    large.locator(".cal-month").select_option("9")
    large.locator('.cal-day[data-date="2026-10-14"]').click()
    large.locator('.cal-day[data-date="2026-10-14"]').focus()
    page.keyboard.press("ArrowDown")
    expect(large.locator(".cal-day.is-selected")).to_have_attribute("data-date", "2026-10-21")
    assert page.evaluate("document.activeElement.dataset.date") == "2026-10-21"
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("document.activeElement.dataset.date") == "2026-10-20"
    page.keyboard.press("Enter")
    expect(page.locator("#day-panel-title")).to_have_text("20/10/2026")

    # Browsing without choosing a meeting returns to the one open before the calendar.
    page.get_by_role("button", name="Quay lại notes").click()
    page.wait_for_url(f"{live.url}/meetings/{alpha}")
    expect(page.locator("#meeting-title")).to_have_text("Alpha review")
    expect(page.locator("#recent-list a[aria-current='page']")).to_contain_text("Alpha review")

    # Choosing a different meeting from a calendar cell opens exactly that record.
    page.get_by_role("button", name="Mở lịch").click()
    large.locator('.cal-day[data-date="2026-10-14"]').click()
    page.locator("#day-panel-list a").filter(has_text="Beta sync").click()
    page.wait_for_url(f"{live.url}/meetings/{beta}")
    expect(page.locator("#meeting-title")).to_have_text("Beta sync")
    page.go_back()
    expect(page.locator("#meeting-title")).to_have_text("Alpha review")
    page.get_by_role("button", name="Mở lịch").click()
    large.locator('.cal-day[data-date="2026-10-14"]').click()
    large.locator(".cal-chip").filter(has_text="Alpha review").click()
    page.wait_for_url(f"{live.url}/meetings/{alpha}")

    # An unauthenticated context cannot read the history.
    anonymous = page.context.browser.new_context()
    try:
        assert anonymous.request.get(f"{live.url}/api/meetings").status == 401
    finally:
        anonymous.close()


def test_empty_history_states(live, browser_context):
    _, page = browser_context
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    expect(page.locator("#sidebar-empty")).to_have_text("Cuộc họp đã lưu sẽ xuất hiện tại đây.")
    expect(page.locator("#workspace-empty")).to_be_visible()
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#large-calendar .cal-summary")).to_have_text(
        "Không có cuộc họp trong tháng này."
    )
    page.locator("#large-calendar .cal-undated").click()
    expect(page.locator("#day-panel-empty")).to_have_text("Mọi cuộc họp đều đã có ngày.")
    expect(page.locator("#large-calendar .cal-count")).to_have_count(0)
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#home-view")).to_be_visible()


def test_edit_metadata_conflict_keeps_draft_and_persists_across_restart(live, browser_context):
    context, page_a = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Original", "2026-10-14", language_hint="vi")
    seed_meeting(live.settings.data_dir, "Other", "2026-10-13")
    page_a.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page_a.locator("#meeting-title")).to_have_text("Original")
    page_b = open_page(context, live, f"/meetings/{meeting_id}")
    expect(page_b.locator("#meeting-title")).to_have_text("Original")

    patches: list[dict] = []
    page_b.on(
        "request",
        lambda request: (
            patches.append(json.loads(request.post_data)) if request.method == "PATCH" else None
        ),
    )

    # Tab A starts a draft but does not save yet.
    page_a.get_by_role("button", name="Sửa tên và ngày").click()
    page_a.locator("#edit-title").fill("Draft from A")
    page_a.locator("#edit-clear-date").click()

    # Tab B saves a title-only edit; it must not carry a date or language.
    page_b.get_by_role("button", name="Sửa tên và ngày").click()
    page_b.locator("#edit-title").fill("Saved from B")
    page_b.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_b.locator("#meeting-title")).to_have_text("Saved from B")
    expect(page_b.locator("#edit-status")).to_have_text("Đã lưu tên và ngày họp.")
    assert patches == [{"expected_metadata_version": 1, "title": "Saved from B"}]
    expect(page_b.locator("#recent-list a").first).to_contain_text("Saved from B")

    # Tab A's save is stale: rejected, draft kept, nothing merged or overwritten.
    page_a.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_a.locator("#edit-conflict")).to_contain_text("Saved from B")
    expect(page_a.locator("#edit-title")).to_have_value("Draft from A")
    expect(page_a.locator("#edit-date")).to_have_value("")
    expect(page_a.locator("#meeting-title")).to_have_text("Saved from B")
    expect(page_a.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-14")
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert (stored["title"], stored["meeting_date"]) == ("Saved from B", "2026-10-14")

    # After comparing, an explicit second save wins and removes the date.
    page_a.get_by_role("button", name="Lưu bản nháp lên bản mới nhất").click()
    expect(page_a.locator("#meeting-title")).to_have_text("Draft from A")
    expect(page_a.locator("#meeting-date")).to_have_text("Chưa đặt ngày")
    expect(page_a.locator("#meeting-language")).to_have_text("Tiếng Việt")
    expect(page_a.locator("#recent-list")).not_to_contain_text("Draft from A")
    page_a.get_by_role("button", name="Mở lịch").click()
    expect(page_a.locator("#large-calendar .cal-undated-count")).to_have_text("1")
    expect(page_a.locator('#large-calendar .cal-day[data-date="2026-10-14"]')).not_to_have_class(
        "has-meetings"
    )
    page_a.get_by_label("Tìm cuộc họp theo tên").fill("draft")
    expect(page_a.locator("#recent-list a")).to_have_count(1)
    expect(page_a.locator("#recent-list a")).to_contain_text("Chưa đặt ngày")

    # Restart the server: the edits come from SQLite, not frontend memory.
    live.stop()
    live.start()
    page_a.reload(wait_until="domcontentloaded")
    expect(page_a.locator("#large-calendar .cal-undated-count")).to_have_text("1")
    page_a.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page_a.locator("#meeting-title")).to_have_text("Draft from A")
    expect(page_a.locator("#meeting-date")).to_have_text("Chưa đặt ngày")
    final = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert final["metadata_version"] == 3
    assert final["notes_source_version"] == 2  # only the date change bumped the notes source
    assert final["language_hint"] == "vi"

    # Re-adding a date from the editor moves it back onto the calendar.
    page_a.get_by_role("button", name="Sửa tên và ngày").click()
    page_a.locator("#edit-date").fill("2026-02-28")
    page_a.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_a.locator("#meeting-date")).to_have_attribute("datetime", "2026-02-28")
    page_a.get_by_role("button", name="Mở lịch").click()
    page_a.locator("#large-calendar .cal-month").select_option("1")
    expect(
        page_a.locator('#large-calendar .cal-day[data-date="2026-02-28"] .cal-count')
    ).to_have_text("1")


def record_patches(page) -> list[dict]:
    patches: list[dict] = []
    page.on(
        "request",
        lambda request: (
            patches.append(json.loads(request.post_data)) if request.method == "PATCH" else None
        ),
    )
    return patches


def test_partial_date_is_not_treated_as_clearing_the_date(live, browser_context):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Keep my date", "2026-10-14")
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    patches = record_patches(page)

    page.get_by_role("button", name="Sửa tên và ngày").click()
    date = page.locator("#edit-date")
    date.focus()
    page.keyboard.press("Backspace")  # clears only the focused month segment
    assert date.evaluate("element => element.validity.badInput") is True
    assert date.input_value() == "", "a partial date reads as empty, which must not mean delete"
    page.locator("#edit-title").fill("Renamed too")

    page.get_by_role("button", name="Lưu thay đổi").click()
    expect(page.locator("#edit-error")).to_contain_text("chưa đầy đủ")
    expect(page.locator("#meeting-edit")).to_be_visible()
    expect(page.locator("#edit-title")).to_have_value("Renamed too")
    assert patches == []
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert (stored["title"], stored["meeting_date"]) == ("Keep my date", "2026-10-14")

    # Deleting the date is still possible, but only on purpose.
    page.locator("#edit-clear-date").click()
    assert page.locator("#edit-date").evaluate("element => element.validity.badInput") is False
    page.get_by_role("button", name="Lưu thay đổi").click()
    expect(page.locator("#meeting-date")).to_have_text("Chưa đặt ngày")
    assert patches == [
        {"expected_metadata_version": 1, "title": "Renamed too", "meeting_date": None}
    ]


def test_conflict_resends_only_fields_the_user_edited(live, browser_context):
    context, page_a = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Orig title", "2026-10-14")
    path = f"/meetings/{meeting_id}"
    page_a.goto(f"{live.url}{path}", wait_until="domcontentloaded")
    page_b = open_page(context, live, path)
    patches_a = record_patches(page_a)
    patches_b = record_patches(page_b)

    page_a.get_by_role("button", name="Sửa tên và ngày").click()
    page_a.locator("#edit-title").fill("Title from A")
    page_b.get_by_role("button", name="Sửa tên và ngày").click()
    page_b.locator("#edit-date").fill("2026-11-02")
    page_b.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_b.locator("#meeting-date")).to_have_attribute("datetime", "2026-11-02")
    assert patches_b == [{"expected_metadata_version": 1, "meeting_date": "2026-11-02"}]

    page_a.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_a.locator("#edit-conflict")).to_be_visible()
    expect(page_a.locator("#edit-title")).to_have_value("Title from A")
    expect(page_a.locator("#edit-date")).to_have_value("2026-11-02")  # untouched: follows server
    page_a.get_by_role("button", name="Lưu bản nháp lên bản mới nhất").click()
    expect(page_a.locator("#meeting-title")).to_have_text("Title from A")
    expect(page_a.locator("#meeting-date")).to_have_attribute("datetime", "2026-11-02")
    assert patches_a == [
        {"expected_metadata_version": 1, "title": "Title from A"},
        {"expected_metadata_version": 2, "title": "Title from A"},
    ]
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert (stored["title"], stored["meeting_date"]) == ("Title from A", "2026-11-02")
    assert (stored["metadata_version"], stored["notes_source_version"]) == (3, 2)

    # The same field edited in both tabs may be overwritten, but only after confirmation.
    page_b.reload(wait_until="domcontentloaded")
    expect(page_b.locator("#meeting-title")).to_have_text("Title from A")
    page_a.get_by_role("button", name="Sửa tên và ngày").click()
    page_a.locator("#edit-title").fill("A wins")
    page_b.get_by_role("button", name="Sửa tên và ngày").click()
    page_b.locator("#edit-title").fill("B first")
    page_b.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_b.locator("#meeting-title")).to_have_text("B first")
    page_a.get_by_role("button", name="Lưu thay đổi").click()
    expect(page_a.locator("#edit-conflict")).to_be_visible()
    expect(page_a.locator("#edit-title")).to_have_value("A wins")
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert stored["title"] == "B first"
    page_a.get_by_role("button", name="Lưu bản nháp lên bản mới nhất").click()
    expect(page_a.locator("#meeting-title")).to_have_text("A wins")


def test_calendar_does_not_add_history_entries_or_revive_stale_return_target(live, browser_context):
    _, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Back target", "2026-10-14")
    page.goto(f"{live.url}/", wait_until="domcontentloaded")

    page.locator("#recent-list a").first.click()
    page.wait_for_url(f"{live.url}/meetings/{meeting_id}")
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#calendar-view")).to_be_visible()
    assert page.url == f"{live.url}/meetings/{meeting_id}", "the calendar must not change the URL"

    # Browser Back from the calendar goes to the previous page, not to a stale meeting.
    page.go_back()
    page.wait_for_url(f"{live.url}/")
    expect(page.locator("#home-view")).to_be_visible()
    expect(page.locator("#calendar-view")).to_be_hidden()
    page.get_by_role("button", name="Mở lịch").click()
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#home-view")).to_be_visible()
    expect(page.locator("#meeting-view")).to_be_hidden()
    assert page.url == f"{live.url}/"

    # Returning from the calendar adds no entry: one Back from the meeting reaches home.
    page.locator("#recent-list a").first.click()
    page.wait_for_url(f"{live.url}/meetings/{meeting_id}")
    page.get_by_role("button", name="Mở lịch").click()
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-title")).to_have_text("Back target")
    page.go_back()
    page.wait_for_url(f"{live.url}/")
    expect(page.locator("#home-view")).to_be_visible()


def test_search_failure_is_an_error_not_an_empty_result(live, browser_context):
    _, page = browser_context
    seed_meeting(live.settings.data_dir, "Alpha review", "2026-10-14")
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    search = page.get_by_label("Tìm cuộc họp theo tên")

    page.route(re.compile(r"/api/meetings\?q="), lambda route: route.fulfill(status=500, body="{}"))
    search.fill("Alpha")
    expect(page.locator("#search-error")).to_be_visible()
    expect(page.locator("#search-empty")).to_be_hidden()

    page.unroute(re.compile(r"/api/meetings\?q="))
    search.fill("Alph")
    expect(page.locator("#search-error")).to_be_hidden()
    expect(page.locator("#recent-list a")).to_have_count(1)
    search.fill("zzz")
    expect(page.locator("#search-empty")).to_be_visible()
    expect(page.locator("#search-error")).to_be_hidden()


def test_negative_utc_offset_keeps_date_only_values_and_local_today(live, signed_in):
    # 05:00 UTC on 17 Oct is still the 16th in American Samoa (UTC-11).
    context, page = signed_in(timezone="Pacific/Pago_Pago", now="2026-10-17T05:00:00Z")
    meeting_id = seed_meeting(live.settings.data_dir, "Late night", "2026-10-14")
    seed_meeting(live.settings.data_dir, "Year end", "2025-12-31")
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")

    expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-14")
    expect(page.locator("#meeting-date")).to_contain_text("14 tháng 10")
    expect(page.locator("#recent-list .link-date").first).to_have_text("14/10/2026 · 1 giây")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    expect(page.locator("#edit-date")).to_have_value("2026-10-14")
    page.locator("#edit-cancel").click()

    page.get_by_role("button", name="Mở lịch").click()
    large = page.locator("#large-calendar")
    expect(large.locator(".cal-day.is-today")).to_have_attribute("data-date", "2026-10-16")
    expect(large.locator('.cal-day[data-date="2026-10-14"] .cal-count')).to_have_text("1")
    large.locator(".cal-month").select_option("11")
    large.locator(".cal-year").fill("2025")
    large.locator(".cal-year").press("Enter")
    expect(large.locator('.cal-day[data-date="2025-12-31"] .cal-count')).to_have_text("1")


def test_mini_calendar_opens_large_calendar_and_supports_keyboard(
    live, browser_context, monkeypatch
):
    _, page = browser_context
    seed_meeting(live.settings.data_dir, "Mini target", "2026-10-14")
    seed_meeting(live.settings.data_dir, "Mini undated")
    history_request_started = threading.Event()
    history_request_release = threading.Event()
    original_list_meetings = routes_module.list_meetings

    def delayed_list_meetings(data_dir, *, query=None):
        if query is None:
            history_request_started.set()
            history_request_release.wait(timeout=5)
        return original_list_meetings(data_dir, query=query)

    monkeypatch.setattr(routes_module, "list_meetings", delayed_list_meetings)
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    assert history_request_started.wait(timeout=2)
    mini = page.locator("#mini-calendar")
    calendar = page.locator("#calendar-view")
    expect(calendar).to_be_hidden()

    mini.locator(".cal-day.is-selected").focus()
    history_request_release.set()
    expect(mini.locator('.cal-day[data-date="2026-10-14"] .cal-count')).to_have_text("1")
    page.keyboard.press("ArrowRight")
    expect(mini.locator(".cal-day.is-selected")).to_have_attribute("data-date", "2026-10-18")
    assert page.evaluate("document.activeElement.closest('#mini-calendar') !== null")
    assert page.evaluate("document.activeElement.dataset.date") == "2026-10-18"
    expect(calendar).to_be_hidden()
    page.keyboard.press("Enter")
    expect(calendar).to_be_visible()
    expect(page.locator("#day-panel-title")).to_have_text("18/10/2026")
    page.get_by_role("button", name="Quay lại notes").click()
    expect(calendar).to_be_hidden()

    mini.locator('.cal-day[data-date="2026-10-14"]').click()
    expect(calendar).to_be_visible()
    expect(page.locator('#large-calendar .cal-day[data-date="2026-10-14"]')).to_have_class(
        re.compile(r"is-selected")
    )
    expect(page.locator("#day-panel-title")).to_have_text("14/10/2026")
    expect(page.locator("#day-panel-list a")).to_have_count(1)
    page.get_by_role("button", name="Quay lại notes").click()
    expect(calendar).to_be_hidden()

    mini.locator(".cal-undated").click()
    expect(calendar).to_be_visible()
    expect(page.locator("#day-panel-title")).to_have_text("Chưa đặt ngày")
    expect(page.locator("#day-panel-list a")).to_contain_text(["Mini undated"])


def hold_first(page, pattern, method):
    """Hold the first matching request until the test releases it; later ones pass."""
    held: list = []

    def handler(route):
        if route.request.method == method and not held:
            held.append(route)
        else:
            route.fallback()

    page.route(re.compile(pattern), handler)
    return held


def settle(page, milliseconds=300):
    page.evaluate(f"new Promise(resolve => setTimeout(resolve, {milliseconds}))")


def wait_for_stored_title(context, live, meeting_id, title):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
        if stored["title"] == title:
            return stored
        time.sleep(0.05)
    raise AssertionError(f"{title!r} was never stored")


def audio_meeting_id(page):
    return page.locator("#meeting-audio").get_attribute("data-meeting-id")


def test_slow_save_never_repaints_after_navigating_elsewhere(live, browser_context):
    context, page = browser_context
    a = seed_meeting(live.settings.data_dir, "Meeting A", "2026-10-14")
    b = seed_meeting(live.settings.data_dir, "Meeting B", "2026-10-13")
    page.goto(f"{live.url}/meetings/{a}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Meeting A")

    # Save A, then open B before the PATCH returns.
    held = hold_first(page, rf"/api/meetings/{a}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("A renamed")
    page.get_by_role("button", name="Lưu thay đổi").click()
    expect(page.locator("#edit-save")).to_be_disabled()
    page.locator("#recent-list a").filter(has_text="Meeting B").click()
    page.wait_for_url(f"{live.url}/meetings/{b}")
    expect(page.locator("#meeting-title")).to_have_text("Meeting B")
    held[0].continue_()
    wait_for_stored_title(context, live, a, "A renamed")
    settle(page)
    expect(page.locator("#meeting-title")).to_have_text("Meeting B")
    expect(page.locator("#page-title")).to_have_text("Meeting B")
    assert page.title() == "Meeting B · ASR EN VI"
    assert page.url == f"{live.url}/meetings/{b}"
    assert audio_meeting_id(page) == b
    expect(page.locator("#meeting-edit")).to_be_hidden()
    expect(page.locator("#edit-status")).to_have_text("")
    expect(page.locator("#recent-list")).to_contain_text("A renamed")  # lists still learn of it

    # Save B, then open the calendar before the PATCH returns.
    held = hold_first(page, rf"/api/meetings/{b}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("B renamed")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#calendar-view")).to_be_visible()
    held[0].continue_()
    wait_for_stored_title(context, live, b, "B renamed")
    settle(page)
    expect(page.locator("#calendar-view")).to_be_visible()
    expect(page.locator("#meeting-view")).to_be_hidden()
    expect(page.locator("#page-title")).to_have_text("Lịch cuộc họp")
    assert page.title() == "Lịch cuộc họp · ASR EN VI"
    assert page.url == f"{live.url}/meetings/{b}"
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-title")).to_have_text("B renamed")
    expect(page.locator("#meeting-edit")).to_be_hidden()


def test_slow_conflict_lookup_never_repaints_after_navigating_elsewhere(live, browser_context):
    context, page = browser_context
    a = seed_meeting(live.settings.data_dir, "Conflict A", "2026-10-14")
    b = seed_meeting(live.settings.data_dir, "Conflict B", "2026-10-13")
    page.goto(f"{live.url}/meetings/{a}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Conflict A")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("Draft A")

    other_tab = context.request.patch(
        f"{live.url}/api/meetings/{a}",
        headers={"Origin": live.url},
        data={"expected_metadata_version": 1, "title": "From elsewhere"},
    )
    assert other_tab.ok
    # The conflict re-read of A is the next GET of A; hold it while we move on to B.
    held = hold_first(page, rf"/api/meetings/{a}$", "GET")
    page.get_by_role("button", name="Lưu thay đổi").click()
    expect(page.locator("#edit-save")).to_be_disabled()
    page.locator("#recent-list a").filter(has_text="Conflict B").click()
    page.wait_for_url(f"{live.url}/meetings/{b}")
    expect(page.locator("#meeting-title")).to_have_text("Conflict B")
    deadline = time.monotonic() + 10
    while not held and time.monotonic() < deadline:
        time.sleep(0.05)
    assert held, "the conflict lookup never started"
    held[0].continue_()
    settle(page)
    expect(page.locator("#meeting-title")).to_have_text("Conflict B")
    expect(page.locator("#page-title")).to_have_text("Conflict B")
    assert audio_meeting_id(page) == b
    expect(page.locator("#edit-conflict")).to_be_hidden()
    expect(page.locator("#meeting-edit")).to_be_hidden()
    stored = context.request.get(f"{live.url}/api/meetings/{a}").json()
    assert stored["title"] == "From elsewhere", "a conflicted save must not write"


def test_leaving_calendar_follows_the_url_even_while_loading_or_after_an_error(
    live, browser_context
):
    context, page = browser_context
    x = seed_meeting(live.settings.data_dir, "Slow meeting", "2026-10-14")

    # Calendar opened while /meetings/X is still loading: leaving loads X, not home.
    held = hold_first(page, rf"/api/meetings/{x}$", "GET")
    page.goto(f"{live.url}/meetings/{x}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-loading")).to_be_visible()
    page.get_by_role("button", name="Lịch", exact=True).click()
    expect(page.locator("#calendar-view")).to_be_visible()
    held[0].continue_()
    settle(page)
    expect(page.locator("#calendar-view")).to_be_visible()  # the late load must not repaint
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-title")).to_have_text("Slow meeting")
    assert page.url == f"{live.url}/meetings/{x}"
    assert page.evaluate("document.activeElement.id") == "meeting-title"

    # From the error view the URL still names the meeting that failed, so return there.
    page.goto(f"{live.url}/meetings/missing", wait_until="domcontentloaded")
    expect(page.locator("#meeting-error")).to_be_visible()
    page.get_by_role("button", name="Lịch", exact=True).click()
    expect(page.locator("#calendar-view")).to_be_visible()
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-error")).to_be_visible()
    assert page.url == f"{live.url}/meetings/missing"
    assert page.evaluate("document.activeElement.id") == "meeting-error-title"

    # From home, leaving lands on home with focus on the page heading.
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    page.get_by_role("button", name="Lịch", exact=True).click()
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#home-view")).to_be_visible()
    assert page.evaluate("document.activeElement.id") == "page-title"


def test_duration_rounds_before_choosing_the_unit(live, browser_context):
    _, page = browser_context
    for seconds in (0.4, 59.4, 59.5, 59.99, 90, 3599.6):
        seed_meeting(live.settings.data_dir, f"d {seconds}", "2026-10-20", duration_seconds=seconds)
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    page.get_by_role("button", name="Mở lịch").click()
    page.locator('#large-calendar .cal-day[data-date="2026-10-20"]').click()
    labels = {
        link.locator(".link-title").inner_text(): link.locator(".link-date").inner_text()
        for link in page.locator("#day-panel-list a").all()
    }
    assert labels == {
        "d 0.4": "20/10/2026 · 1 giây",
        "d 59.4": "20/10/2026 · 59 giây",
        "d 59.5": "20/10/2026 · 1 phút",
        "d 59.99": "20/10/2026 · 1 phút",
        "d 90": "20/10/2026 · 2 phút",
        "d 3599.6": "20/10/2026 · 1 giờ 00 phút",
    }
    assert not any("60 giây" in text for text in labels.values())


def test_year_box_commits_on_typing_and_enter_and_rejects_bad_years(live, browser_context):
    _, page = browser_context
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    page.get_by_role("button", name="Mở lịch").click()
    large_title = page.locator("#large-calendar .cal-title")
    mini_title = page.locator("#mini-calendar .cal-title")
    year = page.locator("#large-calendar .cal-year")
    expect(large_title).to_have_text("Tháng 10 · 2026")

    # Real key presses: partial years are ignored, the 4th digit commits, Enter keeps it.
    year.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("2031")
    expect(large_title).to_have_text("Tháng 10 · 2031")
    page.keyboard.press("Enter")
    expect(large_title).to_have_text("Tháng 10 · 2031")
    expect(mini_title).to_have_text("Tháng 10 · 2031")
    expect(page.locator("#mini-calendar .cal-year")).to_have_value("2031")

    # Intermediate and out-of-range text never corrupts state; Enter restores the real year.
    for bad in ("20", "999", "12345", ""):
        year.fill(bad)
        expect(large_title).to_have_text("Tháng 10 · 2031")
        year.press("Enter")
        expect(year).to_have_value("2031")
        expect(large_title).to_have_text("Tháng 10 · 2031")

    # Mini calendar's own year box drives both, and Enter without a change is harmless.
    mini_year = page.locator("#mini-calendar .cal-year")
    mini_year.fill("2024")
    mini_year.press("Enter")
    expect(large_title).to_have_text("Tháng 10 · 2024")
    expect(year).to_have_value("2024")


def test_year_box_blur_commits_valid_years_and_reverts_partial_ones(live, browser_context):
    _, page = browser_context
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    page.get_by_role("button", name="Mở lịch").click()
    title = page.locator("#large-calendar .cal-title")
    year = page.locator("#large-calendar .cal-year")

    year.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("2040")
    page.keyboard.press("Tab")  # blur with a valid year keeps it
    expect(title).to_have_text("Tháng 10 · 2040")
    expect(year).to_have_value("2040")
    expect(page.locator("#mini-calendar .cal-year")).to_have_value("2040")

    for partial in ("99", "20", "12345"):
        year.click()
        page.keyboard.press("Control+A")
        year.fill(partial)  # one input event, so no valid prefix is typed on the way
        page.keyboard.press("Tab")  # blur with an intermediate/invalid year reverts it
        expect(year).to_have_value("2040")
        expect(title).to_have_text("Tháng 10 · 2040")
        expect(page.locator("#mini-calendar .cal-title")).to_have_text("Tháng 10 · 2040")

    # Blurring by clicking a day must not swallow that click.
    year.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("20")
    page.locator('#large-calendar .cal-day[data-date="2040-10-15"]').click()
    expect(page.locator("#day-panel-title")).to_have_text("15/10/2040")
    expect(year).to_have_value("2040")


def test_background_history_refresh_does_not_overwrite_partial_year_text(live, browser_context):
    _, page = browser_context
    seed_meeting(live.settings.data_dir, "Refresh target", "2026-10-14")
    page.goto(f"{live.url}/", wait_until="domcontentloaded")
    expect(page.locator("#recent-list a")).to_have_count(1)

    held = hold_first(page, r"/api/meetings$", "GET")  # the refresh the calendar triggers
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#calendar-view")).to_be_visible()
    year = page.locator("#large-calendar .cal-year")
    year.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("20")
    deadline = time.monotonic() + 10
    while not held and time.monotonic() < deadline:
        time.sleep(0.05)
    assert held, "the calendar's history refresh never started"
    held[0].continue_()
    settle(page)

    expect(year).to_have_value("20")
    assert page.evaluate("document.activeElement.classList.contains('cal-year')")
    expect(page.locator("#large-calendar .cal-title")).to_have_text("Tháng 10 · 2026")
    # The refresh itself did land: the data is on the calendar.
    expect(
        page.locator('#large-calendar .cal-day[data-date="2026-10-14"] .cal-count')
    ).to_have_text("1")
    page.keyboard.press("Tab")
    expect(year).to_have_value("2026")


def release_when_held(held):
    deadline = time.monotonic() + 10
    while not held and time.monotonic() < deadline:
        time.sleep(0.05)
    assert held, "the request never started"
    held[0].continue_()


def test_save_released_after_a_calendar_round_trip_is_rendered_and_saved(live, browser_context):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Round trip", "2026-10-14")
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Round trip")

    held = hold_first(page, rf"/api/meetings/{meeting_id}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("After round trip")
    page.locator("#edit-date").fill("2026-10-20")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#calendar-view")).to_be_visible()
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-title")).to_have_text("Round trip")  # nothing saved yet
    release_when_held(held)

    expect(page.locator("#meeting-title")).to_have_text("After round trip")
    expect(page.locator("#page-title")).to_have_text("After round trip")
    expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-20")
    expect(page.locator("#edit-status")).to_have_text("Đã lưu tên và ngày họp.")
    expect(page.locator("#meeting-edit")).to_be_hidden()
    expect(page.locator("#edit-meeting")).to_be_enabled()
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert (stored["title"], stored["meeting_date"]) == ("After round trip", "2026-10-20")
    expect(page.locator("#recent-list")).to_contain_text("After round trip")


def test_save_result_arriving_while_the_calendar_is_open_shows_after_leaving(live, browser_context):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Quiet save", "2026-10-14")
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    held = hold_first(page, rf"/api/meetings/{meeting_id}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("Saved in background")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_role("button", name="Mở lịch").click()
    release_when_held(held)
    wait_for_stored_title(context, live, meeting_id, "Saved in background")
    settle(page)
    expect(page.locator("#page-title")).to_have_text("Lịch cuộc họp")  # calendar untouched

    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#meeting-title")).to_have_text("Saved in background")
    expect(page.locator("#edit-status")).to_have_text("Đã lưu tên và ngày họp.")
    expect(page.locator("#meeting-edit")).to_be_hidden()


def test_conflict_arriving_around_a_calendar_round_trip_is_not_lost(live, browser_context):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Conflict trip", "2026-10-14")
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")

    def other_tab_renames(title, version):
        response = context.request.patch(
            f"{live.url}/api/meetings/{meeting_id}",
            headers={"Origin": live.url},
            data={"expected_metadata_version": version, "title": title},
        )
        assert response.ok

    # Conflict lands after returning from the calendar.
    held = hold_first(page, rf"/api/meetings/{meeting_id}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("My draft")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_role("button", name="Mở lịch").click()
    page.get_by_role("button", name="Quay lại notes").click()
    other_tab_renames("Other tab one", 1)
    release_when_held(held)
    expect(page.locator("#edit-conflict")).to_contain_text("Other tab one")
    expect(page.locator("#edit-title")).to_have_value("My draft")
    expect(page.locator("#meeting-title")).to_have_text("Other tab one")
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert stored["title"] == "Other tab one"

    # Conflict lands while the calendar is open: it is waiting after leaving.
    page.get_by_role("button", name="Hủy và bỏ bản nháp").click()
    held = hold_first(page, rf"/api/meetings/{meeting_id}$", "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("Second draft")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_role("button", name="Mở lịch").click()
    other_tab_renames("Other tab two", 2)
    release_when_held(held)
    wait_for_stored_title(context, live, meeting_id, "Other tab two")
    settle(page)
    expect(page.locator("#page-title")).to_have_text("Lịch cuộc họp")
    page.get_by_role("button", name="Quay lại notes").click()
    expect(page.locator("#edit-conflict")).to_contain_text("Other tab two")
    expect(page.locator("#edit-title")).to_have_value("Second draft")
    expect(page.locator("#meeting-title")).to_have_text("Other tab two")
    expect(page.locator("#edit-save")).to_have_text("Lưu bản nháp lên bản mới nhất")


def fetch_now_deliver_later(page, pattern):
    """Let the first GET reach the server immediately, but hold its response back.

    Unlike holding the request, this freezes the *content* at the moment of the read, so a
    later release delivers genuinely stale data regardless of timing.
    """
    held: list = []

    def handler(route):
        if route.request.method == "GET" and not held:
            held.append((route, route.fetch()))
        else:
            route.fallback()

    page.route(re.compile(pattern), handler)
    return held


def test_stale_meeting_read_answering_after_a_save_cannot_roll_the_ui_back(live, browser_context):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Before save", "2026-10-14")
    meeting_path = rf"/api/meetings/{meeting_id}$"
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Before save")
    patches = record_patches(page)

    # 1. Start a save (version 1 -> 2) and keep its PATCH from reaching the server.
    held_patch = hold_first(page, meeting_path, "PATCH")
    page.get_by_role("button", name="Sửa tên và ngày").click()
    page.locator("#edit-title").fill("After save")
    page.locator("#edit-date").fill("2026-10-20")
    page.get_by_role("button", name="Lưu thay đổi").click()

    # 2. Detour through the calendar; leaving re-reads the meeting. That read hits the
    #    server now, while the title is still "Before save", but its response is held.
    page.get_by_role("button", name="Mở lịch").click()
    expect(page.locator("#calendar-view")).to_be_visible()
    held_read = fetch_now_deliver_later(page, meeting_path)
    page.get_by_role("button", name="Quay lại notes").click()
    deadline = time.monotonic() + 10
    while not held_read and time.monotonic() < deadline:
        page.wait_for_timeout(50)  # route handlers only run while we are inside Playwright
    assert held_read, "leaving the calendar never re-read the meeting"
    stale_route, stale_response = held_read[0]
    assert stale_response.json()["title"] == "Before save"
    assert stale_response.json()["metadata_version"] == 1

    # 3. Now the save lands and the UI shows it.
    release_when_held(held_patch)
    wait_for_stored_title(context, live, meeting_id, "After save")
    expect(page.locator("#meeting-title")).to_have_text("After save")
    expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-20")

    # 4. The stale (version 1) read finally answers. It must not roll anything back.
    stale_route.fulfill(response=stale_response)
    settle(page)
    expect(page.locator("#meeting-title")).to_have_text("After save")
    expect(page.locator("#page-title")).to_have_text("After save")
    expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-20")
    assert page.title() == "After save · ASR EN VI"

    # The model kept version 2: the next edit saves cleanly instead of conflicting.
    page.get_by_role("button", name="Sửa tên và ngày").click()
    expect(page.locator("#edit-title")).to_have_value("After save")
    expect(page.locator("#edit-date")).to_have_value("2026-10-20")
    page.locator("#edit-title").fill("Third title")
    page.get_by_role("button", name="Lưu thay đổi").click()
    expect(page.locator("#meeting-title")).to_have_text("Third title")
    expect(page.locator("#edit-conflict")).to_be_hidden()
    assert patches[-1] == {"expected_metadata_version": 2, "title": "Third title"}
    stored = context.request.get(f"{live.url}/api/meetings/{meeting_id}").json()
    assert (stored["title"], stored["meeting_date"], stored["metadata_version"]) == (
        "Third title",
        "2026-10-20",
        3,
    )


def test_runtime_profile_and_saved_status_render_without_collapsing(live, browser_context):
    _context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Runtime profile")
    lock_fd = acquire_worker_lock(live.settings.data_dir)
    assert lock_fd is not None
    write_runtime_profile(
        live.settings.data_dir,
        RuntimeProfile(
            device="cuda",
            compute_type="float16",
            model_path="/models/whisper-large-v3",
        ),
    )
    write_heartbeat(live.settings.data_dir, "idle")
    try:
        page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
        expect(page.locator("#runtime-backend")).to_have_text("GPU · CUDA · float16")
        expect(page.locator("#runtime-model")).to_have_text("whisper-large-v3")
        expect(page.locator("#meeting-status-text")).to_have_text("Đã lưu, chưa xử lý")
        assert page.locator("#meeting-status-text").bounding_box()["width"] > 80
    finally:
        os.close(lock_fd)


def test_transcription_requires_explicit_start_and_renders_poll_cancel_and_rerun(
    live, browser_context
):
    context, page = browser_context
    meeting_id = seed_meeting(live.settings.data_dir, "Transcript controls", duration_seconds=30)
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Transcript controls")
    post_bodies: list[dict[str, object]] = []
    tasks: dict[str, dict[str, object]] = {}
    current_generation: dict[str, object] | None = None
    task_number = 0

    def task_response(
        task_id,
        status,
        *,
        request_id="browser-request-id",
        worker_state=None,
        segment_count=1,
        end_seconds=4.25,
    ):
        return {
            "id": task_id,
            "request_id": request_id,
            "meeting_id": meeting_id,
            "kind": "transcription",
            "status": status,
            "worker_state": worker_state
            or ("healthy" if status in {"running", "stopping"} else "idle"),
            "stage": "transcribing" if status == "running" else status,
            "result_scope": "transcript_only" if status == "succeeded" else None,
            "audio_duration_seconds": 30,
            "transcript_end_seconds": end_seconds,
            "segment_count": segment_count,
            "elapsed_seconds": 2.5,
            "error_code": None,
            "error_message": None,
            "accepted_at": "2026-10-17 00:00:00",
            "started_at": "2026-10-17 00:00:00",
            "heartbeat_at": "2026-10-17 00:00:02",
            "cancel_requested_at": None,
            "completed_at": None,
            "updated_at": "2026-10-17 00:00:02",
        }

    def generation_response(number):
        return {
            "id": f"generation-{number}",
            "generation_number": number,
            "status": "complete",
            "language_hint": "en",
            "model_name": "whisper-large-v3",
            "language_probability": 0.94,
            "source_version": 1,
            "uncertainty_policy": "faster-whisper-review-cues-v1",
            "segment_count": 1,
            "completed_at": "2026-10-17 00:00:05",
            "segments": [
                {
                    "id": f"{number:032x}",
                    "sequence": 0,
                    "start_seconds": 1.25,
                    "end_seconds": 4.25,
                    "text": f"Transcript generation {number}.",
                    "original_speaker_id": None,
                    "speaker_id": None,
                    "avg_logprob": -0.3,
                    "no_speech_prob": 0.02,
                    "compression_ratio": 0.8,
                    "uncertain": False,
                }
            ],
        }

    def route_task_requests(route):
        nonlocal current_generation, task_number
        path = route.request.url.removeprefix(live.url)
        if route.request.method == "POST" and path == "/api/tasks":
            post_bodies.append(route.request.post_data_json)
            if len(post_bodies) == 1:
                route.abort("connectionfailed")
                return
            if len(post_bodies) == 4:
                route.fulfill(
                    status=409,
                    content_type="application/json",
                    body=json.dumps(
                        {"detail": {"code": "system_busy", "message": "Slot is busy."}}
                    ),
                )
                return
            task_number += 1
            task_id = f"browser-task-{task_number}"
            request_id = post_bodies[-1]["request_id"]
            tasks[task_id] = {"polls": 0, "status": "running", "request_id": request_id}
            route.fulfill(
                status=202,
                content_type="application/json",
                body=json.dumps(
                    task_response(
                        task_id,
                        "running",
                        request_id=request_id,
                        worker_state="checking-worker",
                    )
                ),
            )
            return
        if route.request.method == "POST" and path.endswith("/cancel"):
            task_id = path.split("/")[-2]
            tasks[task_id]["status"] = "canceled"
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    task_response(
                        task_id,
                        "stopping",
                        request_id=tasks[task_id]["request_id"],
                    )
                ),
            )
            return
        if route.request.method == "GET" and path.startswith("/api/tasks/"):
            task_id = path.rsplit("/", 1)[-1]
            task = tasks[task_id]
            if task["status"] == "canceled":
                payload = task_response(task_id, "canceled", request_id=task["request_id"])
            else:
                task["polls"] = int(task["polls"]) + 1
                if task["polls"] >= 2:
                    task["status"] = "succeeded"
                    current_generation = generation_response(task_number)
                payload = task_response(task_id, str(task["status"]), request_id=task["request_id"])
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
            return
        if (
            route.request.method == "GET"
            and path == f"/api/meetings/{meeting_id}"
            and current_generation
        ):
            response = route.fetch()
            payload = response.json()
            payload["transcription"]["generation"] = current_generation
            payload["transcription"]["task"] = task_response(
                f"browser-task-{task_number}",
                "succeeded",
                request_id=post_bodies[-1]["request_id"],
            )
            route.fulfill(response=response, json=payload)
            return
        route.fallback()

    page.route(
        re.compile(r"/api/(?:tasks(?:/[^/]+(?:/cancel)?)?|meetings/[^/]+)$"), route_task_requests
    )
    assert post_bodies == []  # Reopening an imported meeting never starts ASR.
    start_button = page.get_by_role("button", name="Bắt đầu chép lời")
    expect(start_button).to_be_visible()
    assert "%" not in page.locator("#transcription-panel").inner_text()
    assert "ETA" not in page.locator("#transcription-panel").inner_text()

    start_button.click()
    expect(page.locator("#transcription-error")).to_be_visible(timeout=5_000)
    expect(start_button).to_be_visible()
    start_button.click()
    expect(page.locator("#transcription-status")).to_contain_text("Đang kiểm tra worker")
    expect(page.locator("#transcription-status")).to_have_attribute(
        "data-worker-state", "checking-worker"
    )
    expect(page.locator("#transcript-generation")).to_be_visible(timeout=8_000)
    expect(page.locator("#generation-title")).to_have_text("Transcript #1")
    expect(page.locator(".segment-text")).to_have_text("Transcript generation 1.")
    expect(page.locator(".segment-timestamp")).to_have_text("0:01.25")
    assert post_bodies[0]["request_id"] == post_bodies[1]["request_id"]

    rerun = page.get_by_role("button", name="Chạy lại bản ghi")
    rerun.click()
    expect(page.locator("#generation-title")).to_have_text("Transcript #2", timeout=8_000)
    assert post_bodies[2]["request_id"] != post_bodies[1]["request_id"]

    rerun.click()
    expect(page.locator("#transcription-error")).to_be_visible(timeout=5_000)
    rerun.click()
    expect(page.get_by_role("button", name="Hủy xử lý")).to_be_visible()
    assert post_bodies[3]["request_id"] != post_bodies[2]["request_id"]
    assert post_bodies[4]["request_id"] != post_bodies[3]["request_id"]
    page.get_by_role("button", name="Hủy xử lý").click()
    expect(page.locator("#transcription-status")).to_contain_text("Đã hủy", timeout=5_000)
    expect(page.locator("#generation-title")).to_have_text("Transcript #2")
    assert len(post_bodies) == 5
