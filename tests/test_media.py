from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

import pytest
from media_tools import require_media_tools

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


def test_probe_keeps_video_container_duration_provisional_when_audio_duration_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: _probe_result(
            [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "disposition": {"default": 1},
                },
                {
                    "index": 1,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "duration": "120.0",
                    "disposition": {"default": 0},
                },
            ],
            duration="120.0",
        ),
    )

    result = media.probe_media(tmp_path / "late-start-video.mp4", max_duration_seconds=4)

    assert result.duration_seconds == 120.0
    assert result.declared_duration_seconds is None
    assert result.duration_is_authoritative is False


def test_real_webm_with_longer_video_than_audio_validates_selected_audio(tmp_path):
    require_media_tools()
    source = tmp_path / "video-longer-than-audio.webm"
    output = tmp_path / "normalized.m4a"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:r=10:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libvpx",
            "-c:a",
            "libvorbis",
            "-t",
            "3",
            str(source),
        ],
        check=True,
        timeout=30,
    )

    result = media.normalize_media(source, output, max_duration_seconds=2)

    assert result.duration_seconds < 2


def test_truncated_m4a_is_rejected_after_decode_but_complete_file_is_accepted(tmp_path):
    require_media_tools()
    source = tmp_path / "complete.m4a"
    truncated = tmp_path / "truncated.m4a"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "180",
            "-c:a",
            "aac",
            "-b:a",
            "8k",
            "-movflags",
            "+faststart",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    content = source.read_bytes()
    truncated.write_bytes(content[: int(len(content) * 0.6)])
    complete = media.normalize_media(
        source,
        tmp_path / "complete-normalized.m4a",
        max_duration_seconds=240,
    )
    assert 179 <= complete.duration_seconds <= 181

    with pytest.raises(media.MediaProcessingError) as error:
        media.normalize_media(
            truncated,
            tmp_path / "truncated-normalized.m4a",
            max_duration_seconds=240,
        )

    assert error.value.code == "duration_mismatch"


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


def test_normalize_rejects_declared_audio_duration_that_truncates_on_decode(monkeypatch, tmp_path):
    probes = iter(
        [
            media.MediaProbe(180.0, "aac", 0, declared_duration_seconds=180.0),
            media.MediaProbe(32.0, "aac", 0),
        ]
    )
    monkeypatch.setattr(media, "probe_media", lambda *args, **kwargs: next(probes))
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: media._CommandResult(0, b"", False),
    )

    with pytest.raises(media.MediaProcessingError) as error:
        media.normalize_media(
            tmp_path / "truncated.m4a",
            tmp_path / "output.m4a",
            max_duration_seconds=240,
        )

    assert error.value.code == "duration_mismatch"


def test_normalize_allows_small_codec_padding_difference(monkeypatch, tmp_path):
    probes = iter(
        [
            media.MediaProbe(10.0, "opus", 0, declared_duration_seconds=10.0),
            media.MediaProbe(9.2, "aac", 0),
        ]
    )
    monkeypatch.setattr(media, "probe_media", lambda *args, **kwargs: next(probes))
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        media,
        "_run_bounded",
        lambda argv, **kwargs: media._CommandResult(0, b"", False),
    )

    result = media.normalize_media(
        tmp_path / "source.opus",
        tmp_path / "output.m4a",
        max_duration_seconds=240,
    )

    assert result.duration_seconds == 9.2


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
