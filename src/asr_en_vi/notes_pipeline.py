"""Provider-neutral notes generation: plan, call, validate, repair, reduce and restore refs."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import suppress
from typing import Any, Protocol

# Limits are read through the module at call time so tests can lower them.
from asr_en_vi import notes_document as nd

# The code a transport gives a response over its output cap.
_OUTPUT_TOO_LARGE = "provider_output_too_large"


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
    on_coverage: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the notes synthesis for one task through a provider transport.

    The transport owns credentials, model pinning and provider errors. This function owns
    the call budget, the single repair allowed per task, the bounded recovery from a response
    over its output cap, validation and source-ref restoring, so no provider can skip them.
    `invalid_output_error` receives bounded diagnostics only.
    `on_coverage` gets the coverage manifest, with the accepted call of every planned request
    and the call and recovery counts, only after the final document is valid, so it never
    describes a partial run.
    """
    output_language = nd.validate_output_language(output_language)
    projection = nd.project_source_snapshot(snapshot)
    projected_snapshot = projection.snapshot
    plan = nd.plan_source(
        snapshot,
        projected_snapshot=projected_snapshot,
        output_language=output_language,
    )
    nd.verify_coverage(snapshot, plan)  # before any provider call
    coverage = copy.deepcopy(plan.manifest)
    call_count = 0
    repair_used = False
    output_recoveries = 0
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

    def recovery_prompts(
        prompt: str, *, target: int, allowed_source_ids: Sequence[str]
    ) -> Iterator[str]:
        """Yield the lower-target prompts one request may still send, within both budgets."""
        nonlocal output_recoveries
        for _ in range(nd.MAX_OUTPUT_RECOVERY_ATTEMPTS):
            if output_recoveries >= nd.MAX_OUTPUT_RECOVERY_CALLS:
                return
            target = nd.lower_output_target(target)
            try:
                lowered = nd.build_recovery_prompt(
                    prompt,
                    target_bytes=target,
                    allowed_source_ids=allowed_source_ids,
                    output_language=output_language,
                )
            except nd.NotesDocumentError:
                return  # the request budget has no room for the lower-target prompt
            output_recoveries += 1
            yield lowered

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
        recoveries = recovery_prompts(
            prompt,
            # The aim the primary prompt states: the reduction target, else the stage cap.
            target=nd.MAX_REDUCTION_TARGET_BYTES if stage == "reduce" else max_output_bytes,
            allowed_source_ids=allowed_source_ids,
        )
        attempt, sent = "primary", prompt
        while True:
            try:
                raw_output = request(
                    sent,
                    allowed_source_ids=allowed_source_ids,
                    max_output_bytes=max_output_bytes,
                    stage=stage,
                    attempt=attempt,
                )
            except Exception as error:
                # Only a response over its cap earns a smaller ask; any other failure is final.
                if getattr(error, "code", None) != _OUTPUT_TOO_LARGE:
                    raise
                lowered = next(recoveries, None)
                if lowered is None:
                    raise
                attempt, sent = "recovery", lowered
                continue
            provider_call_index = call_count
            try:
                validated = parse_and_validate(
                    raw_output,
                    citation_scope,
                    max_output_bytes=max_output_bytes,
                )
                last_successful_response = (provider_call_index, attempt, raw_output)
                return validated
            except (nd.NotesDocumentError, TypeError) as validation_error:
                # OMP ignores the response cap, so its overflow is a size failure here.
                if getattr(validation_error, "reason_code", None) == "size":
                    lowered = next(recoveries, None)
                    if lowered is not None:
                        attempt, sent = "recovery", lowered
                        continue
                if repair_used:
                    raise invalid_output(
                        validation_error,
                        stage=stage,
                        provider_call_index=provider_call_index,
                        attempt=attempt,
                        raw_output=raw_output,
                        repair_state="already_consumed",
                        prompt_bytes=len(sent.encode("utf-8")),
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
                        attempt=attempt,
                        raw_output=raw_output,
                        repair_state="unavailable",
                        prompt_bytes=len(sent.encode("utf-8")),
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

    def finish(document: dict[str, Any]) -> dict[str, Any]:
        coverage["provider_calls"] = call_count
        coverage["output_recoveries"] = output_recoveries
        if on_coverage is not None:
            on_coverage(coverage)
        return document

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
        coverage["chunks"][0]["provider_call_index"] = call_count
        return finish(restore_final_document(document, stage="single"))

    summaries: list[dict[str, Any]] = []
    previous_document: dict[str, Any] | None = None
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

        document = request_document(
            prompt,
            projected_chunk,
            max_output_bytes=nd.MAX_CHUNK_OUTPUT_BYTES,
            stage="chunk",
            repair_prompt=repair_chunk,
        )
        coverage["chunks"][index - 1]["provider_call_index"] = call_count
        if previous_document is not None:
            # The previous chunk read the overlap in full, so its items win over repeats.
            overlap_ids = [
                segment["id"] for segment in projected_chunk["segments"] if segment.get("overlap")
            ]
            summaries.append(nd.drop_overlap_duplicates(previous_document, document, overlap_ids))
        else:
            summaries.append(document)
        previous_document = document

    reduction_calls = 0

    def reduction_prompt(
        group: list[dict[str, Any]], *, final: bool, invalid_output: str | None = None
    ) -> str:
        return nd.build_reduction_prompt(
            projected_snapshot,
            group,
            final=final,
            invalid_output=invalid_output,
            output_language=output_language,
        )

    def fits(group: list[dict[str, Any]]) -> bool:
        try:
            reduction_prompt(group, final=False)
        except nd.NotesDocumentError:
            return False
        return True

    def reduce_group(group: list[dict[str, Any]]) -> dict[str, Any]:
        nonlocal reduction_calls
        if reduction_calls >= nd.MAX_REDUCTION_CALLS:
            raise limit_error("This transcript exceeds the bounded notes reduction limit.")
        reduction_calls += 1
        return request_document(
            reduction_prompt(group, final=False),
            nd._prompt_citation_scope(projected_snapshot, group),
            max_output_bytes=nd.MAX_REDUCTION_OUTPUT_BYTES,
            stage="reduce",
            repair_prompt=lambda raw, inputs=group: reduction_prompt(
                inputs, final=False, invalid_output=raw
            ),
        )

    def document_bytes(document: dict[str, Any]) -> int:
        return len(json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def compact(document: dict[str, Any]) -> dict[str, Any]:
        reduced = reduce_group([document])
        if document_bytes(reduced) >= document_bytes(document):
            raise limit_error("Notes synthesis could not compact a summary within its limit.")
        return reduced

    documents = summaries
    for _level in range(nd.MAX_REDUCTION_LEVELS):
        final_prompt = None
        final_scope = nd._prompt_citation_scope(projected_snapshot, documents)
        with suppress(nd.NotesDocumentError):
            final_prompt = reduction_prompt(documents, final=True)
        if final_prompt is not None:
            if reduction_calls >= nd.MAX_REDUCTION_CALLS:
                raise limit_error("This transcript exceeds the bounded notes reduction limit.")
            reduction_calls += 1
            final_document = request_document(
                final_prompt,
                final_scope,
                max_output_bytes=nd.MAX_OUTPUT_BYTES,
                stage="final",
                repair_prompt=lambda raw, inputs=documents: reduction_prompt(
                    inputs, final=True, invalid_output=raw
                ),
            )
            return finish(restore_final_document(final_document, stage="final"))

        # Merge neighbours in source order. When two summaries leave no room for each other, the
        # larger one is compacted alone and the other moves on, so none is dropped or cut.
        next_documents: list[dict[str, Any]] = []
        for position in range(0, len(documents), 2):
            group = documents[position : position + 2]
            if not all(fits([item]) for item in group):
                raise limit_error("A notes summary exceeds the bounded synthesis request limit.")
            if len(group) == 2 and fits(group):
                next_documents.append(reduce_group(group))
            elif len(group) == 2:
                larger = max(group, key=document_bytes)
                next_documents.extend(compact(item) if item is larger else item for item in group)
            else:
                next_documents.extend(group)
        documents = next_documents

    raise limit_error("This transcript exceeds the bounded notes reduction depth.")
