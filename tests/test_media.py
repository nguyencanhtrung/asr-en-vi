from __future__ import annotations

import json
import sys
import time

import pytest

from asr_en_vi import media


def _probe_result(streams: list[dict], duration: str = "2.0") -> media._CommandResult:
    document = {"streams": streams, "format": {"duration": duration}}
    return media._CommandResult(0, json.dumps(document).encode(), False)


def test_probe_chooses_default_audio_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: _probe_result(
            [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "pcm_s16le",
                    "duration": "1.0",
                    "disposition": {"default": 0},
                },
                {
                    "index": 2,
                    "codec_type": "audio",
                    "codec_name": "opus",
                    "duration": "2.0",
                    "disposition": {"default": 1},
                },
            ]
        ),
    )

    result = media.probe_media(tmp_path / "input", max_duration_seconds=4)

    assert result.stream_index == 2
    assert result.codec_name == "opus"
    assert result.duration_seconds == 2.0


def test_probe_rejects_audio_codecs_outside_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: _probe_result(
            [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "ac3",
                    "duration": "2.0",
                    "disposition": {"default": 1},
                }
            ]
        ),
    )

    with pytest.raises(media.MediaProcessingError) as error:
        media.probe_media(tmp_path / "input", max_duration_seconds=4)

    assert error.value.code == "unsupported_codec"


def test_probe_requires_audio_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: _probe_result(
            [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "duration": "2.0",
                    "disposition": {"default": 1},
                }
            ]
        ),
    )

    with pytest.raises(media.MediaProcessingError) as error:
        media.probe_media(tmp_path / "input", max_duration_seconds=4)

    assert error.value.code == "missing_audio_stream"


def test_probe_restricts_protocols_and_uses_short_timeout(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return _probe_result(
            [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "pcm_s16le",
                    "duration": "1.0",
                    "disposition": {"default": 1},
                }
            ]
        )

    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(media, "_run_bounded", run)

    media.probe_media(tmp_path / "input.wav", max_duration_seconds=10)

    argv = captured["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("-protocol_whitelist") + 1] == media.LOCAL_PROTOCOLS
    assert captured["kwargs"] == {"timeout_seconds": media.PROBE_TIMEOUT_SECONDS}


def test_normalize_bounds_conversion_duration_and_protocols(monkeypatch, tmp_path):
    probes = iter(
        [
            media.MediaProbe(10.0, "pcm_s16le", 2),
            media.MediaProbe(10.0, "aac", 0),
        ]
    )
    captured: list[str] = []
    monkeypatch.setattr(media, "probe_media", lambda *args, **kwargs: next(probes))
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")

    def run(argv, **kwargs):
        captured.extend(argv)
        return media._CommandResult(0, b"", False)

    monkeypatch.setattr(media, "_run_bounded", run)

    result = media.normalize_media(
        tmp_path / "input.wav",
        tmp_path / "output.m4a",
        max_duration_seconds=10,
    )

    assert result.codec_name == "pcm_s16le"
    assert captured[captured.index("-protocol_whitelist") + 1] == media.LOCAL_PROTOCOLS
    assert captured[captured.index("-t") + 1] == "11"


def test_bounded_command_kills_process_when_cancelled():
    started = time.monotonic()

    with pytest.raises(media.MediaProcessingError) as error:
        media._run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout_seconds=5,
            should_cancel=lambda: True,
        )

    assert error.value.code == "media_processing_cancelled"
    assert time.monotonic() - started < 2
