from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pytest

from asr_en_vi.chatgpt import (
    DIRECT_SCOPE,
    ChatGPTError,
    ChatGPTProvider,
)
from asr_en_vi.notes_document import MAX_PROMPT_BYTES


@dataclass
class NotesReply:
    prompt: str
    access_token: str
    model: str
    reasoning_effort: str


class NotesOnlyAdapter:
    def __init__(self, replies: list[str | ChatGPTError]) -> None:
        self.replies = list(replies)
        self.calls: list[NotesReply] = []

    def generate_notes(self, *, access_token, model, reasoning_effort, prompt):
        self.calls.append(NotesReply(prompt, access_token, model, reasoning_effort))
        reply = self.replies.pop(0)
        if isinstance(reply, ChatGPTError):
            raise reply
        return reply


def _provider(tmp_path, adapter):
    provider = ChatGPTProvider(tmp_path / "provider", callback_url="", adapter=adapter)
    provider.ensure()
    client_id = "oaiapp_test-123456"
    with provider.store.locked(write=True) as state:
        state["connection_status"] = "connected"
        state["connection_version"] = 7
        state["active_client_id"] = client_id
        state["registrations"][client_id] = {
            "access_token": "local-test-access-token",
            "refresh_token": "local-test-refresh-token",
            "expires_at": time.time() + 3600,
            "scopes": [DIRECT_SCOPE],
            "subject": "test-subject",
            "label": "Test account",
        }
        state["notes_provider"] = "chatgpt"
        state["selected_model"] = "gpt-6.1-sol"
        state["selected_reasoning_effort"] = "high"
    return provider


def _snapshot():
    return {
        "id": "a" * 32,
        "meeting_id": "b" * 32,
        "meeting_date": "2026-10-19",
        "segments": [
            {
                "id": "c" * 32,
                "start_seconds": 1.0,
                "end_seconds": 2.0,
                "text": "Morgan will prepare the draft.",
                "speaker_name": "Morgan",
            }
        ],
    }


def _valid_document():
    return {
        "schema_version": 1,
        "overview": [{"text": "Morgan will prepare a draft.", "source_ids": ["c" * 32]}],
        "key_topics": [],
        "decisions": [],
        "open_questions": [],
        "action_items": [],
        "confirmation_items": [],
    }


def test_invalid_first_result_gets_one_bounded_repair_on_the_pinned_account(tmp_path):
    adapter = NotesOnlyAdapter(["not-json", json.dumps(_valid_document())])
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=_snapshot(),
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert result["overview"][0]["text"] == "Morgan will prepare a draft."
    assert len(adapter.calls) == 2
    assert adapter.calls[0].prompt != adapter.calls[1].prompt
    assert all(len(call.prompt.encode("utf-8")) <= MAX_PROMPT_BYTES for call in adapter.calls)
    assert all(call.access_token == "local-test-access-token" for call in adapter.calls)
    assert all(call.model == "gpt-6.1-sol" for call in adapter.calls)
    assert all(call.reasoning_effort == "high" for call in adapter.calls)


def test_invalid_repair_fails_without_a_third_provider_call(tmp_path):
    adapter = NotesOnlyAdapter(["not-json", "still-not-json"])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert len(adapter.calls) == 2


def test_provider_failure_is_not_retried_as_a_repair(tmp_path):
    adapter = NotesOnlyAdapter(
        [ChatGPTError(503, "provider_timeout", "ChatGPT did not complete the notes request.")]
    )
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as failed:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert failed.value.code == "provider_timeout"
    assert len(adapter.calls) == 1


def test_changed_account_or_model_never_silently_replaces_the_pinned_selection(tmp_path):
    adapter = NotesOnlyAdapter([json.dumps(_valid_document())])
    provider = _provider(tmp_path, adapter)
    with provider.store.locked(write=True) as state:
        state["selected_model"] = "gpt-6-luna"

    with pytest.raises(ChatGPTError) as changed:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert changed.value.code == "connection_changed"
    assert adapter.calls == []
