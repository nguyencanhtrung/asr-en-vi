#!/usr/bin/env python3
"""Resolve a published platform image's config digest from the public GHCR registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

REGISTRY = "ghcr.io"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PLATFORMS = {"amd64", "arm64"}
INDEX_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
    )
)
MANIFEST_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)
CONFIG_ACCEPT = (
    "application/vnd.oci.image.config.v1+json, application/vnd.docker.container.image.v1+json"
)


class ResolutionError(RuntimeError):
    """A public image config digest could not be proved."""


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ResolutionError(f"invalid SHA-256 digest for {label}: {value!r}")
    return value


def anonymous_registry_token(repository: str) -> str:
    query = urllib.parse.urlencode({"service": REGISTRY, "scope": f"repository:{repository}:pull"})
    request = urllib.request.Request(
        f"https://{REGISTRY}/token?{query}",
        headers={"Accept": "application/json", "User-Agent": "asr-studio-release-resolver/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"anonymous registry token request failed: {exc}") from exc
    token = payload.get("token") or payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise ResolutionError("anonymous registry token response has no token")
    return token


def registry_json(
    repository: str,
    kind: str,
    digest: str,
    token: str,
    accept: str,
) -> dict[str, Any]:
    """Fetch and hash-check one registry JSON response."""
    require_digest(digest, f"registry {kind}")
    request = urllib.request.Request(
        f"https://{REGISTRY}/v2/{repository}/{kind}/{digest}",
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "User-Agent": "asr-studio-release-resolver/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise ResolutionError(f"registry {kind} request failed for {digest}: {exc}") from exc
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual != digest:
        raise ResolutionError(
            f"registry {kind} digest mismatch: requested {digest}, received {actual}"
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResolutionError(f"registry {kind} response is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ResolutionError(f"registry {kind} response is not an object")
    return value


def select_platform_descriptor(index: dict[str, Any], platform: str) -> dict[str, Any]:
    """Select exactly one native Linux child, ignoring attestations."""
    if platform not in PLATFORMS:
        raise ResolutionError(f"unsupported platform: {platform}")
    descriptors = index.get("manifests")
    if not isinstance(descriptors, list):
        raise ResolutionError("registry response is not an image index")

    matches = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise ResolutionError("image index contains a malformed descriptor")
        descriptor_platform = descriptor.get("platform")
        if descriptor_platform is None:
            # OCI attestation descriptors may omit platform metadata.
            continue
        if not isinstance(descriptor_platform, dict):
            raise ResolutionError("image index contains malformed platform metadata")
        os_name = descriptor_platform.get("os")
        architecture = descriptor_platform.get("architecture")
        if os_name is None and architecture is None:
            # Be tolerant of attestation descriptors with an empty platform object.
            continue
        if not isinstance(os_name, str) or not isinstance(architecture, str):
            raise ResolutionError("image index contains malformed platform metadata")
        if os_name == "unknown" or architecture == "unknown":
            # BuildKit provenance/SBOM attestations commonly use unknown/unknown.
            continue
        if os_name == "linux" and architecture == platform:
            matches.append(descriptor)

    if len(matches) != 1:
        raise ResolutionError(
            f"expected exactly one linux/{platform} child manifest, found {len(matches)}"
        )
    return {
        "digest": require_digest(matches[0].get("digest"), f"linux/{platform} child manifest"),
        "platform": matches[0]["platform"],
    }


def resolve_image_config(repository: str, published_digest: str, platform: str) -> dict[str, Any]:
    """Resolve the config digest for one platform from a public image index."""
    if platform not in PLATFORMS:
        raise ResolutionError(f"unsupported platform: {platform}")
    if not repository or "/" not in repository:
        raise ResolutionError(f"invalid repository: {repository!r}")

    token = anonymous_registry_token(repository)
    index = registry_json(repository, "manifests", published_digest, token, INDEX_ACCEPT)
    child = select_platform_descriptor(index, platform)
    manifest_digest = child["digest"]
    manifest = registry_json(repository, "manifests", manifest_digest, token, MANIFEST_ACCEPT)
    config_descriptor = manifest.get("config")
    if not isinstance(config_descriptor, dict):
        raise ResolutionError("platform manifest has no config descriptor")
    config_digest = require_digest(config_descriptor.get("digest"), "platform config")
    config = registry_json(repository, "blobs", config_digest, token, CONFIG_ACCEPT)
    if config.get("os") != "linux" or config.get("architecture") != platform:
        raise ResolutionError(
            "platform config mismatch: "
            f"expected linux/{platform}, got {config.get('os')}/{config.get('architecture')}"
        )
    return {
        "status": "passed",
        "anonymous": True,
        "repository": repository,
        "platform": platform,
        "index_digest": published_digest,
        "manifest_digest": manifest_digest,
        "config_digest": config_digest,
        "config_os": config["os"],
        "config_architecture": config["architecture"],
    }


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    command_parser.add_argument("--repository", required=True)
    command_parser.add_argument(
        "--published-digest",
        "--index-digest",
        dest="published_digest",
        required=True,
        help="the digest emitted for the pushed platform image index",
    )
    command_parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = resolve_image_config(args.repository, args.published_digest, args.platform)
    except (OSError, urllib.error.URLError, ResolutionError, ValueError) as exc:
        print(f"image config resolution failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
