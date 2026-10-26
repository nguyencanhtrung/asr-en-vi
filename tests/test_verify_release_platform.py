from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_release_platform", ROOT / "scripts" / "verify-release-platform.py"
)
assert SPEC and SPEC.loader
verify_release_platform = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_release_platform)


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def test_select_platform_descriptor_requires_exactly_one_native_child():
    descriptor = {
        "digest": _digest("a"),
        "platform": {"os": "linux", "architecture": "amd64"},
    }
    index = {
        "manifests": [
            descriptor,
            {
                "digest": _digest("b"),
                "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
            },
        ]
    }
    assert verify_release_platform.select_platform_descriptor(index, "amd64") == {
        "digest": _digest("a"),
        "platform": {"os": "linux", "architecture": "amd64"},
    }

    duplicate = {"manifests": [descriptor, {**descriptor, "digest": _digest("c")}]}
    with pytest.raises(verify_release_platform.VerificationError, match="exactly one"):
        verify_release_platform.select_platform_descriptor(duplicate, "amd64")


def _write_archive(tmp_path: Path, *, unsafe_name: str | None = None):
    config_digest = _digest("a")
    archive = tmp_path / (
        f"corresponding-source-amd64-{config_digest.removeprefix('sha256:')}.tar.gz"
    )
    artifact = {
        "config_digest": config_digest,
        "local_image_id": config_digest,
        "platform": "amd64",
        "revision": "r" * 40,
        "schema": 12,
        "version": "0.1.0",
    }
    members = {
        "runtime-inventory.json": {"artifact": artifact},
        "platform-coverage.json": {"status": "passed", "platform": "amd64"},
        "source-artifacts/source-manifest.json": {"status": "collected"},
    }
    with tarfile.open(archive, "w:gz") as output:
        for name, value in members.items():
            payload = json.dumps(value).encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            output.addfile(info, io.BytesIO(payload))
        if unsafe_name:
            payload = b"unsafe"
            info = tarfile.TarInfo(unsafe_name)
            info.size = len(payload)
            output.addfile(info, io.BytesIO(payload))
    checksum = archive.with_name(f"{archive.name}.sha256")
    checksum.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
    registry_report = {
        "status": "passed",
        "anonymous": True,
        "platform": "amd64",
        "index_digest": _digest("b"),
        "manifest_digest": _digest("c"),
        "config_digest": config_digest,
    }
    return archive, checksum, registry_report


def test_verify_source_archive_streams_safe_members_without_extracting(tmp_path):
    archive, checksum, registry_report = _write_archive(tmp_path)

    result = verify_release_platform.verify_source_archive(
        registry_report,
        archive,
        checksum,
        "amd64",
        "0.1.0",
        12,
        "r" * 40,
    )

    assert result["status"] == "passed"
    assert result["source_archive"]["extracted"] is False
    assert result["artifact"]["config_digest"] == registry_report["config_digest"]


def test_verify_source_archive_rejects_unsafe_member_paths(tmp_path):
    archive, checksum, registry_report = _write_archive(tmp_path, unsafe_name="../escape")

    with pytest.raises(verify_release_platform.VerificationError, match="unsafe"):
        verify_release_platform.verify_source_archive(
            registry_report,
            archive,
            checksum,
            "amd64",
            "0.1.0",
            12,
            "r" * 40,
        )
    assert not (tmp_path / "escape").exists()
