from __future__ import annotations

import json
from pathlib import Path

from asr_studio.alignment import align_segments_to_speakers

FIXTURE = Path(__file__).parent / "fixtures" / "en-vi-code-switch.json"


def test_english_vietnamese_code_switch_fixture_keeps_source_intervals_and_reviews_overlap():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = align_segments_to_speakers(
        fixture["segments"], fixture["regular_turns"], fixture["exclusive_turns"]
    )

    segments = result["segments"]
    assert [segment["speaker_id"] for segment in segments] == [
        "SPEAKER_00",
        "SPEAKER_01",
        "SPEAKER_02",
        None,
    ]
    assert [(item["start_seconds"], item["end_seconds"]) for item in segments] == [
        (item["start_seconds"], item["end_seconds"]) for item in fixture["segments"]
    ]
    assert [item["display_name"] for item in result["speakers"]] == [
        "Speaker 1",
        "Speaker 2",
        "Speaker 3",
    ]
    assert "blocker" in segments[1]["text"]
    assert "idempotency key" in segments[2]["text"]
    assert segments[2]["overlap"] is True
    assert segments[2]["review_reasons"] == ["overlap", "multiple_speakers"]
    assert segments[3]["review_reasons"] == ["asr_uncertain", "unidentified_speaker"]
    assert segments[3]["text"] == fixture["segments"][3]["text"]
    assert result["regular_turn_count"] == len(fixture["regular_turns"])
    assert result["exclusive_turn_count"] == len(fixture["exclusive_turns"])


def test_partial_exclusive_coverage_is_reviewed_as_low_speaker_dominance():
    result = align_segments_to_speakers(
        [
            {
                "id": "a" * 32,
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "text": "Keep this interval intact.",
            }
        ],
        [{"start_seconds": 0.0, "end_seconds": 1.0, "speaker_id": "SPEAKER_00"}],
        [{"start_seconds": 0.0, "end_seconds": 1.0, "speaker_id": "SPEAKER_00"}],
    )

    segment = result["segments"][0]
    assert segment["original_speaker_id"] == "SPEAKER_00"
    assert segment["speaker_dominance"] == 0.1
    assert segment["review_reasons"] == ["low_speaker_dominance"]
    assert (segment["start_seconds"], segment["end_seconds"], segment["text"]) == (
        0.0,
        10.0,
        "Keep this interval intact.",
    )
