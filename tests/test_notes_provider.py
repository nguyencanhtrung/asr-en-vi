from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pytest

from asr_en_vi.chatgpt import (
    ACCESS_REFRESH_MARGIN_SECONDS,
    DIRECT_SCOPE,
    NOTES_HTTP_TOTAL_TIMEOUT_SECONDS,
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
    allowed_source_ids: tuple[str, ...]
    max_output_bytes: int | None


class NotesOnlyAdapter:
    def __init__(
        self,
        replies: list[str | ChatGPTError] | None = None,
        *,
        responder=None,
    ) -> None:
        self.replies = list(replies or [])
        self.responder = responder
        self.calls: list[NotesReply] = []
        self.refresh_calls: list[dict[str, str]] = []
        self.refresh_results: list[dict | ChatGPTError] = []

    def refresh(self, *, client_id, refresh_token):
        self.refresh_calls.append({"client_id": client_id, "refresh_token": refresh_token})
        if self.refresh_results:
            result = self.refresh_results.pop(0)
            if isinstance(result, ChatGPTError):
                raise result
            return result
        return {
            "access_token": "refreshed-test-access-token",
            "refresh_token": "refreshed-test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": DIRECT_SCOPE,
        }

    def generate_notes(
        self,
        *,
        access_token,
        model,
        reasoning_effort,
        prompt,
        allowed_source_ids,
        max_output_bytes=None,
    ):
        self.calls.append(
            NotesReply(
                prompt,
                access_token,
                model,
                reasoning_effort,
                tuple(allowed_source_ids),
                max_output_bytes,
            )
        )
        if self.responder is not None:
            return self.responder(prompt, max_output_bytes)
        reply = self.replies.pop(0)
        if isinstance(reply, ChatGPTError):
            raise reply
        return reply


def _provider(tmp_path, adapter, *, clock=time.time):
    provider = ChatGPTProvider(tmp_path / "provider", callback_url="", adapter=adapter, clock=clock)
    provider.ensure()
    client_id = "oaiapp_test-123456"
    with provider.store.locked(write=True) as state:
        state["connection_status"] = "connected"
        state["connection_version"] = 7
        state["active_client_id"] = client_id
        state["registrations"][client_id] = {
            "access_token": "local-test-access-token",
            "refresh_token": "local-test-refresh-token",
            "expires_at": provider._now() + 3600,
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
        "overview": [{"text": "Morgan will prepare a draft.", "source_ids": ["00000"]}],
        "key_topics": [],
        "decisions": [],
        "open_questions": [],
        "action_items": [],
        "confirmation_items": [],
    }


def _chunked_snapshot():
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index:032x}",
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "x" * 16_000,
            "speaker_name": "Morgan",
        }
        for index in (1, 2)
    ]
    return snapshot


def _document_for_prompt(prompt):
    if "SOURCE_JSON:\n" in prompt:
        payload = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
        source_ids = [payload["segments"][0]["id"]]
    else:
        payload = json.loads(prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])
        source_ids = list(
            dict.fromkeys(
                source_id
                for summary in payload["summaries"]
                for source_id in summary["source_order"]
            )
        )
    document = _valid_document()
    document["overview"] = [{"text": "A concise summary.", "source_ids": source_ids[:1]}]
    return json.dumps(document)


class MutableClock:
    def __init__(self, value=1_800_000_000):
        self.value = float(value)

    def __call__(self):
        return self.value


def test_invalid_first_result_gets_one_bounded_repair_on_the_pinned_account(tmp_path):
    from asr_en_vi.notes_document import build_notes_schema

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
    assert all(call.allowed_source_ids == ("00000",) for call in adapter.calls)
    assert "c" * 32 not in adapter.calls[0].prompt
    assert all(len(call.prompt.encode("utf-8")) <= MAX_PROMPT_BYTES for call in adapter.calls)
    assert all(call.access_token == "local-test-access-token" for call in adapter.calls)
    assert all(call.model == "gpt-6.1-sol" for call in adapter.calls)
    assert all(call.reasoning_effort == "high" for call in adapter.calls)
    assert all(call.max_output_bytes == 128_000 for call in adapter.calls)
    for call in adapter.calls:
        schema = build_notes_schema(call.allowed_source_ids)
        schema_bytes = len(
            json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        assert len(call.prompt.encode("utf-8")) + schema_bytes + 1_024 <= 35_000
    assert provider.store._read().get("last_diagnostic") is None


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


def test_compact_near_limit_document_is_accepted_without_schema_repair(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    output_budget = 8_000
    compact_budget = 7_985
    document = _valid_document()
    snapshot = _snapshot()
    snapshot["segments"][0]["id"] = "c0000"
    document["overview"][0]["source_ids"] = ["c0000"]
    document["overview"][0]["text"] = ""
    template = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    document["overview"][0]["text"] = "x" * (compact_budget - len(template.encode("utf-8")))
    compact_output = json.dumps(document, ensure_ascii=False, separators=(",", ":"))

    assert len(compact_output.encode("utf-8")) == compact_budget
    assert len(json.dumps(json.loads(compact_output), ensure_ascii=False).encode("utf-8")) == (
        output_budget + 1
    )
    monkeypatch.setattr(notes_document, "MAX_OUTPUT_BYTES", output_budget)
    adapter = NotesOnlyAdapter([compact_output, compact_output])
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=snapshot,
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert len(result["overview"][0]["text"]) > 7_000
    assert len(adapter.calls) == 1
    assert adapter.calls[0].max_output_bytes == output_budget
    assert "INVALID_OUTPUT:" not in adapter.calls[0].prompt


def test_invalid_citation_terminal_failure_is_safe_and_uses_only_one_repair(tmp_path):
    invalid_document = _valid_document()
    invalid_document["overview"][0]["source_ids"] = ["private-unknown-source-id"]
    invalid_output = json.dumps(invalid_document)
    adapter = NotesOnlyAdapter([invalid_output, invalid_output])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert "source references" in invalid.value.public_message
    assert "private-unknown-source-id" not in invalid.value.public_message
    assert len(adapter.calls) == 2
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "source_ids"
    assert diagnostic["stage"] == "single"
    assert diagnostic["provider_call_index"] == 2
    assert diagnostic["attempt"] == "repair"
    assert diagnostic["output_bytes"] == len(invalid_output.encode("utf-8"))
    assert diagnostic["repair_state"] == "already_consumed"
    assert "private-unknown-source-id" not in json.dumps(diagnostic)


def test_provider_normalizes_only_valid_duplicate_citations_without_repair(tmp_path):
    document = _valid_document()
    document["overview"][0]["source_ids"] = ["00000", "00000"]
    adapter = NotesOnlyAdapter([json.dumps(document), json.dumps(_valid_document())])
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=_snapshot(),
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert len(adapter.calls) == 1
    assert result["overview"][0]["source_ids"] == ["c" * 32]
    assert adapter.calls[0].allowed_source_ids == ("00000",)


def test_final_output_expansion_fails_safely_after_restoring_original_ids(tmp_path):
    from asr_en_vi.notes_document import MAX_OUTPUT_BYTES, project_source_snapshot

    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"segment-{index:04d}-" + "x" * 124,
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "source",
        }
        for index in range(200)
    ]
    projection = project_source_snapshot(snapshot)
    alias_ids = list(projection.alias_to_original)
    document = {
        "schema_version": 1,
        **{
            key: []
            for key in (
                "overview",
                "key_topics",
                "decisions",
                "open_questions",
                "action_items",
                "confirmation_items",
            )
        },
        "overview": [
            {
                "text": "x" * 11_500,
                "source_ids": alias_ids[index * 20 : (index + 1) * 20],
            }
            for index in range(10)
        ],
    }
    output = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    assert len(output.encode("utf-8")) <= MAX_OUTPUT_BYTES
    adapter = NotesOnlyAdapter([output])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as oversized:
        provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert oversized.value.code == "notes_invalid_output"
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["stage"] == "single"
    assert diagnostic["validation_reason"] == "size"
    assert diagnostic["output_bytes"] > MAX_OUTPUT_BYTES
    assert len(adapter.calls) == 1
    assert "segment-" not in json.dumps(diagnostic)


@pytest.mark.parametrize(
    ("failure_kind", "expected_detail"),
    [
        ("unknown", "unknown_source_id"),
        ("missing", "required_source_missing"),
    ],
)
def test_terminal_source_diagnostics_distinguish_failures_without_content(
    tmp_path, failure_kind, expected_detail
):
    document = _valid_document()
    document["overview"][0]["text"] = "private summary content"
    if failure_kind == "unknown":
        document["overview"][0]["source_ids"] = ["private-unknown-source-id"]
    else:
        document["decisions"] = [{"text": "private decision content", "source_ids": []}]
    invalid_output = json.dumps(document)
    adapter = NotesOnlyAdapter([invalid_output, invalid_output])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert invalid.value.public_message == (
        "ChatGPT returned notes with invalid source references. No new notes were saved."
    )
    assert len(adapter.calls) == 2
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "source_ids"
    assert diagnostic["validation_detail"] == expected_detail
    serialized_diagnostic = json.dumps(diagnostic)
    assert "private" not in serialized_diagnostic
    assert "c" * 32 not in serialized_diagnostic


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("owner", {"secret": "private owner value"}),
        ("deadline_text", "private deadline phrase\x01"),
        ("deadline_date", {"secret": "private date value"}),
    ],
)
def test_action_field_diagnostics_keep_only_allowlisted_field_name(
    tmp_path, field_name, invalid_value
):
    document = _valid_document()
    action = {
        "text": "private action content",
        "source_ids": ["00000"],
        "owner": None,
        "deadline_text": None,
        "deadline_date": None,
    }
    action[field_name] = invalid_value
    document["action_items"] = [action]
    invalid_output = json.dumps(document)
    adapter = NotesOnlyAdapter([invalid_output, invalid_output])
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
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "action_fields"
    assert diagnostic["validation_field"] == field_name
    serialized_diagnostic = json.dumps(diagnostic)
    assert "private" not in serialized_diagnostic
    assert "c" * 32 not in serialized_diagnostic


def test_invalid_output_keeps_safe_diagnostic_when_repair_cannot_fit(tmp_path):
    invalid_output = "not-json" + "x" * 8_001
    adapter = NotesOnlyAdapter([invalid_output])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert len(adapter.calls) == 1
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "json"
    assert diagnostic["stage"] == "single"
    assert diagnostic["provider_call_index"] == 1
    assert diagnostic["attempt"] == "primary"
    assert diagnostic["output_bytes"] == len(invalid_output.encode("utf-8"))
    assert diagnostic["repair_state"] == "unavailable"
    assert diagnostic["prompt_bytes"] == len(adapter.calls[0].prompt.encode("utf-8"))
    assert diagnostic["response_limit"] == 128_000
    assert "not-json" not in json.dumps(diagnostic)


def test_deeply_nested_provider_json_is_normalized_as_invalid_output(tmp_path):
    valid = json.dumps(_valid_document(), separators=(",", ":"))
    start = valid.index('"overview":') + len('"overview":')
    end = valid.index(',"key_topics"', start)
    nested_array = "[" * 1_200 + "0" + "]" * 1_200
    invalid_output = valid[:start] + "[" + nested_array + "]" + valid[end:]
    adapter = NotesOnlyAdapter([invalid_output, invalid_output])
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
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "json"
    assert diagnostic["stage"] == "single"
    assert diagnostic["provider_call_index"] == 2
    assert diagnostic["attempt"] == "repair"
    assert diagnostic["output_bytes"] == len(invalid_output.encode("utf-8"))
    assert diagnostic["repair_state"] == "already_consumed"


def test_notes_refreshes_access_token_between_stages_and_keeps_the_task_pin(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    clock = MutableClock()
    adapter = NotesOnlyAdapter(responder=lambda prompt, _limit: _document_for_prompt(prompt))
    provider = _provider(tmp_path, adapter, clock=clock)
    with provider.store.locked(write=True) as state:
        registration = state["registrations"]["oaiapp_test-123456"]
        registration["expires_at"] = clock.value + 1_800

    def advance_each_stage(prompt, _limit):
        clock.value += 700
        return _document_for_prompt(prompt)

    adapter.responder = advance_each_stage
    result = provider.generate_notes_document(
        snapshot=_chunked_snapshot(),
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert result["overview"]
    assert len(adapter.calls) == 3
    assert [call.access_token for call in adapter.calls] == [
        "local-test-access-token",
        "local-test-access-token",
        "refreshed-test-access-token",
    ]
    assert clock.value - 1_800_000_000 == 2_100
    assert adapter.refresh_calls == [
        {"client_id": "oaiapp_test-123456", "refresh_token": "local-test-refresh-token"}
    ]
    assert all(call.model == "gpt-6.1-sol" for call in adapter.calls)
    assert all(call.reasoning_effort == "high" for call in adapter.calls)
    state = provider.store._read()
    assert state["connection_status"] == "connected"
    assert state["connection_version"] == 7
    assert state["active_client_id"] == "oaiapp_test-123456"
    assert state["selected_model"] == "gpt-6.1-sol"
    assert state["selected_reasoning_effort"] == "high"
    registration = state["registrations"]["oaiapp_test-123456"]
    assert registration["subject"] == "test-subject"
    assert registration["label"] == "Test account"
    assert registration["access_token"] == "refreshed-test-access-token"


def test_notes_proactively_refreshes_when_token_cannot_cover_stage_deadline(tmp_path):
    clock = MutableClock()
    adapter = NotesOnlyAdapter([json.dumps(_valid_document())])
    provider = _provider(tmp_path, adapter, clock=clock)
    with provider.store.locked(write=True) as state:
        state["registrations"]["oaiapp_test-123456"]["expires_at"] = (
            clock.value + NOTES_HTTP_TOTAL_TIMEOUT_SECONDS + ACCESS_REFRESH_MARGIN_SECONDS - 1
        )

    provider.generate_notes_document(
        snapshot=_snapshot(),
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert len(adapter.refresh_calls) == 1
    assert adapter.calls[0].access_token == "refreshed-test-access-token"


def test_terminal_refresh_failure_stops_notes_without_replaying_inference(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    clock = MutableClock()
    adapter = NotesOnlyAdapter(responder=lambda prompt, _limit: _document_for_prompt(prompt))
    adapter.refresh_results.append(ChatGPTError(400, "invalid_grant", "private refresh detail"))
    provider = _provider(tmp_path, adapter, clock=clock)
    with provider.store.locked(write=True) as state:
        state["registrations"]["oaiapp_test-123456"]["expires_at"] = clock.value + 1_800

    def advance_each_stage(prompt, _limit):
        clock.value += 700
        return _document_for_prompt(prompt)

    adapter.responder = advance_each_stage
    with pytest.raises(ChatGPTError) as failed:
        provider.generate_notes_document(
            snapshot=_chunked_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert failed.value.code == "reconnect_required"
    assert len(adapter.calls) == 2
    assert len(adapter.refresh_calls) == 1
    assert clock.value - 1_800_000_000 == 1_400
    state = provider.store._read()
    assert state["connection_status"] == "reconnect_required"
    assert "access_token" not in state["registrations"]["oaiapp_test-123456"]
    assert "refresh_token" not in state["registrations"]["oaiapp_test-123456"]


def test_refresh_auth_failure_marks_reconnect_once_before_any_inference(tmp_path):
    clock = MutableClock()
    adapter = NotesOnlyAdapter([json.dumps(_valid_document())])
    adapter.refresh_results.append(
        ChatGPTError(401, "provider_auth_error", "private refresh authorization detail")
    )
    provider = _provider(tmp_path, adapter, clock=clock)
    with provider.store.locked(write=True) as state:
        state["registrations"]["oaiapp_test-123456"]["expires_at"] = (
            clock.value + NOTES_HTTP_TOTAL_TIMEOUT_SECONDS + ACCESS_REFRESH_MARGIN_SECONDS - 1
        )

    with pytest.raises(ChatGPTError) as failed:
        provider.generate_notes_document(
            snapshot=_snapshot(),
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert failed.value.code == "provider_auth_error"
    assert adapter.calls == []
    assert len(adapter.refresh_calls) == 1
    state = provider.store._read()
    assert state["connection_status"] == "reconnect_required"
    assert state["connection_version"] == 8


def test_only_one_schema_repair_is_available_across_all_chunks(tmp_path):
    snapshot = _snapshot()
    snapshot["segments"] = [
        {"id": "c" * 32, "start_seconds": 1, "end_seconds": 2, "text": "x" * 20_000},
        {"id": "d" * 32, "start_seconds": 3, "end_seconds": 4, "text": "y" * 20_000},
    ]
    first_chunk_result = _valid_document()
    first_chunk_result["overview"][0]["source_ids"] = ["00000"]
    adapter = NotesOnlyAdapter(["not-json", json.dumps(first_chunk_result), "still-not-json"])
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert len(adapter.calls) == 3
    assert "INVALID_OUTPUT:" in adapter.calls[1].prompt
    assert "INVALID_OUTPUT:" not in adapter.calls[2].prompt
    assert all(call.max_output_bytes == 8_000 for call in adapter.calls)
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["validation_reason"] == "json"
    assert diagnostic["stage"] == "chunk"
    assert diagnostic["provider_call_index"] == 3
    assert diagnostic["attempt"] == "primary"
    assert diagnostic["output_bytes"] == len(b"still-not-json")
    assert diagnostic["repair_state"] == "already_consumed"


def test_reducer_scope_contains_only_aliases_cited_by_its_inputs(tmp_path):
    snapshot = _snapshot()
    snapshot["segments"] = [
        {"id": "c" * 32, "start_seconds": 1, "end_seconds": 2, "text": "x" * 20_000},
        {"id": "d" * 32, "start_seconds": 3, "end_seconds": 4, "text": "y" * 20_000},
    ]
    first_chunk_result = _valid_document()
    first_chunk_result["overview"][0]["source_ids"] = ["00000"]
    empty_chunk_result = {
        "schema_version": 1,
        **{
            key: []
            for key in (
                "overview",
                "key_topics",
                "decisions",
                "open_questions",
                "action_items",
                "confirmation_items",
            )
        },
    }
    invalid_reducer_result = {
        **empty_chunk_result,
        "overview": [{"text": "Unsupported citation", "source_ids": ["00001"]}],
    }
    adapter = NotesOnlyAdapter(
        [
            json.dumps(first_chunk_result),
            json.dumps(empty_chunk_result),
            json.dumps(invalid_reducer_result),
            json.dumps(invalid_reducer_result),
        ]
    )
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as invalid:
        provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert invalid.value.code == "notes_invalid_output"
    assert len(adapter.calls) == 4
    assert adapter.calls[0].allowed_source_ids == ("00000",)
    assert adapter.calls[1].allowed_source_ids == ("00001",)
    assert adapter.calls[2].allowed_source_ids == ("00000",)
    assert adapter.calls[3].allowed_source_ids == ("00000",)
    assert "SYNTHESIS_INPUT_JSON:" in adapter.calls[2].prompt
    assert "INVALID_OUTPUT:" in adapter.calls[3].prompt


def test_empty_reducer_scope_is_sent_as_empty_after_uncited_chunk_summaries(tmp_path):
    snapshot = _snapshot()
    snapshot["segments"] = [
        {"id": "c" * 32, "start_seconds": 1, "end_seconds": 2, "text": "x" * 20_000},
        {"id": "d" * 32, "start_seconds": 3, "end_seconds": 4, "text": "y" * 20_000},
    ]
    empty_document = {
        "schema_version": 1,
        **{
            key: []
            for key in (
                "overview",
                "key_topics",
                "decisions",
                "open_questions",
                "action_items",
                "confirmation_items",
            )
        },
    }
    adapter = NotesOnlyAdapter([json.dumps(empty_document)] * 3)
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=snapshot,
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    assert len(adapter.calls) == 3
    assert [call.allowed_source_ids for call in adapter.calls] == [
        ("00000",),
        ("00001",),
        (),
    ]
    assert result["overview"] == []


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


def test_long_source_uses_bounded_multi_level_reduction_and_later_decision_wins(
    tmp_path, monkeypatch
):
    from asr_en_vi import notes_document
    from asr_en_vi.notes_document import (
        MAX_CHUNK_OUTPUT_BYTES,
        MAX_NOTES_CHUNKS,
        MAX_REDUCTION_OUTPUT_BYTES,
        project_source_snapshot,
    )

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index + 1:032x}",
            "start_seconds": float(index * 60),
            "end_seconds": float(index * 60 + 30),
            "text": (
                "proposal: postpone launch " + "x" * 16_000
                if index == 0
                else "decision: launch Tuesday " + "x" * 16_000
                if index == 15
                else f"discussion {index} " + "x" * 16_000
            ),
            "speaker_name": "Morgan",
        }
        for index in range(16)
    ]
    reduction_levels: list[int] = []

    def respond(prompt, max_output_bytes):
        if "SOURCE_JSON:\n" in prompt:
            source = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
            segment = source["segments"][0]
            index = (
                int(segment["text"].split(maxsplit=2)[1])
                if segment["text"].startswith("discussion")
                else (0 if segment["text"].startswith("proposal") else 15)
            )
            summary_text = f"map-{index:02d}|" + "x" * 6_800
            result = _valid_document()
            result["overview"] = [{"text": summary_text, "source_ids": [segment["id"]]}]
            if index == 0:
                result["confirmation_items"] = [
                    {
                        "text": "Postponing launch was proposed, not decided.",
                        "source_ids": [segment["id"]],
                    }
                ]
            if index == 15:
                result["decisions"] = [
                    {
                        "text": "The team decided to launch Tuesday.",
                        "source_ids": [segment["id"]],
                    }
                ]
            return json.dumps(result, separators=(",", ":"))

        payload = json.loads(prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])
        records = payload["summaries"]
        source_ids = list(
            dict.fromkeys(source_id for record in records for source_id in record["source_order"])
        )
        if "final meeting-level notes" in prompt:
            result = _valid_document()
            result["overview"] = [
                {"text": "Launch timing was discussed.", "source_ids": [source_ids[0]]}
            ]
            result["decisions"] = [
                {
                    "text": (
                        "The later Tuesday decision supersedes the earlier postponement proposal."
                    ),
                    "source_ids": [source_ids[0], source_ids[-1]],
                }
            ]
            return json.dumps(result, separators=(",", ":"))

        input_levels = [
            int(item["text"].split("|", 1)[0].removeprefix("level-"))
            for record in records
            for item in record["notes"]["overview"]
            if item["text"].startswith("level-")
        ]
        level = max(input_levels, default=0) + 1
        reduction_levels.append(level)
        result = _valid_document()
        result["overview"] = [{"text": f"level-{level}|" + "y" * 6_800, "source_ids": source_ids}]
        result["decisions"] = [item for record in records for item in record["notes"]["decisions"]]
        result["confirmation_items"] = [
            item for record in records for item in record["notes"]["confirmation_items"]
        ]
        return json.dumps(result, separators=(",", ":"))

    adapter = NotesOnlyAdapter(responder=respond)
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=snapshot,
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    map_calls = [call for call in adapter.calls if "SOURCE_JSON:\n" in call.prompt]
    reduction_calls = [call for call in adapter.calls if "SYNTHESIS_INPUT_JSON:\n" in call.prompt]
    assert len(map_calls) == 16
    assert len(reduction_calls) > 2
    assert max(reduction_levels) >= 2
    assert all(call.max_output_bytes == MAX_CHUNK_OUTPUT_BYTES for call in map_calls)
    assert all(call.max_output_bytes == MAX_REDUCTION_OUTPUT_BYTES for call in reduction_calls[:-1])
    assert reduction_calls[-1].max_output_bytes == 128_000
    assert len(adapter.calls) <= 2 * MAX_NOTES_CHUNKS + 1
    for call in reduction_calls:
        records = json.loads(call.prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])["summaries"]
        if "final meeting-level notes" not in call.prompt:
            assert len(records) <= 2
        previous_source_end = -1
        for record in records:
            source_order = list(record["source_order"].values())
            assert source_order == sorted(source_order)
            if source_order:
                assert source_order[0] > previous_source_end
                previous_source_end = source_order[-1]
    first_source_id = snapshot["segments"][0]["id"]
    last_source_id = snapshot["segments"][-1]["id"]
    projection = project_source_snapshot(snapshot)
    original_to_alias = {
        original_id: alias for alias, original_id in projection.alias_to_original.items()
    }
    assert original_to_alias[first_source_id] in map_calls[0].prompt
    assert original_to_alias[last_source_id] not in map_calls[0].prompt
    assert original_to_alias[last_source_id] in map_calls[-1].prompt
    assert original_to_alias[first_source_id] not in map_calls[-1].prompt
    assert first_source_id not in map_calls[0].prompt
    assert len(result["decisions"]) == 1
    assert "later Tuesday decision supersedes" in result["decisions"][0]["text"]
    assert result["confirmation_items"] == []


def test_final_synthesis_uses_primary_budget_without_repair_reserve(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index:032x}",
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "source detail " + "x" * 18_000,
        }
        for index in range(1, 5)
    ]

    def respond(prompt, max_output_bytes):
        if "SOURCE_JSON:\n" in prompt:
            source = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
            source_id = source["segments"][0]["id"]
            result = _valid_document()
            result["overview"] = [
                {"text": "chunk summary " + "x" * 7_300, "source_ids": [source_id]}
            ]
            output = json.dumps(result, separators=(",", ":"))
            assert len(output.encode("utf-8")) <= max_output_bytes
            return output

        payload = json.loads(prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])
        source_ids = list(
            dict.fromkeys(
                source_id
                for summary in payload["summaries"]
                for source_id in summary["source_order"]
            )
        )
        if "final meeting-level notes" not in prompt:
            result = _valid_document()
            result["overview"] = [{"text": "x" * 8_001, "source_ids": source_ids}]
            return json.dumps(result, separators=(",", ":"))

        result = _valid_document()
        result["overview"] = [
            {"text": "All four chunks were synthesized.", "source_ids": source_ids}
        ]
        return json.dumps(result, separators=(",", ":"))

    adapter = NotesOnlyAdapter(responder=respond)
    provider = _provider(tmp_path, adapter)

    result = provider.generate_notes_document(
        snapshot=snapshot,
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    synthesis_calls = [call for call in adapter.calls if "SYNTHESIS_INPUT_JSON:\n" in call.prompt]
    assert len(adapter.calls) == 5
    assert len(synthesis_calls) == 1
    assert "final meeting-level notes" in synthesis_calls[0].prompt
    assert synthesis_calls[0].max_output_bytes == 128_000
    assert result["overview"][0]["text"] == "All four chunks were synthesized."


def test_final_repair_is_skipped_when_actual_prompt_budget_cannot_fit_it(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index:032x}",
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "source detail " + "x" * 18_000,
        }
        for index in range(1, 5)
    ]

    def respond(prompt, _max_output_bytes):
        if "SOURCE_JSON:\n" in prompt:
            source = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
            source_id = source["segments"][0]["id"]
            result = _valid_document()
            result["overview"] = [
                {"text": "chunk summary " + "x" * 7_300, "source_ids": [source_id]}
            ]
            return json.dumps(result, separators=(",", ":"))
        assert "final meeting-level notes" in prompt
        return "not-json" + "x" * (8_000 - len("not-json"))

    adapter = NotesOnlyAdapter(responder=respond)
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as failed:
        provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert failed.value.code == "notes_invalid_output"
    assert len(adapter.calls) == 5
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["stage"] == "final"
    assert diagnostic["attempt"] == "primary"
    assert diagnostic["provider_call_index"] == 5
    assert diagnostic["prompt_bytes"] == len(adapter.calls[-1].prompt.encode("utf-8"))
    assert diagnostic["response_limit"] == 128_000
    assert diagnostic["output_bytes"] == 8_000
    assert diagnostic["repair_state"] == "unavailable"


@pytest.mark.parametrize("intermediate_bytes", [11_500, 16_001])
def test_intermediate_reduction_has_its_own_hard_output_budget(
    tmp_path, monkeypatch, intermediate_bytes
):
    from asr_en_vi import notes_document
    from asr_en_vi.notes_document import MAX_REDUCTION_OUTPUT_BYTES

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index:032x}",
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "source detail " + "x" * 18_000,
        }
        for index in range(1, 7)
    ]
    reduction_outputs: list[str] = []

    def respond(prompt, max_output_bytes):
        if "SOURCE_JSON:\n" in prompt:
            source = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
            source_id = source["segments"][0]["id"]
            result = _valid_document()
            result["overview"] = [
                {"text": "chunk summary " + "x" * 7_300, "source_ids": [source_id]}
            ]
            output = json.dumps(result, separators=(",", ":"))
            assert len(output.encode("utf-8")) <= max_output_bytes
            return output

        payload = json.loads(prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])
        source_ids = list(
            dict.fromkeys(
                source_id
                for summary in payload["summaries"]
                for source_id in summary["source_order"]
            )
        )
        if "final meeting-level notes" in prompt:
            result = _valid_document()
            result["overview"] = [
                {"text": "All six chunks were synthesized.", "source_ids": source_ids}
            ]
            return json.dumps(result, separators=(",", ":"))

        assert max_output_bytes == MAX_REDUCTION_OUTPUT_BYTES
        result = _valid_document()
        marker = f"reduce-{len(reduction_outputs) + 1}|"
        result["overview"] = [{"text": marker, "source_ids": source_ids}]
        compact = json.dumps(result, separators=(",", ":"))
        target_text_bytes = intermediate_bytes - len(compact.encode("utf-8")) + len(marker)
        result["overview"][0]["text"] += "r" * (target_text_bytes - len(marker))
        output = json.dumps(result, separators=(",", ":"))
        assert len(output.encode("utf-8")) == intermediate_bytes
        reduction_outputs.append(output)
        return output

    adapter = NotesOnlyAdapter(responder=respond)
    provider = _provider(tmp_path, adapter)

    if intermediate_bytes > MAX_REDUCTION_OUTPUT_BYTES:
        with pytest.raises(ChatGPTError) as failed:
            provider.generate_notes_document(
                snapshot=snapshot,
                connection_version=7,
                model="gpt-6.1-sol",
                reasoning_effort="high",
            )

        assert failed.value.code == "notes_invalid_output"
        diagnostic = provider.store._read()["last_diagnostic"]
        assert diagnostic["stage"] == "reduce"
        assert diagnostic["attempt"] == "primary"
        assert diagnostic["provider_call_index"] == 7
        assert diagnostic["response_limit"] == MAX_REDUCTION_OUTPUT_BYTES
        assert diagnostic["output_bytes"] == intermediate_bytes
        assert diagnostic["validation_reason"] == "size"
        assert len(adapter.calls) == 7
        return

    result = provider.generate_notes_document(
        snapshot=snapshot,
        connection_version=7,
        model="gpt-6.1-sol",
        reasoning_effort="high",
    )

    reduction_calls = [call for call in adapter.calls if "SYNTHESIS_INPUT_JSON:\n" in call.prompt]
    intermediate_calls = [
        call for call in reduction_calls if "final meeting-level notes" not in call.prompt
    ]
    assert len(intermediate_calls) == 4
    assert all(call.max_output_bytes == MAX_REDUCTION_OUTPUT_BYTES for call in intermediate_calls)
    assert all(len(output.encode("utf-8")) == intermediate_bytes for output in reduction_outputs)
    for call in reduction_calls:
        summaries = json.loads(call.prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])["summaries"]
        assert len(summaries) <= 2
        previous_source_end = -1
        for summary in summaries:
            source_order = list(summary["source_order"].values())
            assert source_order == sorted(source_order)
            if source_order:
                assert source_order[0] > previous_source_end
                previous_source_end = source_order[-1]
    final_payload = json.loads(reduction_calls[-1].prompt.split("SYNTHESIS_INPUT_JSON:\n", 1)[1])
    assert final_payload["summaries"][1]["notes"]["overview"][0]["text"].startswith("reduce-3|")
    assert result["overview"][0]["text"] == "All six chunks were synthesized."


def test_transport_failure_diagnostics_use_actual_stage_and_bounded_metadata(tmp_path, monkeypatch):
    from asr_en_vi import notes_document

    monkeypatch.setattr(notes_document, "MAX_PRIMARY_PROMPT_BYTES", 20_000)
    snapshot = _snapshot()
    snapshot["segments"] = [
        {
            "id": f"{index:032x}",
            "start_seconds": float(index),
            "end_seconds": float(index + 1),
            "text": "source detail " + "x" * 18_000,
        }
        for index in range(1, 7)
    ]

    def respond(prompt, _max_output_bytes):
        if "SOURCE_JSON:\n" in prompt:
            source = json.loads(prompt.split("SOURCE_JSON:\n", 1)[1])
            source_id = source["segments"][0]["id"]
            result = _valid_document()
            result["overview"] = [
                {"text": "chunk summary " + "x" * 7_300, "source_ids": [source_id]}
            ]
            return json.dumps(result, separators=(",", ":"))

        failure = ChatGPTError(
            502, "provider_output_too_large", "ChatGPT returned an oversized notes document."
        )
        failure.diagnostics = {
            "stage": "untrusted-stage",
            "attempt": "repair",
            "provider_call_index": 999,
            "prompt_bytes": -1,
            "response_limit": 1,
            "output_bytes": 16_001,
            "request_id": "req_reduce123",
            "private": "secret provider body",
        }
        raise failure

    adapter = NotesOnlyAdapter(responder=respond)
    provider = _provider(tmp_path, adapter)

    with pytest.raises(ChatGPTError) as failed:
        provider.generate_notes_document(
            snapshot=snapshot,
            connection_version=7,
            model="gpt-6.1-sol",
            reasoning_effort="high",
        )

    assert failed.value.code == "provider_output_too_large"
    diagnostic = provider.store._read()["last_diagnostic"]
    assert diagnostic["stage"] == "reduce"
    assert diagnostic["attempt"] == "primary"
    assert diagnostic["provider_call_index"] == 7
    assert diagnostic["prompt_bytes"] == len(adapter.calls[-1].prompt.encode("utf-8"))
    assert diagnostic["response_limit"] == 16_000
    assert diagnostic["output_bytes"] == 16_001
    assert diagnostic["request_id"] == "req_reduce123"
    assert "private" not in json.dumps(diagnostic)
    assert "untrusted-stage" not in json.dumps(diagnostic)
