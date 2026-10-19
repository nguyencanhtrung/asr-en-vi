from __future__ import annotations

import copy
import json

import pytest

from asr_en_vi.notes_document import (
    SECTIONS,
    NotesDocumentError,
    build_prompt,
    provider_source,
    render_markdown,
    validate_document,
)


@pytest.fixture
def snapshot():
    return {
        "id": "a" * 32,
        "meeting_id": "b" * 32,
        "meeting_date": "2026-10-19",
        "storage_key": "private/audio.m4a",
        "title": "Private title",
        "segments": [
            {
                "id": "c" * 32,
                "start_seconds": 3661.9,
                "end_seconds": 3670,
                "text": "I'll send it tomorrow",
                "speaker_id": "SPEAKER_00",
                "original_speaker_id": "SPEAKER_01",
                "avg_logprob": -0.2,
            }
        ],
        "speakers": [{"speaker_id": "SPEAKER_00", "display_name": "Mai"}],
    }


@pytest.fixture
def document():
    return {
        "schema_version": 1,
        **{key: [] for key, _ in SECTIONS},
        "decisions": [{"text": "Ship the update.", "source_ids": ["c" * 32]}],
        "action_items": [
            {
                "text": "Send the report",
                "source_ids": ["c" * 32],
                "owner": None,
                "deadline_text": "tomorrow",
                "deadline_date": "2099-01-01",
            }
        ],
    }


def test_only_renderer_builds_source_links_and_deadlines(document, snapshot):
    result = validate_document(document, snapshot)
    assert result["action_items"][0]["deadline_date"] == "2026-10-20"
    assert document["action_items"][0]["deadline_date"] == "2099-01-01"
    markdown = render_markdown(document, snapshot)
    assert "Owner: Undetermined; Deadline: tomorrow (2026-10-20)." in markdown
    assert (
        f"[01:01:01](/meetings/{'b' * 32}?notes_source={'a' * 32}&segment={'c' * 32})" in markdown
    )
    for _, heading in SECTIONS:
        assert f"## {heading}" in markdown


@pytest.mark.parametrize("section", [key for key, _ in SECTIONS])
def test_invalid_source_in_every_section_is_rejected(document, snapshot, section):
    document[section] = [{"text": "Unsupported", "source_ids": ["unknown"]}]
    if section == "action_items":
        document[section][0].update(owner=None, deadline_text=None, deadline_date=None)
    with pytest.raises(NotesDocumentError, match="source IDs"):
        validate_document(document, snapshot)


@pytest.mark.parametrize("section", ["decisions", "action_items"])
def test_decisions_and_actions_need_sources(document, snapshot, section):
    document[section][0]["source_ids"] = []
    with pytest.raises(NotesDocumentError, match="source IDs"):
        validate_document(document, snapshot)


@pytest.mark.parametrize(
    "raw,meeting_date,expected",
    [
        ("tomorrow", None, None),
        ("next week", "2026-10-19", None),
        (None, "2026-10-19", None),
        ("ngày mai", "2026-10-19", "2026-10-20"),
        ("2026-11-01", None, "2026-11-01"),
        ("2026-02-30", None, None),
    ],
)
def test_deadlines_do_not_invent_dates(document, snapshot, raw, meeting_date, expected):
    snapshot["meeting_date"] = meeting_date
    document["action_items"][0]["deadline_text"] = raw
    result = validate_document(document, snapshot)
    assert result["action_items"][0]["deadline_date"] == expected


def test_provider_receives_only_needed_source_fields(snapshot):
    source = provider_source(snapshot)
    assert set(source) == {"meeting_date", "segments"}
    assert source["segments"][0] == {
        "id": "c" * 32,
        "start_seconds": 3661.9,
        "end_seconds": 3670,
        "text": "I'll send it tomorrow",
        "speaker_name": "Mai",
    }
    assert "private/audio" not in build_prompt(snapshot)
    assert "Private title" not in json.dumps(source)


def test_provider_markup_is_content(document, snapshot):
    document["overview"] = [
        {
            "text": "<script>alert(1)</script> [click](https://example.test)\n## Decisions",
            "source_ids": [],
        }
    ]
    markdown = render_markdown(document, snapshot)
    assert "<script>" not in markdown
    assert "[click](https" not in markdown
    assert markdown.count("\n## Decisions\n") == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version=True),
        lambda d: d.update(extra="field"),
        lambda d: d.pop("overview"),
        lambda d: d["decisions"][0].update(source_ids="c" * 32),
        lambda d: d["decisions"][0].update(text=""),
        lambda d: d["action_items"][0].update(owner=42),
    ],
)
def test_malformed_documents_fail_before_render(document, snapshot, mutation):
    mutation(document)
    with pytest.raises(NotesDocumentError):
        render_markdown(document, snapshot)


def test_prompt_budget_covers_repair_and_rejects_full_oversize_source(snapshot):
    original = copy.deepcopy(snapshot)
    with pytest.raises(NotesDocumentError, match="budget"):
        build_prompt(snapshot, invalid_output="x" * 48_000)
    snapshot["segments"][0]["text"] = "x" * 48_000
    with pytest.raises(NotesDocumentError, match="budget"):
        build_prompt(snapshot)
    assert original["segments"][0]["text"] == "I'll send it tomorrow"
