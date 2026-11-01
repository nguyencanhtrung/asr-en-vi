#!/usr/bin/env python3
"""Verify the reviewed native payload for the image's actual architecture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import sysconfig
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_MANIFEST = Path("/usr/local/share/licenses/asr-studio/platform-coverage.json")
DEFAULT_LICENSE_ROOT = Path("/usr/local/share/licenses/asr-studio")
REQUIRED_DISTRIBUTIONS = frozenset(
    {"ctranslate2", "tokenizers", "torch", "torchaudio", "torchcodec"}
)


class CoverageError(RuntimeError):
    """Raised when a platform payload is absent, stale, or unreviewed."""


def sha256_path(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize_platform(machine: str) -> str:
    normalized = machine.casefold()
    if normalized in {"x86_64", "amd64"}:
        return "amd64"
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    raise CoverageError(f"unsupported machine: {machine}")


def safe_member(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise CoverageError(f"unsafe {label} path: {value}")
    return path.as_posix()


def native_member(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".so") or ".so." in name


def require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise CoverageError(f"invalid SHA-256 for {label}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise CoverageError(f"invalid SHA-256 for {label}") from exc
    return value


def component_purls_digest(components: Any, label: str) -> tuple[int, str, set[str]]:
    if not isinstance(components, list) or not components:
        raise CoverageError(f"{label} has no components")
    purls = []
    for component in components:
        if not isinstance(component, dict) or not isinstance(component.get("purl"), str):
            raise CoverageError(f"{label} has a component without a purl")
        purls.append(component["purl"])
    if len(set(purls)) != len(purls):
        raise CoverageError(f"{label} has duplicate component purls")
    ordered = sorted(purls)
    digest = hashlib.sha256(("\n".join(ordered) + "\n").encode()).hexdigest()
    return len(ordered), digest, set(ordered)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"cannot read coverage manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise CoverageError("unsupported platform coverage manifest")
    if not isinstance(manifest.get("platforms"), dict):
        raise CoverageError("coverage manifest has no platform records")
    return manifest


def check_notices(
    manifest: dict[str, Any],
    license_root: Path,
) -> dict[str, str]:
    expected = manifest.get("required_notice_hashes")
    if not isinstance(expected, dict) or not expected:
        raise CoverageError("platform record has no required notice hashes")
    actual: dict[str, str] = {}
    for raw_path, raw_hash in expected.items():
        path = license_root / safe_member(str(raw_path), "notice")
        expected_hash = require_hash(raw_hash, f"notice {raw_path}")
        if not path.is_file():
            raise CoverageError(f"missing required notice: {raw_path}")
        actual[str(raw_path)] = sha256_path(path)
        if actual[str(raw_path)] != expected_hash:
            raise CoverageError(f"notice hash mismatch: {raw_path}")
    return actual


def check_package(
    record: dict[str, Any],
    purelib: Path,
    replacement_records: dict[str, dict[str, Any]],
    distribution_getter: Callable[[str], Any],
) -> dict[str, Any]:
    name = record.get("distribution")
    version = record.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise CoverageError("malformed package coverage record")
    try:
        distribution = distribution_getter(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise CoverageError(f"missing reviewed distribution: {name}") from exc
    if distribution.version != version:
        raise CoverageError(
            f"version mismatch for {name}: expected {version}, got {distribution.version}"
        )

    raw_native = record.get("native_files")
    if not isinstance(raw_native, list) or not raw_native:
        raise CoverageError(f"no native files recorded for {name}")
    expected_native: dict[str, dict[str, Any]] = {}
    for item in raw_native:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise CoverageError(f"malformed native file record for {name}")
        path = safe_member(item["path"], f"{name} native")
        if path in expected_native:
            raise CoverageError(f"duplicate native file for {name}: {path}")
        expected_native[path] = item
        require_hash(item.get("sha256"), f"{name}:{path}")

    files = distribution.files or ()
    actual_native = {
        PurePosixPath(str(path)).as_posix()
        for path in files
        if native_member(PurePosixPath(str(path)).as_posix())
    }
    if actual_native != set(expected_native):
        missing = sorted(set(expected_native) - actual_native)
        extra = sorted(actual_native - set(expected_native))
        raise CoverageError(
            f"native file set mismatch for {name}: missing={missing}, extra={extra}"
        )

    native_report = []
    for path, item in sorted(expected_native.items()):
        target = Path(distribution.locate_file(path))
        if not target.is_file():
            raise CoverageError(f"missing native object for {name}: {path}")
        actual_hash = sha256_path(target)
        replacement = bool(item.get("replacement"))
        if replacement:
            replacement_record = replacement_records.get(path)
            if replacement_record is None:
                raise CoverageError(f"unrecorded GNU replacement: {name}:{path}")
            expected_actual = require_hash(
                replacement_record.get("replacement_sha256"),
                f"replacement {path}",
            )
            if actual_hash != expected_actual:
                raise CoverageError(f"replacement hash mismatch: {name}:{path}")
        elif actual_hash != item["sha256"]:
            raise CoverageError(f"native hash mismatch: {name}:{path}")
        native_report.append(
            {
                "path": path,
                "sha256": actual_hash,
                "wheel_sha256": item["sha256"],
                "replacement": replacement,
            }
        )

    license_report = []
    for item in record.get("license_files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise CoverageError(f"malformed license file record for {name}")
        path = safe_member(item["path"], f"{name} license")
        expected_hash = require_hash(item.get("sha256"), f"{name}:{path}")
        target = Path(distribution.locate_file(path))
        if not target.is_file() or sha256_path(target) != expected_hash:
            raise CoverageError(f"license hash mismatch: {name}:{path}")
        license_report.append({"path": path, "sha256": expected_hash})

    sbom_report = None
    if "sbom" in record:
        sbom = record.get("sbom")
        if not isinstance(sbom, dict) or not isinstance(sbom.get("path"), str):
            raise CoverageError(f"malformed SBOM record for {name}")
        sbom_path = safe_member(sbom["path"], f"{name} SBOM")
        expected_sbom_hash = require_hash(sbom.get("sha256"), f"{name} SBOM")
        target = Path(distribution.locate_file(sbom_path))
        if not target.is_file():
            raise CoverageError(f"missing SBOM for {name}: {sbom_path}")
        actual_sbom_hash = sha256_path(target)
        if actual_sbom_hash != expected_sbom_hash:
            raise CoverageError(f"SBOM hash mismatch: {name}:{sbom_path}")
        try:
            sbom_payload = json.loads(target.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CoverageError(f"invalid SBOM for {name}: {exc}") from exc
        component_count, component_digest, _ = component_purls_digest(
            sbom_payload.get("components"), f"{name} SBOM"
        )
        if component_count != sbom.get("component_count"):
            raise CoverageError(f"SBOM component count mismatch: {name}")
        if component_digest != sbom.get("component_purls_sha256"):
            raise CoverageError(f"SBOM component set mismatch: {name}")
        sbom_report = {
            "path": sbom_path,
            "sha256": actual_sbom_hash,
            "component_count": component_count,
            "component_purls_sha256": component_digest,
        }

    wheel = record.get("wheel")
    if not isinstance(wheel, dict):
        raise CoverageError(f"missing wheel provenance for {name}")
    wheel_hash = require_hash(wheel.get("sha256"), f"{name} wheel")
    result = {
        "version": distribution.version,
        "wheel_sha256": wheel_hash,
        "native_files": native_report,
        "license_files": license_report,
    }
    if sbom_report is not None:
        result["sbom"] = sbom_report
    return result


def check_tokenizer_rust_coverage(
    tokenizers_record: dict[str, Any],
    tokenizers_report: dict[str, Any],
    notice_report: dict[str, str],
    license_root: Path,
) -> dict[str, Any]:
    if not isinstance(tokenizers_record, dict):
        raise CoverageError("platform record has no tokenizers Rust coverage")
    raw_path = tokenizers_record.get("rust_manifest_path")
    if not isinstance(raw_path, str):
        raise CoverageError("tokenizers Rust manifest path is missing")
    manifest_path = safe_member(raw_path, "tokenizers Rust manifest")
    target = license_root / "third-party" / manifest_path
    if not target.is_file():
        raise CoverageError("missing tokenizers Rust manifest")
    expected_hash = require_hash(
        tokenizers_record.get("rust_manifest_sha256"), "tokenizers Rust manifest"
    )
    actual_hash = sha256_path(target)
    if actual_hash != expected_hash:
        raise CoverageError("tokenizers Rust manifest hash mismatch")
    try:
        rust_manifest = json.loads(target.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"invalid tokenizers Rust manifest: {exc}") from exc
    count, digest, _ = component_purls_digest(
        rust_manifest.get("components"), "tokenizers Rust manifest"
    )
    if count != tokenizers_record.get("component_count"):
        raise CoverageError("tokenizers Rust component count mismatch")
    if digest != tokenizers_record.get("component_purls_sha256"):
        raise CoverageError("tokenizers Rust component set mismatch")
    sbom_report = tokenizers_report.get("sbom")
    if not isinstance(sbom_report, dict):
        raise CoverageError("tokenizers SBOM report is missing")
    if (
        sbom_report.get("component_count") != count
        or sbom_report.get("component_purls_sha256") != digest
    ):
        raise CoverageError("tokenizers SBOM and Rust component sets differ")

    component_notice_paths = set()
    for component in rust_manifest["components"]:
        raw_notice = component.get("notice_path")
        prefix = "third_party/notices/"
        if not isinstance(raw_notice, str) or not raw_notice.startswith(prefix):
            raise CoverageError("tokenizers Rust component has an invalid notice path")
        notice_path = safe_member(raw_notice[len(prefix) :], "tokenizers Rust notice")
        if notice_path not in notice_report:
            raise CoverageError(f"missing tokenizers Rust notice: {notice_path}")
        component_notice_paths.add(notice_path)
    expected_notice_paths = {
        path for path in notice_report if path.startswith("tokenizers/0.23.3/rust/")
    }
    if component_notice_paths != expected_notice_paths:
        raise CoverageError("tokenizers Rust notice set differs from component set")
    return {
        "rust_manifest_sha256": actual_hash,
        "component_count": count,
        "component_purls_sha256": digest,
        "notice_count": len(component_notice_paths),
    }


def check_coverage(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    machine: str | None = None,
    license_root: Path = DEFAULT_LICENSE_ROOT,
    purelib: Path | None = None,
    distribution_getter: Callable[[str], Any] = importlib.metadata.distribution,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    actual_machine = machine or platform.machine()
    platform_name = normalize_platform(actual_machine)
    record = manifest["platforms"].get(platform_name)
    if not isinstance(record, dict):
        raise CoverageError(f"no reviewed coverage for {platform_name}")
    machines = record.get("machines")
    if not isinstance(machines, list) or actual_machine not in machines:
        raise CoverageError(f"machine {actual_machine} is not bound to {platform_name}")

    replacement_path = license_root / "openmp-runtime.json"
    try:
        replacement_payload = json.loads(replacement_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"cannot read GNU replacement record: {exc}") from exc
    replacements = replacement_payload.get("replacements")
    if not isinstance(replacements, list):
        raise CoverageError("GNU replacement record is malformed")
    replacement_records: dict[str, dict[str, Any]] = {}
    for item in replacements:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise CoverageError("GNU replacement entry is malformed")
        path = safe_member(item["path"], "GNU replacement")
        if path in replacement_records:
            raise CoverageError(f"duplicate GNU replacement: {path}")
        source = Path(str(item.get("source", "")))
        if not source.is_file():
            raise CoverageError(f"missing GNU replacement source: {source}")
        replacement_hash = require_hash(item.get("replacement_sha256"), f"replacement {path}")
        if sha256_path(source) != replacement_hash:
            raise CoverageError(f"GNU replacement source hash mismatch: {path}")
        replacement_records[path] = item

    package_records = record.get("packages")
    if not isinstance(package_records, list) or not package_records:
        raise CoverageError(f"no packages recorded for {platform_name}")
    package_names = []
    for package in package_records:
        if not isinstance(package, dict) or not isinstance(package.get("distribution"), str):
            raise CoverageError("package record has no distribution name")
        name = package["distribution"]
        if name in package_names:
            raise CoverageError(f"duplicate distribution record: {name}")
        package_names.append(name)
    if set(package_names) != REQUIRED_DISTRIBUTIONS:
        raise CoverageError(
            "required distribution set mismatch: "
            f"missing={sorted(REQUIRED_DISTRIBUTIONS - set(package_names))}, "
            f"extra={sorted(set(package_names) - REQUIRED_DISTRIBUTIONS)}"
        )
    package_report = {}
    for package in package_records:
        if not isinstance(package, dict):
            raise CoverageError("malformed package coverage record")
        name = package.get("distribution")
        if not isinstance(name, str):
            raise CoverageError("package record has no distribution name")
        package_report[name] = check_package(
            package,
            Path(purelib or sysconfig.get_paths()["purelib"]),
            replacement_records,
            distribution_getter,
        )

    notice_report = check_notices(
        {"required_notice_hashes": record.get("required_notice_hashes")},
        license_root / "third-party",
    )
    tokenizer_rust_report = check_tokenizer_rust_coverage(
        record.get("tokenizers_rust"),
        package_report["tokenizers"],
        notice_report,
        license_root,
    )
    return {
        "schema": manifest["schema"],
        "status": "passed",
        "platform": platform_name,
        "machine": actual_machine,
        "packages": package_report,
        "required_notice_hashes": notice_report,
        "tokenizers_rust": tokenizer_rust_report,
        "gnu_replacements": sorted(replacement_records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--machine", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        report = check_coverage(args.manifest, machine=args.machine)
    except CoverageError as exc:
        print(f"platform coverage failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
