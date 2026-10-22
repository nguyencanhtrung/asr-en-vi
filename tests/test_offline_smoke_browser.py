from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect
from seeding import seed_meeting
from test_browser_history import live as live
from test_browser_history import signed_in as signed_in

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "offline-smoke.py"
SPEC = importlib.util.spec_from_file_location("offline_smoke_browser_harness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
offline_smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = offline_smoke
SPEC.loader.exec_module(offline_smoke)

pytestmark = pytest.mark.browser


def test_undated_history_fixture_uses_calendar_group_to_open(live, signed_in):
    meeting_title = "Offline smoke undated history target"
    meeting_id = seed_meeting(live.settings.data_dir, meeting_title)
    _context, page = signed_in()
    page.set_default_timeout(5_000)
    assert page.url == f"{live.url}/"

    # The smoke previously waited for this link immediately after opening `/`.
    # An undated meeting is not in the recent list until its calendar group is selected.
    meeting_link = page.locator(f'a[href="/meetings/{meeting_id}"]')
    with pytest.raises(PlaywrightTimeoutError):
        meeting_link.wait_for(state="visible", timeout=350)

    stages: list[str] = []

    def record_stage(name: str) -> None:
        stages.append(name)
        if name == "open_matching_day_panel_link":
            expect(page.locator("#day-panel-title")).to_have_text("Chưa đặt ngày")
            expect(
                page.locator(f'#day-panel-list a[href="/meetings/{meeting_id}"]')
            ).to_be_visible()

    offline_smoke.open_undated_history_meeting(page, meeting_id, on_stage=record_stage)

    assert stages == [
        "select_undated_calendar_group",
        "open_matching_day_panel_link",
        "wait_for_meeting_view",
    ]
    expect(page.locator("#meeting-title")).to_have_text(meeting_title, timeout=5_000)
