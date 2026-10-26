#!/usr/bin/env python3
"""Verify one published platform image and its public corresponding source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_JSON_MEMBER_BYTES = 64 * 1024 * 1024
REGISTRY = "ghcr.io"


class VerificationError(RuntimeError):
    """A public release artifact could not be proved."""


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise VerificationError(f"invalid SHA-256 digest for {label}: {value!r}")
    return value


def sha256_path(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"JSON root is not an object: {path}")
    return value


def anonymous_registry_token(repository: str) -> str:
    query = urllib.parse.urlencode({"service": REGISTRY, "scope": f"repository:{repository}:pull"})
    request = urllib.request.Request(
        f"https://{REGISTRY}/token?{query}",
        headers={"Accept": "application/json", "User-Agent": "asr-en-vi-release-verifier/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise VerificationError(f"anonymous registry token request failed: {exc}") from exc
    token = payload.get("token") or payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise VerificationError("anonymous registry token response has no token")
    return token


def registry_json(
    repository: str,
    kind: str,
    digest: str,
    token: str,
    accept: str,
) -> dict[str, Any]:
    require_digest(digest, f"registry {kind}")
    request = urllib.request.Request(
        f"https://{REGISTRY}/v2/{repository}/{kind}/{digest}",
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "User-Agent": "asr-en-vi-release-verifier/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise VerificationError(f"registry {kind} request failed for {digest}: {exc}") from exc
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual != digest:
        raise VerificationError(
            f"registry {kind} digest mismatch: requested {digest}, received {actual}"
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"registry {kind} response is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"registry {kind} response is not an object")
    return value


def select_platform_descriptor(index: dict[str, Any], platform: str) -> dict[str, Any]:
    descriptors = index.get("manifests")
    if not isinstance(descriptors, list):
        raise VerificationError("registry response is not an image index")
    matches = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise VerificationError("image index contains a malformed descriptor")
        descriptor_platform = descriptor.get("platform")
        if not isinstance(descriptor_platform, dict):
            continue
        if (
            descriptor_platform.get("os") == "linux"
            and descriptor_platform.get("architecture") == platform
        ):
            matches.append(descriptor)
    if len(matches) != 1:
        raise VerificationError(
            f"expected exactly one linux/{platform} child manifest, found {len(matches)}"
        )
    digest = require_digest(matches[0].get("digest"), f"linux/{platform} child manifest")
    return {"digest": digest, "platform": matches[0]["platform"]}


def image_labels(config: dict[str, Any]) -> dict[str, str]:
    raw_config = config.get("config")
    if not isinstance(raw_config, dict):
        raise VerificationError("image config has no config object")
    labels = raw_config.get("Labels", {})
    if labels is None:
        labels = {}
    if not isinstance(labels, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in labels.items()
    ):
        raise VerificationError("image config labels are malformed")
    return labels


def inspect_published_image(
    repository: str,
    index_digest: str,
    platform: str,
    expected_revision: str,
    expected_image_version: str,
) -> dict[str, Any]:
    if platform not in {"amd64", "arm64"}:
        raise VerificationError(f"unsupported platform: {platform}")
    token = anonymous_registry_token(repository)
    index = registry_json(
        repository,
        "manifests",
        index_digest,
        token,
        ", ".join(
            (
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.manifest.v1+json",
            )
        ),
    )
    child = select_platform_descriptor(index, platform)
    manifest_digest = child["digest"]
    manifest = registry_json(
        repository,
        "manifests",
        manifest_digest,
        token,
        ", ".join(
            (
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
            )
        ),
    )
    config_descriptor = manifest.get("config")
    if not isinstance(config_descriptor, dict):
        raise VerificationError("platform manifest has no config descriptor")
    config_digest = require_digest(config_descriptor.get("digest"), "platform config")
    config = registry_json(
        repository,
        "blobs",
        config_digest,
        token,
        "application/vnd.oci.image.config.v1+json, application/vnd.docker.container.image.v1+json",
    )
    if config.get("architecture") != platform or config.get("os") != "linux":
        raise VerificationError(
            "platform config mismatch: "
            f"expected linux/{platform}, got {config.get('os')}/{config.get('architecture')}"
        )
    labels = image_labels(config)
    revision = labels.get("org.opencontainers.image.revision")
    if revision != expected_revision:
        raise VerificationError(
            f"image revision mismatch: expected {expected_revision}, got {revision!r}"
        )
    version = labels.get("org.opencontainers.image.version")
    if version != expected_image_version:
        raise VerificationError(
            f"image version label mismatch: expected {expected_image_version}, got {version!r}"
        )
    return {
        "status": "passed",
        "anonymous": True,
        "repository": repository,
        "platform": platform,
        "index_digest": index_digest,
        "index_manifests": index["manifests"],
        "manifest_digest": manifest_digest,
        "config_digest": config_digest,
        "config_architecture": config["architecture"],
        "config_os": config["os"],
        "revision": revision,
        "version_label": version,
    }


def safe_member_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise VerificationError(f"unsafe source archive member path: {name!r}")
    return path.as_posix()


def read_archive_jsons(archive: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], int]:
    wanted = {
        "runtime-inventory.json",
        "platform-coverage.json",
        "source-artifacts/source-manifest.json",
    }
    found: dict[str, dict[str, Any]] = {}
    member_count = 0
    try:
        with tarfile.open(archive, mode="r|gz") as stream:
            for member in stream:
                member_count += 1
                name = safe_member_name(member.name)
                if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                    raise VerificationError(f"unsupported source archive member type: {name}")
                if name not in wanted:
                    continue
                if name in found:
                    raise VerificationError(f"duplicate source archive member: {name}")
                extracted = stream.extractfile(member)
                if extracted is None:
                    raise VerificationError(f"cannot read source archive member: {name}")
                payload = extracted.read(MAX_JSON_MEMBER_BYTES + 1)
                if len(payload) > MAX_JSON_MEMBER_BYTES:
                    raise VerificationError(f"source archive JSON member is too large: {name}")
                try:
                    value = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise VerificationError(
                        f"source archive member is not JSON: {name}: {exc}"
                    ) from exc
                if not isinstance(value, dict):
                    raise VerificationError(f"source archive JSON member is not an object: {name}")
                found[name] = value
    except (OSError, tarfile.TarError) as exc:
        raise VerificationError(f"cannot open source archive {archive}: {exc}") from exc
    missing = wanted - found.keys()
    if missing:
        raise VerificationError(f"source archive is missing members: {sorted(missing)}")
    return (
        found["runtime-inventory.json"],
        found["platform-coverage.json"],
        found["source-artifacts/source-manifest.json"],
        member_count,
    )


def verify_checksum(archive: Path, checksum: Path) -> str:
    try:
        lines = [
            line.strip()
            for line in checksum.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        raise VerificationError(f"cannot read checksum file {checksum}: {exc}") from exc
    if len(lines) != 1:
        raise VerificationError(f"checksum file must contain exactly one record: {checksum}")
    parts = lines[0].split(maxsplit=1)
    if len(parts) != 2 or HEX_SHA256_RE.fullmatch(parts[0]) is None:
        raise VerificationError(f"malformed checksum record: {lines[0]!r}")
    expected, filename = parts
    if filename.startswith("*"):
        filename = filename[1:]
    if filename != archive.name:
        raise VerificationError(
            f"checksum names {filename!r}, but downloaded archive is {archive.name!r}"
        )
    actual = sha256_path(archive)
    if actual != expected:
        raise VerificationError(
            f"source archive checksum mismatch: expected {expected}, got {actual}"
        )
    return actual


def verify_source_archive(
    registry_report: dict[str, Any],
    archive: Path,
    checksum: Path,
    platform: str,
    expected_version: str,
    expected_schema: int,
    expected_revision: str,
) -> dict[str, Any]:
    if registry_report.get("status") != "passed":
        raise VerificationError("registry report did not pass")
    if registry_report.get("platform") != platform:
        raise VerificationError("registry report platform does not match requested platform")
    config_digest = require_digest(registry_report.get("config_digest"), "registry report config")
    expected_name = (
        f"corresponding-source-{platform}-{config_digest.removeprefix('sha256:')}.tar.gz"
    )
    if archive.name != expected_name:
        raise VerificationError(
            f"source archive name mismatch: expected {expected_name}, got {archive.name}"
        )
    archive_sha256 = verify_checksum(archive, checksum)
    inventory, coverage, source_manifest, member_count = read_archive_jsons(archive)
    artifact = inventory.get("artifact")
    if not isinstance(artifact, dict):
        raise VerificationError("runtime inventory has no artifact record")
    expected_artifact = {
        "config_digest": config_digest,
        "revision": expected_revision,
        "version": expected_version,
        "schema": expected_schema,
        "platform": platform,
    }
    for key, expected in expected_artifact.items():
        if artifact.get(key) != expected:
            raise VerificationError(
                f"runtime inventory artifact {key} mismatch: expected {expected!r}, "
                f"got {artifact.get(key)!r}"
            )
    if artifact.get("local_image_id") != config_digest:
        raise VerificationError(
            "runtime inventory local image ID does not match the verified config digest"
        )
    if coverage.get("status") != "passed" or coverage.get("platform") != platform:
        raise VerificationError(
            "platform coverage did not pass for the requested platform: "
            f"status={coverage.get('status')!r}, platform={coverage.get('platform')!r}"
        )
    if source_manifest.get("status") != "collected":
        raise VerificationError(
            f"corresponding source manifest is not collected: {source_manifest.get('status')!r}"
        )
    return {
        "status": "passed",
        "anonymous": registry_report.get("anonymous") is True,
        "platform": platform,
        "requested_index_digest": registry_report["index_digest"],
        "index_manifests": registry_report.get("index_manifests", []),
        "manifest_digest": registry_report["manifest_digest"],
        "config_digest": config_digest,
        "revision": expected_revision,
        "version": expected_version,
        "schema": expected_schema,
        "source_archive": {
            "name": archive.name,
            "sha256": archive_sha256,
            "checksum_file": checksum.name,
            "member_count": member_count,
            "read_only_validation": True,
            "extracted": False,
        },
        "artifact": {key: artifact[key] for key in expected_artifact},
        "platform_coverage": {
            "status": coverage["status"],
            "platform": coverage["platform"],
        },
        "source_manifest_status": source_manifest["status"],
    }


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    commands = command_parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="inspect a public registry image index")
    inspect.add_argument("--repository", required=True)
    inspect.add_argument("--index-digest", required=True)
    inspect.add_argument("--platform", choices=("amd64", "arm64"), required=True)
    inspect.add_argument("--expected-revision", required=True)
    inspect.add_argument("--expected-image-version", required=True)

    archive = commands.add_parser("verify-archive", help="verify a downloaded source archive")
    archive.add_argument("--registry-report", type=Path, required=True)
    archive.add_argument("--archive", type=Path, required=True)
    archive.add_argument("--checksum", type=Path, required=True)
    archive.add_argument("--platform", choices=("amd64", "arm64"), required=True)
    archive.add_argument("--version", required=True)
    archive.add_argument("--schema", type=int, required=True)
    archive.add_argument("--revision", required=True)
    return command_parser


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "inspect":
            result = inspect_published_image(
                args.repository,
                args.index_digest,
                args.platform,
                args.expected_revision,
                args.expected_image_version,
            )
        else:
            result = verify_source_archive(
                load_json(args.registry_report),
                args.archive,
                args.checksum,
                args.platform,
                args.version,
                args.schema,
                args.revision,
            )
    except (OSError, tarfile.TarError, VerificationError, ValueError) as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
