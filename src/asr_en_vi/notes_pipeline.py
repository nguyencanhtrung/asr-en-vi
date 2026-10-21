"""Provider-neutral notes generation: plan, call, validate, repair, reduce and restore refs."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any, Protocol

# Limits are read through the module at call time so tests can lower them.
from asr_en_vi import notes_document as nd


class NotesTransport(Protocol):
    """Send one prompt through the pinned provider and return its raw text."""

    def __call__(
        self,
        prompt: str,
        *,
        allowed_source_ids: Sequence[str],
        max_output_bytes: int,
        stage: str,
        attempt: str,
        provider_call_index: int,
        prompt_bytes: int,
    ) -> str: ...


def generate_notes_document(
    *,
    snapshot: dict[str, Any],
    output_language: str,
    transport: NotesTransport,
    invalid_output_error: Callable[[dict[str, Any]], Exception],
    limit_error: Callable[[str], Exception],
) -> dict[str, Any]:
    """Run the notes synthesis for one task through a provider transport.

    The transport owns credentials, model pinning and provider errors. This function owns
    the call budget, the single repair allowed per task, validation and source-ref restoring,
    so no provider can skip them. `invalid_output_error` receives bounded diagnostics only.
    """
    output_language = nd.validate_output_language(output_language)
    projection = nd.project_source_snapshot(snapshot)
    projected_snapshot = projection.snapshot
    plan = nd.plan_source(
        snapshot,
        projected_snapshot=projected_snapshot,
        output_language=output_language,
    )
    call_count = 0
    repair_used = False
    last_successful_response: tuple[int, str, str] | None = None

    def request(
        prompt: str,
        *,
        allowed_source_ids: Sequence[str],
        max_output_bytes: int,
        stage: str,
        attempt: str,
    ) -> str:
        nonlocal call_count
        if call_count >= nd.MAX_PROVIDER_CALLS:
            raise limit_error("This transcript exceeds the bounded notes synthesis request limit.")
        call_count += 1
        return transport(
            prompt,
            allowed_source_ids=allowed_source_ids,
            max_output_bytes=max_output_bytes,
            stage=stage,
            attempt=attempt,
            provider_call_index=call_count,
            prompt_bytes=len(prompt.encode("utf-8")),
        )

    def invalid_output(
        validation_error: Exception,
        *,
        stage: str,
        provider_call_index: int,
        attempt: str | None,
        raw_output: object,
        repair_state: str | None,
        reported_output_bytes: int | None = None,
        prompt_bytes: int | None = None,
        response_limit: int | None = None,
    ) -> Exception:
        diagnostics: dict[str, Any] = {
            "stage": stage,
            "provider_call_index": provider_call_index,
        }
        if attempt is not None:
            diagnostics["attempt"] = attempt
        if repair_state is not None:
            diagnostics["repair_state"] = repair_state
        if prompt_bytes is not None:
            diagnostics["prompt_bytes"] = prompt_bytes
        if response_limit is not None:
            diagnostics["response_limit"] = response_limit
        reason = getattr(validation_error, "reason_code", None)
        if isinstance(reason, str) and reason in nd.NOTES_VALIDATION_REASON_CODES:
            diagnostics["validation_reason"] = reason
        detail = getattr(validation_error, "detail_code", None)
        if (
            reason == "source_ids"
            and isinstance(detail, str)
            and detail in nd.NOTES_VALIDATION_DETAIL_CODES
        ):
            diagnostics["validation_detail"] = detail
        field_name = getattr(validation_error, "field_name", None)
        if (
            reason == "action_fields"
            and isinstance(field_name, str)
            and field_name in nd.NOTES_ACTION_FIELD_NAMES
        ):
            diagnostics["validation_field"] = field_name
        if reported_output_bytes is not None:
            diagnostics["output_bytes"] = reported_output_bytes
        elif isinstance(raw_output, str):
            try:
                diagnostics["output_bytes"] = len(raw_output.encode("utf-8"))
            except UnicodeError:
                diagnostics["output_bytes"] = len(
                    raw_output.encode("utf-8", errors="surrogatepass")
                )
        return invalid_output_error(diagnostics)

    def parse_and_validate(
        raw_output: object,
        citation_scope: dict[str, Any],
        *,
        max_output_bytes: int,
    ) -> dict[str, Any]:
        if not isinstance(raw_output, str):
            raise nd.NotesDocumentError("The notes response must be text.", reason_code="json")
        try:
            document = json.loads(raw_output)
        except (json.JSONDecodeError, RecursionError):
            raise nd.NotesDocumentError(
                "The notes response must be valid JSON.", reason_code="json"
            ) from None
        try:
            document = nd.normalize_duplicate_source_refs(
                document,
                tuple(segment["id"] for segment in citation_scope["segments"]),
            )
            return nd.validate_document(
                document,
                citation_scope,
                max_output_bytes=max_output_bytes,
            )
        except RecursionError:
            raise nd.NotesDocumentError(
                "The notes response must be valid JSON.", reason_code="json"
            ) from None

    def request_document(
        prompt: str,
        citation_scope: dict[str, Any],
        *,
        max_output_bytes: int,
        stage: str,
        repair_prompt: Callable[[str], str],
    ) -> dict[str, Any]:
        nonlocal last_successful_response, repair_used
        allowed_source_ids = tuple(segment["id"] for segment in citation_scope["segments"])
        raw_output = request(
            prompt,
            allowed_source_ids=allowed_source_ids,
            max_output_bytes=max_output_bytes,
            stage=stage,
            attempt="primary",
        )
        provider_call_index = call_count
        try:
            validated = parse_and_validate(
                raw_output,
                citation_scope,
                max_output_bytes=max_output_bytes,
            )
            last_successful_response = (provider_call_index, "primary", raw_output)
            return validated
        except (nd.NotesDocumentError, TypeError) as validation_error:
            if repair_used:
                raise invalid_output(
                    validation_error,
                    stage=stage,
                    provider_call_index=provider_call_index,
                    attempt="primary",
                    raw_output=raw_output,
                    repair_state="already_consumed",
                    prompt_bytes=len(prompt.encode("utf-8")),
                    response_limit=max_output_bytes,
                ) from None
            repair_used = True
            try:
                bounded_repair_prompt = repair_prompt(raw_output)
            except (nd.NotesDocumentError, TypeError, AttributeError):
                raise invalid_output(
                    validation_error,
                    stage=stage,
                    provider_call_index=provider_call_index,
                    attempt="primary",
                    raw_output=raw_output,
                    repair_state="unavailable",
                    prompt_bytes=len(prompt.encode("utf-8")),
                    response_limit=max_output_bytes,
                ) from None
            repaired_output = request(
                bounded_repair_prompt,
                allowed_source_ids=allowed_source_ids,
                max_output_bytes=max_output_bytes,
                stage=stage,
                attempt="repair",
            )
            repair_call_index = call_count
            try:
                validated = parse_and_validate(
                    repaired_output,
                    citation_scope,
                    max_output_bytes=max_output_bytes,
                )
                last_successful_response = (repair_call_index, "repair", repaired_output)
                return validated
            except (nd.NotesDocumentError, TypeError) as repair_error:
                raise invalid_output(
                    repair_error,
                    stage=stage,
                    provider_call_index=repair_call_index,
                    attempt="repair",
                    raw_output=repaired_output,
                    repair_state="already_consumed",
                    prompt_bytes=len(bounded_repair_prompt.encode("utf-8")),
                    response_limit=max_output_bytes,
                ) from None

    def restore_final_document(document: dict[str, Any], *, stage: str) -> dict[str, Any]:
        restored = nd.restore_source_refs(document, projection.alias_to_original)
        try:
            return nd.validate_document(restored, snapshot, max_output_bytes=nd.MAX_OUTPUT_BYTES)
        except (nd.NotesDocumentError, TypeError) as validation_error:
            response = last_successful_response
            call_index = response[0] if response is not None else max(call_count, 1)
            try:
                expanded_bytes = len(
                    json.dumps(
                        restored,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                )
            except (TypeError, ValueError, UnicodeError):
                expanded_bytes = None
            raise invalid_output(
                validation_error,
                stage=stage,
                provider_call_index=call_index,
                attempt=None,
                raw_output=None,
                repair_state=None,
                reported_output_bytes=expanded_bytes,
            ) from None

    if not plan.chunked:
        source_ids = tuple(segment["id"] for segment in projected_snapshot["segments"])
        document = request_document(
            nd.build_prompt(
                projected_snapshot,
                allowed_source_ids=source_ids,
                output_language=output_language,
            ),
            projected_snapshot,
            max_output_bytes=nd.MAX_OUTPUT_BYTES,
            stage="single",
            repair_prompt=lambda raw: nd.build_prompt(
                projected_snapshot,
                allowed_source_ids=source_ids,
                invalid_output=raw,
                output_language=output_language,
            ),
        )
        return restore_final_document(document, stage="single")

    summaries: list[dict[str, Any]] = []
    for index, chunk in enumerate(plan.chunks, start=1):
        projected_chunk = projection.project_chunk(chunk)
        source_ids = tuple(segment["id"] for segment in projected_chunk["segments"])
        prompt = nd.build_chunk_prompt(
            projected_chunk,
            chunk_index=index,
            chunk_count=len(plan.chunks),
            allowed_source_ids=source_ids,
            output_language=output_language,
        )

        def repair_chunk(
            raw: str,
            *,
            source_chunk: dict[str, Any] = projected_chunk,
            chunk_index: int = index,
            allowed_ids: tuple[str, ...] = source_ids,
        ) -> str:
            return nd.build_chunk_prompt(
                source_chunk,
                chunk_index=chunk_index,
                chunk_count=len(plan.chunks),
                allowed_source_ids=allowed_ids,
                invalid_output=raw,
                output_language=output_language,
            )

        summaries.append(
            request_document(
                prompt,
                projected_chunk,
                max_output_bytes=nd.MAX_CHUNK_OUTPUT_BYTES,
                stage="chunk",
                repair_prompt=repair_chunk,
            )
        )

    reduction_calls = 0
    documents = summaries
    for _level in range(nd.MAX_REDUCTION_LEVELS):
        final_prompt = None
        final_scope = nd._prompt_citation_scope(projected_snapshot, documents)
        with suppress(nd.NotesDocumentError):
            final_prompt = nd.build_reduction_prompt(
                projected_snapshot,
                documents,
                final=True,
                output_language=output_language,
            )
        if final_prompt is not None:
            if reduction_calls >= nd.MAX_REDUCTION_CALLS:
                raise limit_error("This transcript exceeds the bounded notes reduction limit.")
            reduction_calls += 1
            final_document = request_document(
                final_prompt,
                final_scope,
                max_output_bytes=nd.MAX_OUTPUT_BYTES,
                stage="final",
                repair_prompt=lambda raw, inputs=documents: nd.build_reduction_prompt(
                    projected_snapshot,
                    inputs,
                    final=True,
                    invalid_output=raw,
                    output_language=output_language,
                ),
            )
            return restore_final_document(final_document, stage="final")

        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for document in documents:
            try:
                nd.build_reduction_prompt(
                    projected_snapshot,
                    [document],
                    final=False,
                    output_language=output_language,
                )
            except nd.NotesDocumentError:
                raise limit_error(
                    "A notes summary exceeds the bounded synthesis request limit."
                ) from None
            if not current:
                current = [document]
                continue
            if len(current) >= 2:
                groups.append(current)
                current = [document]
                continue
            candidate = [*current, document]
            try:
                nd.build_reduction_prompt(
                    projected_snapshot,
                    candidate,
                    final=False,
                    output_language=output_language,
                )
            except nd.NotesDocumentError:
                groups.append(current)
                current = [document]
            else:
                current = candidate
        if current:
            groups.append(current)

        next_documents: list[dict[str, Any]] = []
        for group in groups:
            if len(group) == 1:
                next_documents.extend(group)
                continue
            if reduction_calls >= nd.MAX_REDUCTION_CALLS:
                raise limit_error("This transcript exceeds the bounded notes reduction limit.")
            reduction_calls += 1
            group_scope = nd._prompt_citation_scope(projected_snapshot, group)
            intermediate_prompt = nd.build_reduction_prompt(
                projected_snapshot,
                group,
                final=False,
                output_language=output_language,
            )
            next_documents.append(
                request_document(
                    intermediate_prompt,
                    group_scope,
                    max_output_bytes=nd.MAX_REDUCTION_OUTPUT_BYTES,
                    stage="reduce",
                    repair_prompt=lambda raw, inputs=group: nd.build_reduction_prompt(
                        projected_snapshot,
                        inputs,
                        final=False,
                        invalid_output=raw,
                        output_language=output_language,
                    ),
                )
            )
        if len(next_documents) >= len(documents):
            raise limit_error(
                "Notes synthesis could not reduce the summary count within its limit."
            )
        documents = next_documents

    raise limit_error("This transcript exceeds the bounded notes reduction depth.")
