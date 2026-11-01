from __future__ import annotations

import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient
from seeding import seed_meeting

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.storage import database_path

pytestmark = pytest.mark.anyio


async def _authorize(client, settings) -> dict[str, str]:
    state = AuthStore(settings.auth_dir).load()
    headers = {"Origin": settings.public_url}
    response = await client.post(
        "/api/access/session", headers=headers, json={"token": state.token}
    )
    assert response.status_code == 204
    return headers


async def test_history_requires_authentication(client, settings):
    meeting_id = seed_meeting(settings.data_dir, "Private", "2026-10-01")
    headers = {"Origin": settings.public_url}

    assert (await client.get("/api/meetings")).status_code == 401
    patch = await client.patch(
        f"/api/meetings/{meeting_id}",
        headers=headers,
        json={"expected_metadata_version": 1, "title": "x"},
    )
    assert patch.status_code == 401


async def test_history_orders_by_meeting_date_and_limits_recent_to_three(client, settings):
    await _authorize(client, settings)
    seed_meeting(settings.data_dir, "undated")
    for day in ("2026-01-31", "2026-02-01", "2025-12-31", "2026-02-01", "2024-02-29"):
        seed_meeting(settings.data_dir, f"m {day}", day)

    body = (await client.get("/api/meetings")).json()

    dates = [item["meeting_date"] for item in body["meetings"]]
    assert dates == [
        "2026-02-01",
        "2026-02-01",
        "2026-01-31",
        "2025-12-31",
        "2024-02-29",
        None,
    ]
    assert [item["meeting_date"] for item in body["recent"]] == dates[:3]
    assert body["total"] == 6
    assert "created_at" not in body["meetings"][0]


async def test_history_items_carry_recording_duration_without_start_time(client, settings):
    await _authorize(client, settings)
    seed_meeting(settings.data_dir, "Long", "2026-10-01", duration_seconds=5025.5)

    body = (await client.get("/api/meetings")).json()

    assert body["meetings"][0]["duration_seconds"] == 5025.5
    assert body["recent"][0]["duration_seconds"] == 5025.5
    assert not any("time" in key or "start" in key for key in body["meetings"][0])


async def test_search_covers_all_history_and_distinguishes_empty_from_no_match(client, settings):
    await _authorize(client, settings)
    empty = (await client.get("/api/meetings", params={"q": "abc"})).json()
    assert empty["total"] == 0 and empty["meetings"] == []

    for day in range(1, 6):
        seed_meeting(settings.data_dir, f"Họp {day}", f"2026-03-0{day}")
    seed_meeting(settings.data_dir, "Kế hoạch ĐẶC BIỆT", "2020-01-01")

    hit = (await client.get("/api/meetings", params={"q": "  đặc biệt "})).json()
    assert [item["title"] for item in hit["meetings"]] == ["Kế hoạch ĐẶC BIỆT"]
    assert len(hit["recent"]) == 3

    miss = (await client.get("/api/meetings", params={"q": "không có"})).json()
    assert miss["meetings"] == [] and miss["total"] == 6


async def test_patch_title_keeps_notes_source_and_date_edit_bumps_it(client, settings):
    headers = await _authorize(client, settings)
    meeting_id = seed_meeting(settings.data_dir, "Old", "2026-10-15", language_hint="vi")
    url = f"/api/meetings/{meeting_id}"

    renamed = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 1, "title": "  New  "}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "New"
    assert renamed.json()["metadata_version"] == 2
    assert renamed.json()["notes_source_version"] == 1
    assert renamed.json()["meeting_date"] == "2026-10-15"

    moved = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 2, "meeting_date": "2026-11-01"}
    )
    assert (moved.json()["metadata_version"], moved.json()["notes_source_version"]) == (3, 2)

    cleared = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 3, "meeting_date": None}
    )
    assert cleared.json()["meeting_date"] is None
    assert cleared.json()["notes_source_version"] == 3

    added = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 4, "meeting_date": "2024-02-29"}
    )
    assert added.json()["meeting_date"] == "2024-02-29"
    assert added.json()["notes_source_version"] == 4
    assert added.json()["language_hint"] == "vi"

    noop = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 5, "meeting_date": "2024-02-29"}
    )
    assert noop.json()["metadata_version"] == 5


async def test_stale_write_is_rejected_with_distinct_code_and_changes_nothing(client, settings):
    headers = await _authorize(client, settings)
    meeting_id = seed_meeting(settings.data_dir, "Original", "2026-10-15")
    url = f"/api/meetings/{meeting_id}"
    first = await client.patch(
        url, headers=headers, json={"expected_metadata_version": 1, "title": "Tab A"}
    )
    assert first.status_code == 200

    stale = await client.patch(
        url,
        headers=headers,
        json={"expected_metadata_version": 1, "title": "Tab B", "meeting_date": "2026-12-01"},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_version"
    current = (await client.get(url)).json()
    assert (current["title"], current["meeting_date"], current["metadata_version"]) == (
        "Tab A",
        "2026-10-15",
        2,
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"expected_metadata_version": 1, "title": "   "}, "invalid_title"),
        ({"expected_metadata_version": 1, "title": "x" * 201}, "invalid_title"),
        ({"expected_metadata_version": 1, "meeting_date": "2026-02-30"}, "invalid_meeting_date"),
        ({"expected_metadata_version": 1, "meeting_date": "2026-1-5"}, "invalid_meeting_date"),
        ({"expected_metadata_version": 1, "meeting_date": "0999-10-15"}, "invalid_meeting_date"),
        ({"expected_metadata_version": 1, "meeting_date": "10000-10-15"}, "invalid_meeting_date"),
        (
            {"expected_metadata_version": 1, "meeting_date": "2026-10-15T00:00"},
            "invalid_meeting_date",
        ),
        ({"expected_metadata_version": "1", "title": "x"}, "invalid_expected_version"),
        ({"expected_metadata_version": 1}, "invalid_request"),
    ],
)
async def test_patch_validation(client, settings, payload, code):
    headers = await _authorize(client, settings)
    meeting_id = seed_meeting(settings.data_dir, "Keep", "2026-10-15")

    response = await client.patch(f"/api/meetings/{meeting_id}", headers=headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code


async def test_patch_rejects_language_and_missing_version_and_unknown_meeting(client, settings):
    headers = await _authorize(client, settings)
    meeting_id = seed_meeting(settings.data_dir, "Keep", language_hint="vi")
    url = f"/api/meetings/{meeting_id}"

    for payload in (
        {"expected_metadata_version": 1, "language_hint": "en"},
        {"title": "no version"},
    ):
        response = await client.patch(url, headers=headers, json=payload)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_request"
    assert (await client.get(url)).json()["language_hint"] == "vi"

    missing = await client.patch(
        "/api/meetings/nope", headers=headers, json={"expected_metadata_version": 1, "title": "x"}
    )
    assert missing.status_code == 404


async def test_edits_persist_in_sqlite_across_a_new_app(settings):
    headers = {"Origin": settings.public_url}

    async def run_app():
        app = create_app(settings)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as http,
        ):
            token = AuthStore(settings.auth_dir).load().token
            await http.post("/api/access/session", headers=headers, json={"token": token})
            yield http

    async for http in run_app():
        meeting_id = seed_meeting(settings.data_dir, "Before", "2026-10-15")
        await http.patch(
            f"/api/meetings/{meeting_id}",
            headers=headers,
            json={"expected_metadata_version": 1, "title": "After", "meeting_date": None},
        )
    async for http in run_app():
        body = (await http.get("/api/meetings")).json()
    assert [(m["title"], m["meeting_date"]) for m in body["meetings"]] == [("After", None)]
    assert body["recent"] == []
    with sqlite3.connect(database_path(settings.data_dir)) as connection:
        assert connection.execute("SELECT notes_source_version FROM meetings").fetchone() == (2,)
    connection.close()
