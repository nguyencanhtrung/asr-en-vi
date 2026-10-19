from __future__ import annotations

import hashlib
import json
import sqlite3
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from notes_helpers import StubNotesProvider, seed_completed_transcript
from playwright.sync_api import expect
from test_browser_history import live as live
from test_browser_history import signed_in as signed_in

from asr_en_vi import notes_routes
from asr_en_vi.media import normalize_media
from asr_en_vi.notes import (
    accept_notes_task,
    get_note,
    get_notes_source,
    publish_notes_revision,
    update_note,
)
from asr_en_vi.notes_document import render_markdown
from asr_en_vi.storage import database_path
from asr_en_vi.tasks import claim_next_task

pytestmark = pytest.mark.browser


def test_notes_late_asset_still_receives_current_meeting_context(live, signed_in):
    _context, page = signed_in()
    meeting_id, _generation_id, _segments = seed_completed_transcript(live.settings.data_dir)
    held_assets = []
    page.route(f"{live.url}/assets/notes.js", lambda route: held_assets.append(route))
    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="commit")
    expect(page.locator("#meeting-title")).to_have_text("Planning meeting")
    assert len(held_assets) == 1
    held_assets.pop().continue_()
    expect(page.locator("#notes-start")).to_be_enabled()
    expect(page.locator(".segment-text-editor").first).to_be_enabled()


@pytest.fixture
def fake_notes_provider(monkeypatch):
    original_accept = notes_routes.accept_notes_task

    def accept_with_stub(data_dir, *, provider, **kwargs):
        return original_accept(data_dir, provider=StubNotesProvider(), **kwargs)

    monkeypatch.setattr(notes_routes, "accept_notes_task", accept_with_stub)
    monkeypatch.setattr(notes_routes, "worker_is_healthy", lambda _path: True)


def _markdown(snapshot: dict[str, object]) -> str:
    segment_ids = [segment["id"] for segment in snapshot["segments"]]
    document = {
        "schema_version": 1,
        "overview": [
            {"text": "The team reviewed its launch plan.", "source_ids": [segment_ids[0]]}
        ],
        "key_topics": [
            {"text": "The team needs a short written draft.", "source_ids": [segment_ids[0]]}
        ],
        "decisions": [{"text": "Prepare the launch plan.", "source_ids": [segment_ids[0]]}],
        "open_questions": [{"text": "Who will review the draft?", "source_ids": [segment_ids[1]]}],
        "action_items": [
            {
                "text": "Send the draft.",
                "source_ids": [segment_ids[1]],
                "owner": "Morgan",
                "deadline_text": "tomorrow",
                "deadline_date": None,
            }
        ],
        "confirmation_items": [
            {"text": "Confirm the review date.", "source_ids": [segment_ids[1]]}
        ],
    }
    return render_markdown(document, snapshot)


def _accept(
    data_dir: Path,
    meeting_id: str,
    generation_id: str,
    *,
    request_id: str,
    expected_source_version: int = 1,
):
    return accept_notes_task(
        data_dir,
        provider=StubNotesProvider(),
        meeting_id=meeting_id,
        request_id=request_id,
        expected_generation_id=generation_id,
        expected_source_version=expected_source_version,
        expected_metadata_version=1,
        worker_ready=True,
    )


def _complete_fake_task(data_dir: Path, task_id: str, request_id: str, markdown: str):
    owner_id = f"notes-browser-worker-{request_id}"
    claimed = claim_next_task(data_dir, owner_id=owner_id)
    assert claimed is not None and claimed["id"] == task_id
    revision = publish_notes_revision(
        data_dir,
        task_id,
        owner_id=owner_id,
        markdown=markdown,
        elapsed_seconds=0.1,
    )
    assert revision is not None
    return revision


def _task_source_id(data_dir: Path, task_id: str) -> str:
    with sqlite3.connect(database_path(data_dir)) as connection:
        row = connection.execute(
            "SELECT notes_source_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    assert row is not None and row[0]
    return row[0]


def _write_test_recording(data_dir: Path, meeting_id: str, tmp_path: Path) -> Path:
    with sqlite3.connect(database_path(data_dir)) as connection:
        row = connection.execute(
            "SELECT storage_key FROM recordings WHERE meeting_id = ?", (meeting_id,)
        ).fetchone()
    assert row is not None
    audio_path = data_dir / row[0]
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    wave_path = tmp_path / "notes-source.wav"
    with wave.open(str(wave_path), "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16_000)
        recording.writeframes(b"\x00\x00" * 16_000 * 30)
    normalize_media(wave_path, audio_path, max_duration_seconds=60)
    return audio_path


def _browser_diagnostics(page):
    console_errors: list[str] = []
    page_errors: list[str] = []
    requests: list[str] = []
    http_errors: list[dict[str, object]] = []
    page.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))

    def capture_http_error(response) -> None:
        if response.status >= 400:
            http_errors.append({"status": response.status, "url": response.url})

    page.on("response", capture_http_error)
    return console_errors, page_errors, requests, http_errors


def _assert_no_token_urls(urls: list[str]) -> None:
    for raw_url in urls:
        query = parse_qs(urlsplit(raw_url).query)
        assert not {key.casefold() for key in query} & {"token", "access_token"}, raw_url


def test_notes_browser_generation_revisions_conflicts_copy_export_and_markdown_safety(
    live, signed_in, fake_notes_provider, tmp_path
):
    context, page = signed_in(
        viewport={"width": 1440, "height": 1000},
        reduced_motion="reduce",
    )
    console_errors, page_errors, requests, http_errors = _browser_diagnostics(page)
    meeting_id, generation_id, _segment_ids = seed_completed_transcript(
        live.settings.data_dir,
        title="Browser notes acceptance",
        meeting_date="2026-10-19",
    )
    _write_test_recording(live.settings.data_dir, meeting_id, tmp_path)

    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#meeting-title")).to_have_text("Browser notes acceptance")
    expect(page.locator("#notes-start")).to_be_enabled()

    note_requests: list[dict[str, object]] = []

    def capture_request(request) -> None:
        if request.method == "POST" and request.url.endswith("/notes-runs"):
            note_requests.append(json.loads(request.post_data or "{}"))

    page.on("request", capture_request)
    with page.expect_response(
        lambda response: response.url.endswith("/notes-runs") and response.request.method == "POST"
    ) as accepted_response:
        page.locator("#notes-start").click()
    assert accepted_response.value.status == 202
    accepted = accepted_response.value.json()
    assert accepted["kind"] == "notes" and accepted["status"] == "accepted"
    assert note_requests == [
        {
            "request_id": note_requests[0]["request_id"],
            "expected_generation_id": generation_id,
            "expected_source_version": 1,
            "expected_metadata_version": 1,
        }
    ]
    assert note_requests[0]["request_id"]

    source_id = _task_source_id(live.settings.data_dir, accepted["id"])
    snapshot = get_notes_source(live.settings.data_dir, source_id)
    first_markdown = _markdown(snapshot)
    first_revision = _complete_fake_task(
        live.settings.data_dir,
        accepted["id"],
        "initial",
        first_markdown,
    )
    expect(page.locator("#notes-saved-work")).to_be_visible(timeout=10_000)
    expect(page.locator("#notes-task-state")).to_have_text("Đã lưu")
    expect(page.locator("#notes-task-stage")).to_have_text("Đã lưu")
    expect(page.locator("#meeting-status-text")).to_have_text("Đã có transcript và notes")
    assert page.locator("#notes-preview h3").all_text_contents() == [
        "Overview",
        "Key Topics and Rationale",
        "Decisions",
        "Open Questions",
        "Confirmed Action Items",
        "Items Requiring Confirmation",
    ]
    expect(page.locator("#notes-preview")).to_contain_text("Prepare the launch plan.")
    expect(page.locator("#notes-preview")).to_contain_text("Send the draft.")
    expect(page.locator("#notes-preview a[data-notes-source-link]")).to_have_count(6)
    assert "token=" not in page.url and "access_token=" not in page.url

    screenshots = Path("/tmp/asr-issue9/screenshots")
    screenshots.mkdir(parents=True, exist_ok=True)
    page.evaluate("document.fonts.ready")
    desktop_overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    desktop_capture = screenshots / "issue9-notes-desktop.png"
    page.screenshot(path=str(desktop_capture), full_page=True, animations="disabled")

    page.set_viewport_size({"width": 390, "height": 844})
    narrow_overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    narrow_capture = screenshots / "issue9-notes-narrow.png"
    page.screenshot(path=str(narrow_capture), full_page=True, animations="disabled")
    assert desktop_capture.stat().st_size > 10_000
    assert narrow_capture.stat().st_size > 10_000
    assert desktop_overflow == 0
    assert narrow_overflow == 0

    draft = "# Local draft\n\nMy unsaved change is still here.\n"
    page.locator("#notes-markdown").fill(draft)
    second_task = _accept(
        live.settings.data_dir,
        meeting_id,
        generation_id,
        request_id="browser-notes-revision-002",
    )
    second_source = get_notes_source(
        live.settings.data_dir,
        _task_source_id(live.settings.data_dir, second_task["id"]),
    )
    second_markdown = "# Newer revision\n\nThis is a second saved revision.\n"
    second_revision = _complete_fake_task(
        live.settings.data_dir,
        second_task["id"],
        "second",
        second_markdown,
    )
    assert second_revision["source_snapshot_id"] == second_source["id"]
    page.evaluate(f"window.ASRMeetingHistory.refreshMeeting('{meeting_id}')")
    expect(page.locator("#notes-revision-selector option")).to_have_count(2, timeout=10_000)
    expect(page.locator("#notes-revision-selector")).to_have_value(first_revision["id"])
    expect(page.locator("#notes-markdown")).to_have_value(draft)
    expect(page.locator("#notes-draft-status")).to_contain_text("chưa lưu")

    remote_markdown = "# Another editor\n\nSaved before this draft.\n"
    update_note(
        live.settings.data_dir,
        first_revision["id"],
        expected_edit_version=1,
        markdown=remote_markdown,
    )
    with page.expect_response(lambda response: response.status == 409) as conflict_response:
        page.locator("#notes-save").click()
    expect(page.locator("#notes-conflict")).to_be_visible(timeout=10_000)
    expect(page.locator("#notes-markdown")).to_have_value(draft)
    expect(page.locator("#notes-conflict-message")).to_contain_text("Bản nháp của bạn vẫn được giữ")
    page.locator("#notes-keep-draft").click()
    expect(page.locator("#notes-conflict")).to_be_hidden(timeout=10_000)
    expect(page.locator("#notes-markdown")).to_have_value(draft)
    expect(page.locator("#notes-revision-meta")).to_contain_text("Edit 3")
    assert get_note(live.settings.data_dir, first_revision["id"])["markdown"] == draft

    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=live.url)
    page.locator("#notes-copy").click()
    expect(page.locator("#notes-copy-export-status")).to_contain_text("edit 3", timeout=10_000)
    assert page.evaluate("navigator.clipboard.readText()") == draft
    with page.expect_download() as download_info:
        page.locator("#notes-export").click()
    exported = download_info.value
    assert Path(exported.path()).read_text(encoding="utf-8") == draft

    hostile_markdown = (
        "# Security check\n\n"
        "<script>window.__notesXss = true</script>\n\n"
        "<img src=x onerror=window.__notesXss = true>\n\n"
        "[foreign](https://attacker.invalid/collect)\n"
    )
    update_note(
        live.settings.data_dir,
        first_revision["id"],
        expected_edit_version=3,
        markdown=hostile_markdown,
    )
    page.evaluate(f"window.ASRMeetingHistory.refreshMeeting('{meeting_id}')")
    expect(page.locator("#notes-markdown")).to_have_value(hostile_markdown, timeout=10_000)
    assert page.locator("#notes-preview script, #notes-preview img").count() == 0
    assert page.locator('#notes-preview a[href^="https://"]').count() == 0
    expect(page.locator("#notes-preview")).to_contain_text(
        "<script>window.__notesXss = true</script>"
    )
    assert page.evaluate("window.__notesXss === undefined")
    _assert_no_token_urls(requests)
    assert not any("attacker.invalid" in url for url in requests)
    diagnostics = {
        "console_errors": console_errors,
        "page_errors": page_errors,
        "http_errors": http_errors,
        "desktop_overflow_px": desktop_overflow,
        "narrow_overflow_px": narrow_overflow,
        "screenshots": [str(desktop_capture), str(narrow_capture)],
    }
    Path("/tmp/asr-issue9/notes-browser-observations.json").write_text(
        json.dumps(diagnostics, indent=2), encoding="utf-8"
    )
    assert http_errors == [{"status": 409, "url": conflict_response.value.url}]
    assert console_errors == [
        "Failed to load resource: the server responded with a status of 409 (Conflict)"
    ]
    assert not page_errors
    context.close()


def test_saved_source_stays_frozen_and_seeks_same_audio_after_live_edit(
    live, signed_in, fake_notes_provider, tmp_path
):
    context, page = signed_in(viewport={"width": 1280, "height": 900})
    console_errors, page_errors, requests, http_errors = _browser_diagnostics(page)
    meeting_id, generation_id, segment_ids = seed_completed_transcript(
        live.settings.data_dir,
        title="Frozen source browser check",
        meeting_date="2026-10-19",
    )
    audio_path = _write_test_recording(live.settings.data_dir, meeting_id, tmp_path)
    audio_digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()

    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#notes-start")).to_be_enabled()
    with page.expect_response(
        lambda response: response.url.endswith("/notes-runs") and response.request.method == "POST"
    ) as accepted_response:
        page.locator("#notes-start").click()
    assert accepted_response.value.status == 202
    accepted = accepted_response.value.json()
    source_id = _task_source_id(live.settings.data_dir, accepted["id"])
    snapshot = get_notes_source(live.settings.data_dir, source_id)
    original_text = snapshot["segments"][0]["text"]
    markdown = _markdown(snapshot)
    _complete_fake_task(live.settings.data_dir, accepted["id"], "source", markdown)
    expect(page.locator("#notes-saved-work")).to_be_visible(timeout=10_000)
    audio = page.locator("#meeting-audio")
    expect(audio).to_be_visible()
    assert audio.get_attribute("src") == f"/api/meetings/{meeting_id}/audio"
    expect(page.locator("#notes-preview a[data-notes-source-link]")).to_have_count(6)

    page.locator("#notes-preview a[data-notes-source-link]").first.click()
    expect(page.locator("#notes-source-view")).to_be_visible()
    expect(page.locator("#notes-source-text")).to_have_text(original_text)
    expect(page.locator("#notes-source-time")).to_have_text("00:00:01")
    expect(page.locator("#notes-source-status")).to_contain_text("Đã tua bản ghi", timeout=10_000)
    assert audio.evaluate("element => Math.abs(element.currentTime - 1) < 0.1")
    assert urlsplit(page.url).path == f"/meetings/{meeting_id}"
    assert parse_qs(urlsplit(page.url).query) == {
        "notes_source": [source_id],
        "segment": [segment_ids[0]],
    }

    first_segment = page.locator(".segment-edit-form").nth(0)
    editor = first_segment.locator(".segment-text-editor")
    editor.fill("The live transcript was corrected after notes generation.")
    first_segment.locator('button[type="submit"]').click()
    expect(first_segment.locator(".segment-edit-status")).to_have_text("Đã lưu.", timeout=10_000)
    expect(page.locator("#notes-source-text")).to_have_text(original_text)
    expect(audio).to_have_attribute("src", f"/api/meetings/{meeting_id}/audio")
    assert hashlib.sha256(audio_path.read_bytes()).hexdigest() == audio_digest
    page.locator("#notes-source-seek").click()
    expect(page.locator("#notes-source-status")).to_contain_text("Đã tua bản ghi", timeout=10_000)
    assert audio.evaluate("element => Math.abs(element.currentTime - 1) < 0.1")
    _assert_no_token_urls(requests)
    assert not console_errors
    assert not http_errors
    assert not page_errors
    context.close()


def test_failed_notes_read_keeps_old_revision_draft_source_and_other_meeting_navigation(
    live, signed_in, fake_notes_provider
):
    context, page = signed_in(viewport={"width": 1280, "height": 900})
    meeting_id, generation_id, _segment_ids = seed_completed_transcript(
        live.settings.data_dir,
        title="Notes read failure target",
        meeting_date="2026-10-19",
    )
    other_id, other_generation_id, _ = seed_completed_transcript(
        live.settings.data_dir,
        title="Other meeting remains usable",
        meeting_date="2026-10-18",
    )
    first_task = _accept(
        live.settings.data_dir,
        meeting_id,
        generation_id,
        request_id="browser-notes-old-revision",
    )
    source = get_notes_source(
        live.settings.data_dir,
        _task_source_id(live.settings.data_dir, first_task["id"]),
    )
    original_text = source["segments"][0]["text"]
    revision = _complete_fake_task(
        live.settings.data_dir,
        first_task["id"],
        "old-revision",
        _markdown(source),
    )
    active = _accept(
        live.settings.data_dir,
        meeting_id,
        generation_id,
        request_id="browser-notes-active-task",
    )
    assert active["status"] == "accepted"

    page.goto(f"{live.url}/meetings/{meeting_id}", wait_until="domcontentloaded")
    expect(page.locator("#notes-revision-selector")).to_have_value(revision["id"], timeout=10_000)
    expect(
        page.get_by_text("Tác vụ notes đang dùng nguồn; chỉnh sửa tạm thời bị khóa.", exact=False)
    ).to_be_visible()
    expect(page.locator(".segment-text-editor").first).to_be_disabled()
    draft = "# Draft while another notes task is running\n\nKeep this across navigation.\n"
    page.locator("#notes-markdown").fill(draft)

    page.locator("#recent-list a").filter(has_text="Other meeting remains usable").click()
    page.wait_for_url(f"{live.url}/meetings/{other_id}")
    expect(page.locator("#meeting-title")).to_have_text("Other meeting remains usable")
    expect(page.locator("#notes-start")).to_be_enabled()

    def fail_notes_read(route) -> None:
        route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": "Seeded notes-read failure"}),
        )

    page.route(f"**/api/meetings/{meeting_id}/notes", fail_notes_read)
    page.locator("#recent-list a").filter(has_text="Notes read failure target").click()
    page.wait_for_url(f"{live.url}/meetings/{meeting_id}")
    expect(page.locator("#notes-error")).to_be_visible(timeout=10_000)
    expect(page.locator("#notes-markdown")).to_have_value(draft)
    expect(page.locator("#notes-save")).to_be_enabled()
    assert page.locator("#notes-source-view").is_hidden()

    page.evaluate(
        """({ meetingId, sourceId, segmentId }) => {
          const url = `/meetings/${meetingId}?notes_source=${sourceId}&segment=${segmentId}`;
          window.history.pushState({}, "", url);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }""",
        {
            "meetingId": meeting_id,
            "sourceId": revision["source_snapshot_id"],
            "segmentId": source["segments"][0]["id"],
        },
    )
    expect(page.locator("#notes-source-view")).to_be_visible(timeout=10_000)
    expect(page.locator("#notes-source-text")).to_have_text(original_text)
    page.locator("#notes-save").click()
    expect(page.locator("#notes-copy-export-status")).to_contain_text(
        "Markdown đã được lưu", timeout=10_000
    )
    assert get_note(live.settings.data_dir, revision["id"])["markdown"] == draft

    page.unroute(f"**/api/meetings/{meeting_id}/notes")
    page.locator("#recent-list a").filter(has_text="Other meeting remains usable").click()
    page.wait_for_url(f"{live.url}/meetings/{other_id}")
    expect(page.locator("#meeting-title")).to_have_text("Other meeting remains usable")
    assert other_generation_id
    context.close()
