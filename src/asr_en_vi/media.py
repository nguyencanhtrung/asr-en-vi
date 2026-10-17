"""Probe uploaded media and convert its selected audio stream to managed M4A."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = (
    "wav",
    "mp3",
    "m4a",
    "mp4",
    "mov",
    "webm",
    "ogg",
    "opus",
    "flac",
)
OUTPUT_CONTENT_TYPE = "audio/mp4"
OUTPUT_CODEC = "aac"
OUTPUT_BITRATE = "160k"
MAX_STDERR_BYTES = 8192
MAX_PROBE_JSON_BYTES = 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 6 * 60 * 60
PROBE_TIMEOUT_SECONDS = 60
LOCAL_PROTOCOLS = "file,pipe,crypto,data"


class MediaProcessingError(RuntimeError):
    """A safe, actionable error raised while validating or converting media."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class MediaProbe:
    duration_seconds: float
    codec_name: str
    stream_index: int


@dataclass(frozen=True, slots=True)
class _CommandResult:
    returncode: int
    stdout: bytes
    stdout_overflow: bool


def _run_bounded(
    argv: list[str],
    *,
    timeout_seconds: int = COMMAND_TIMEOUT_SECONDS,
    should_cancel: Callable[[], bool] | None = None,
) -> _CommandResult:
    """Run a fixed argv without a shell while retaining bounded command output."""
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
    except FileNotFoundError as exc:
        raise MediaProcessingError("media_tool_unavailable") from exc
    except OSError as exc:
        raise MediaProcessingError("media_processing_failed") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    stdout = bytearray()
    stderr = bytearray()
    stdout_overflow = False
    for pipe, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ, name)

    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    cancelled = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and not timed_out:
                timed_out = True
                process.kill()
            if should_cancel is not None and not cancelled and should_cancel():
                cancelled = True
                process.kill()
            events = selector.select(min(max(remaining, 0), 0.25))
            for key, _ in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                target = stdout if key.data == "stdout" else stderr
                limit = MAX_PROBE_JSON_BYTES if key.data == "stdout" else MAX_STDERR_BYTES
                previous_length = len(target)
                if previous_length < limit:
                    target.extend(chunk[: limit - previous_length])
                if key.data == "stdout" and len(chunk) > limit - previous_length:
                    stdout_overflow = True
                # stderr is drained but only its bounded prefix is retained.
        returncode = process.wait()
    finally:
        selector.close()
        for pipe in (process.stdout, process.stderr):
            if not pipe.closed:
                pipe.close()
        if process.poll() is None:
            process.kill()
            process.wait()

    if timed_out:
        raise MediaProcessingError("media_processing_timeout")
    if cancelled:
        raise MediaProcessingError("media_processing_cancelled")
    return _CommandResult(returncode, bytes(stdout), stdout_overflow)


def _supported_codec(codec_name: str) -> bool:
    if codec_name == "mp3" or codec_name in {"aac", "flac", "opus", "vorbis"}:
        return True
    return codec_name.startswith("pcm_")


def _parse_duration(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    if result <= 0 or not result < float("inf"):
        return None
    return result


def probe_media(path: Path, *, max_duration_seconds: int) -> MediaProbe:
    """Inspect one supported audio stream and enforce its codec and duration policy."""
    executable = shutil.which("ffprobe")
    if executable is None:
        raise MediaProcessingError("media_tool_unavailable")
    result = _run_bounded(
        [
            executable,
            "-v",
            "error",
            "-protocol_whitelist",
            LOCAL_PROTOCOLS,
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,duration:stream_disposition=default",
            "-of",
            "json",
            str(path),
        ],
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or result.stdout_overflow:
        raise MediaProcessingError("invalid_media")
    try:
        document = json.loads(result.stdout)
        streams = document.get("streams", [])
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MediaProcessingError("invalid_media") from exc
    if not audio_streams:
        raise MediaProcessingError("missing_audio_stream")

    selected = next(
        (
            stream
            for stream in audio_streams
            if isinstance(stream.get("disposition"), dict)
            and stream["disposition"].get("default") == 1
        ),
        audio_streams[0],
    )
    codec_name = selected.get("codec_name")
    stream_index = selected.get("index")
    if not isinstance(codec_name, str) or not isinstance(stream_index, int):
        raise MediaProcessingError("invalid_media")
    if not _supported_codec(codec_name.lower()):
        raise MediaProcessingError("unsupported_codec")

    format_info = document.get("format")
    duration = _parse_duration(selected.get("duration"))
    if duration is None and isinstance(format_info, dict):
        duration = _parse_duration(format_info.get("duration"))
    if duration is None:
        raise MediaProcessingError("invalid_media")
    if duration > max_duration_seconds:
        raise MediaProcessingError("duration_limit")
    return MediaProbe(duration, codec_name.lower(), stream_index)


def normalize_media(
    source_path: Path,
    output_path: Path,
    *,
    max_duration_seconds: int,
    should_cancel: Callable[[], bool] | None = None,
) -> MediaProbe:
    """Convert the chosen input audio stream to AAC at 160 kbps in faststart M4A."""
    source = probe_media(source_path, max_duration_seconds=max_duration_seconds)
    if should_cancel is not None and should_cancel():
        raise MediaProcessingError("media_processing_cancelled")
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise MediaProcessingError("media_tool_unavailable")
    result = _run_bounded(
        [
            executable,
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-protocol_whitelist",
            LOCAL_PROTOCOLS,
            "-i",
            str(source_path),
            "-map",
            f"0:{source.stream_index}",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata",
            "-1",
            "-t",
            str(max_duration_seconds + 1),
            "-c:a",
            OUTPUT_CODEC,
            "-b:a",
            OUTPUT_BITRATE,
            "-movflags",
            "+faststart",
            "-f",
            "ipod",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )
    if result.returncode != 0:
        raise MediaProcessingError("conversion_failed")
    if should_cancel is not None and should_cancel():
        raise MediaProcessingError("media_processing_cancelled")
    normalized = probe_media(output_path, max_duration_seconds=max_duration_seconds)
    if normalized.codec_name != OUTPUT_CODEC:
        raise MediaProcessingError("conversion_failed")
    return MediaProbe(normalized.duration_seconds, source.codec_name, source.stream_index)
