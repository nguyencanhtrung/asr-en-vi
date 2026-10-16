"""Runtime configuration with strict localhost URL validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_PUBLIC_URL = "http://127.0.0.1:8765"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
DEFAULT_MAX_UPLOAD_BYTES = 4 * 1024**3
DEFAULT_MAX_RECORDING_SECONDS = 4 * 60 * 60


def _bool_from_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _positive_int_from_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _validate_public_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.hostname.lower() not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("ASR_PUBLIC_URL must be an http(s) localhost origin without a path")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("ASR_PUBLIC_URL has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("ASR_PUBLIC_URL has an invalid port")
    return f"{parsed.scheme}://{parsed.netloc}"


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    auth_dir: Path
    public_url: str = DEFAULT_PUBLIC_URL
    cookie_secure: bool = False
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_recording_seconds: int = DEFAULT_MAX_RECORDING_SECONDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "auth_dir", Path(self.auth_dir))
        object.__setattr__(self, "public_url", _validate_public_url(self.public_url))
        if isinstance(self.max_upload_bytes, bool) or self.max_upload_bytes < 1:
            raise ValueError("max_upload_bytes must be a positive integer")
        if isinstance(self.max_recording_seconds, bool) or self.max_recording_seconds < 1:
            raise ValueError("max_recording_seconds must be a positive integer")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            data_dir=Path(os.environ.get("ASR_DATA_DIR", "/var/lib/asr-en-vi/data")),
            auth_dir=Path(os.environ.get("ASR_AUTH_DIR", "/var/lib/asr-en-vi/auth")),
            public_url=os.environ.get("ASR_PUBLIC_URL", DEFAULT_PUBLIC_URL),
            cookie_secure=_bool_from_env("ASR_COOKIE_SECURE", False),
            max_upload_bytes=_positive_int_from_env(
                "ASR_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES
            ),
            max_recording_seconds=_positive_int_from_env(
                "ASR_MAX_RECORDING_SECONDS", DEFAULT_MAX_RECORDING_SECONDS
            ),
        )

    @property
    def origin(self) -> tuple[str, str, int]:
        parsed = urlsplit(self.public_url)
        default_port = 443 if parsed.scheme == "https" else 80
        return parsed.scheme, (parsed.hostname or "").lower(), parsed.port or default_port

    @property
    def host_header(self) -> str:
        parsed = urlsplit(self.public_url)
        return parsed.netloc

    @property
    def access_url_prefix(self) -> str:
        return f"{self.public_url}/access#"
