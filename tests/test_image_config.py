from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resolve_image_config", ROOT / "scripts" / "resolve-image-config.py"
)
assert SPEC and SPEC.loader
resolve_image_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolve_image_config)


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.payload


def _registry_fixture(*, config: dict[str, object] | None = None):
    config_value = config or {"architecture": "amd64", "os": "linux"}
    config_bytes = _json_bytes(config_value)
    config_digest = _digest(config_bytes)
    manifest_value = {
        "config": {
            "digest": config_digest,
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "size": len(config_bytes),
        },
        "layers": [],
        "schemaVersion": 2,
    }
    manifest_bytes = _json_bytes(manifest_value)
    manifest_digest = _digest(manifest_bytes)
    child_descriptor = {
        "digest": manifest_digest,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "platform": {"architecture": "amd64", "os": "linux"},
        "size": len(manifest_bytes),
    }
    index_value = {
        "manifests": [
            child_descriptor,
            {
                "digest": _digest(b"attestation"),
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "platform": {"architecture": "unknown", "os": "unknown"},
                "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
                "size": 11,
            },
            {
                "digest": _digest(b"attestation-without-platform"),
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
                "size": 29,
            },
        ]
    }
    index_bytes = _json_bytes(index_value)
    index_digest = _digest(index_bytes)

    def urlopen(request, timeout):
        del timeout
        url = urlparse(request.full_url)
        if url.path == "/token":
            return _Response(b'{"token":"anonymous-token"}')
        if url.path.endswith(f"/manifests/{index_digest}"):
            return _Response(index_bytes)
        if url.path.endswith(f"/manifests/{manifest_digest}"):
            return _Response(manifest_bytes)
        if url.path.endswith(f"/blobs/{config_digest}"):
            return _Response(config_bytes)
        raise AssertionError(f"unexpected registry URL: {request.full_url}")

    return index_digest, manifest_digest, config_digest, urlopen


def test_resolves_exact_linux_child_and_ignores_attestation_descriptors(monkeypatch):
    index_digest, manifest_digest, config_digest, urlopen = _registry_fixture()
    monkeypatch.setattr(resolve_image_config.urllib.request, "urlopen", urlopen)

    result = resolve_image_config.resolve_image_config("example/repository", index_digest, "amd64")

    assert result == {
        "status": "passed",
        "anonymous": True,
        "repository": "example/repository",
        "platform": "amd64",
        "index_digest": index_digest,
        "manifest_digest": manifest_digest,
        "config_digest": config_digest,
        "config_os": "linux",
        "config_architecture": "amd64",
    }


def test_select_platform_descriptor_rejects_missing_or_duplicate_native_child():
    descriptor = {
        "digest": "sha256:" + "a" * 64,
        "platform": {"architecture": "amd64", "os": "linux"},
    }
    with pytest.raises(resolve_image_config.ResolutionError, match="exactly one"):
        resolve_image_config.select_platform_descriptor({"manifests": []}, "amd64")
    with pytest.raises(resolve_image_config.ResolutionError, match="exactly one"):
        resolve_image_config.select_platform_descriptor(
            {"manifests": [descriptor, {**descriptor, "digest": "sha256:" + "b" * 64}]},
            "amd64",
        )


def test_rejects_unknown_requested_platform():
    with pytest.raises(resolve_image_config.ResolutionError, match="unsupported platform"):
        resolve_image_config.select_platform_descriptor({"manifests": []}, "riscv64")


def test_rejects_wrong_platform_config(monkeypatch):
    index_digest, _manifest_digest, _config_digest, urlopen = _registry_fixture(
        config={"architecture": "arm64", "os": "linux"}
    )
    monkeypatch.setattr(resolve_image_config.urllib.request, "urlopen", urlopen)

    with pytest.raises(resolve_image_config.ResolutionError, match="platform config mismatch"):
        resolve_image_config.resolve_image_config("example/repository", index_digest, "amd64")


def test_rejects_response_whose_bytes_do_not_match_requested_digest(monkeypatch):
    index_digest, _manifest_digest, _config_digest, urlopen = _registry_fixture()

    def tampered_urlopen(request, timeout):
        if urlparse(request.full_url).path.endswith(f"/manifests/{index_digest}"):
            return _Response(b"{}")
        return urlopen(request, timeout)

    monkeypatch.setattr(resolve_image_config.urllib.request, "urlopen", tampered_urlopen)
    with pytest.raises(resolve_image_config.ResolutionError, match="digest mismatch"):
        resolve_image_config.resolve_image_config("example/repository", index_digest, "amd64")
