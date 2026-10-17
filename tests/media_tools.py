"""Media-tool gate: skip locally, fail when CI promises the tools exist."""

from __future__ import annotations

import os
import shutil

import pytest


def require_media_tools() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    message = "ffmpeg and ffprobe are required for backend media tests"
    if os.environ.get("ASR_REQUIRE_MEDIA_TOOLS") == "1":
        pytest.fail(message)
    pytest.skip(message)
