from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from seeding import seed_meeting

from asr_en_vi.storage import database_path, initialize


class StubNotesProviderStore:
    def __init__(self) -> None:
        self.lock = threading.RLock()

    @contextmanager
    def operation(self):
        with self.lock:
            yield


class StubNotesProvider:
    def __init__(self) -> None:
        self.store = StubNotesProviderStore()

    def notes_task_pin(self) -> dict[str, object]:
        return {
            "provider": "chatgpt",
            "connection_version": 7,
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }


def seed_completed_transcript(
    data_dir: Path,
    *,
    title: str = "Planning meeting",
    meeting_date: str | None = "2026-10-19",
) -> tuple[str, str, list[str]]:
    initialize(data_dir)
    meeting_id = seed_meeting(data_dir, title, meeting_date, duration_seconds=30.0)
    task_id = uuid.uuid4().hex
    generation_id = uuid.uuid4().hex
    segment_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
    with sqlite3.connect(database_path(data_dir)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO tasks(id, request_id, request_hash, meeting_id, kind, model_path, "
            "model_name, device, compute_type, language_hint, status, stage, result_scope, "
            "audio_duration_seconds, transcript_end_seconds, segment_count) "
            "VALUES (?, ?, ?, ?, 'transcription', '/models/whisper-small', 'whisper-small', "
            "'cpu', 'int8', 'en', 'succeeded', 'complete', 'transcript_only', 30.0, 5.0, 2)",
            (task_id, f"seed-{task_id}", f"hash-{task_id}", meeting_id),
        )
        connection.execute(
            "INSERT INTO transcript_generations(id, meeting_id, task_id, generation_number, "
            "status, language_hint, model_name, language_probability, uncertainty_policy, "
            "segment_count, diarization_model_name, regular_turn_count, exclusive_turn_count, "
            "alignment_policy) VALUES (?, ?, ?, 1, 'complete', 'en', 'whisper-small', 0.9, "
            "'test-policy', 2, 'community-1', 1, 0, 'test-alignment')",
            (generation_id, meeting_id, task_id),
        )
        connection.execute(
            "INSERT INTO generation_speakers(generation_id, speaker_id, display_name, "
            "first_seen_seconds, last_seen_seconds) VALUES (?, 'SPEAKER_00', 'Morgan', 1.0, 5.0)",
            (generation_id,),
        )
        connection.executemany(
            "INSERT INTO transcript_segments(id, generation_id, sequence, start_seconds, "
            "end_seconds, text, original_speaker_id, speaker_id, avg_logprob, no_speech_prob, "
            "compression_ratio, uncertain, review_reasons, overlap, speaker_dominance, "
            "assignment_version) VALUES (?, ?, ?, ?, ?, ?, 'SPEAKER_00', 'SPEAKER_00', "
            "-0.2, 0.05, 1.0, 0, '[]', 0, 1.0, 1)",
            [
                (segment_ids[0], generation_id, 0, 1.0, 2.0, "We need a launch plan."),
                (segment_ids[1], generation_id, 1, 4.0, 5.0, "Morgan will send a draft."),
            ],
        )
        connection.execute(
            "UPDATE meetings SET current_generation_id = ? WHERE id = ?",
            (generation_id, meeting_id),
        )
    return meeting_id, generation_id, segment_ids
