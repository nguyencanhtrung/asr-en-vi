#!/usr/bin/env python3
"""Collect and validate release notices without treating metadata as approval.

The collector downloads only public, explicitly configured artifacts.  Every
download is hashed before it is copied into ``third_party``.  The generated
manifest keeps the package-declared expression separate from the reviewed
expression and reports unresolved runtime evidence as blockers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_TIMEOUT = 120
KNOWN_OPERATORS = {"AND", "OR", "WITH"}
SPDX_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-+]*")


class CollectionError(RuntimeError):
    """A configured artifact could not be proved."""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    root = root.resolve()
    if candidate != root and root not in candidate.parents:
        raise CollectionError(f"path escapes root: {relative}")
    return candidate


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        with source.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, stream)
    temporary.chmod(0o644)
    os.replace(temporary, destination)


def request_for(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": "asr-studio-license-collector/0.1",
            "Accept": "*/*",
        },
    )


def download_checked(
    url: str,
    destination: Path,
    expected_sha256: str | None,
    *,
    offline: bool,
) -> dict[str, object]:
    """Download one artifact, or validate a previously downloaded artifact."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        if offline:
            raise CollectionError(f"offline artifact missing: {destination}")
        temporary = destination.with_name(f".{destination.name}.download")
        try:
            with (
                urllib.request.urlopen(request_for(url), timeout=DEFAULT_TIMEOUT) as response,
                temporary.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
            os.replace(temporary, destination)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            temporary.unlink(missing_ok=True)
            raise CollectionError(f"download failed for {url}: {exc}") from exc

    actual = sha256_path(destination)
    if expected_sha256 and actual != expected_sha256:
        raise CollectionError(
            f"sha256 mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    return {
        "url": url,
        "path": str(destination),
        "expected_sha256": expected_sha256,
        "actual_sha256": actual,
        "hash_pinned": bool(expected_sha256),
        "bytes": destination.stat().st_size,
        "validated": bool(expected_sha256 and actual == expected_sha256),
    }


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def extract_zip_member(archive: Path, suffix: str) -> tuple[str, bytes]:
    with zipfile.ZipFile(archive) as wheel:
        matches = [name for name in wheel.namelist() if name.endswith(suffix)]
        if len(matches) != 1:
            raise CollectionError(f"expected one {suffix} in {archive}, found {matches}")
        name = matches[0]
        return name, wheel.read(name)


def extract_zip_named(archive: Path, member_name: str) -> bytes:
    with zipfile.ZipFile(archive) as wheel:
        try:
            return wheel.read(member_name)
        except KeyError as exc:
            raise CollectionError(f"missing {member_name} in {archive}") from exc


def extract_tar_member(archive: Path, suffix: str) -> tuple[str, bytes]:
    with tarfile.open(archive, mode="r:*") as source:
        matches = [member for member in source.getmembers() if member.name.endswith(suffix)]
        if len(matches) != 1:
            raise CollectionError(f"expected one {suffix} in {archive}, found {len(matches)}")
        member = matches[0]
        stream = source.extractfile(member)
        if stream is None:
            raise CollectionError(f"tar member is not a file: {member.name}")
        return member.name, stream.read()


def write_bytes(root: Path, relative: str, content: bytes) -> Path:
    destination = safe_path(root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, destination)
    return destination


def expression_ids(expression: str) -> list[str]:
    return sorted(
        {token for token in SPDX_ID_RE.findall(expression) if token.upper() not in KNOWN_OPERATORS}
    )


def crate_identity(purl: str) -> tuple[str, str] | None:
    match = re.match(r"pkg:cargo/([^@?]+)@([^?]+)", purl)
    if not match:
        return None
    return urllib.parse.unquote(match.group(1)), urllib.parse.unquote(match.group(2))


def license_file_members(archive: Path) -> list[tuple[str, bytes]]:
    matches: list[tuple[str, bytes]] = []
    with tarfile.open(archive, mode="r:*") as source:
        for member in source.getmembers():
            if not member.isfile() or member.size > 2 * 1024 * 1024:
                continue
            basename = Path(member.name).name.lower()
            if not (
                basename.startswith("license")
                or basename.startswith("licence")
                or basename.startswith("copying")
                or basename.startswith("notice")
                or basename == "copyright"
            ):
                continue
            stream = source.extractfile(member)
            if stream is not None:
                matches.append((member.name, stream.read()))
    return matches


def collect_tokenizer_rust_notices(
    *,
    spec: dict,
    artifact_root: Path,
    repo_root: Path,
    wheel: Path,
    sdist: Path,
    offline: bool,
) -> tuple[dict, list[str]]:
    """Render one human-readable notice per CycloneDX cargo component."""

    sbom_name, sbom_bytes = extract_zip_member(wheel, ".cyclonedx.json")
    try:
        sbom = json.loads(sbom_bytes)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"invalid tokenizers SBOM {sbom_name}: {exc}") from exc
    components = sbom.get("components", [])
    if len(components) != 127:
        raise CollectionError(f"tokenizers SBOM has {len(components)} components, expected 127")

    write_bytes(
        repo_root,
        "third_party/notices/tokenizers/0.23.3/tokenizers-python.cyclonedx.json",
        sbom_bytes,
    )
    cargo_lock_name, cargo_lock = extract_tar_member(sdist, "bindings/python/Cargo.lock")
    write_bytes(repo_root, "third_party/notices/tokenizers/0.23.3/Cargo.lock", cargo_lock)

    spdx_root = artifact_root / "downloads/spdx"
    spdx_records: dict[str, dict[str, object]] = {}
    blockers: list[str] = []
    spdx_config = spec["tokenizers_spdx"]
    for identifier, filename in spdx_config["licenses"].items():
        url = f"{spdx_config['base_url']}/{filename}"
        try:
            spdx_records[identifier] = download_checked(
                url,
                spdx_root / filename,
                spdx_config["sha256"].get(filename),
                offline=offline,
            )
        except CollectionError as exc:
            blockers.append(str(exc))

    component_records: list[dict[str, object]] = []
    for component in sorted(
        components, key=lambda item: (item.get("name", ""), item.get("version", ""))
    ):
        name = str(component.get("name", "unknown"))
        version = str(component.get("version", "unknown"))
        expression = " ".join(
            str(license_item.get("expression", ""))
            for license_item in component.get("licenses", [])
            if license_item.get("expression")
        ).strip()
        if not expression:
            blockers.append(f"tokenizers component has no license expression: {name}@{version}")
        identifiers = expression_ids(expression)
        unknown_ids = [
            identifier for identifier in identifiers if identifier not in spdx_config["licenses"]
        ]
        if unknown_ids:
            blockers.append(f"unknown SPDX identifiers for {name}@{version}: {unknown_ids}")

        cargo = crate_identity(str(component.get("purl", "")))
        cargo_record: dict[str, object] = {"status": "not-a-cargo-purl"}
        license_members: list[tuple[str, bytes]] = []
        if cargo:
            crate_name, crate_version = cargo
            crate_filename = f"{crate_name}-{crate_version}.crate"
            crate_url = f"https://crates.io/api/v1/crates/{urllib.parse.quote(crate_name)}/{urllib.parse.quote(crate_version)}/download"
            try:
                cargo_record = download_checked(
                    crate_url,
                    artifact_root / "cargo-crates" / crate_filename,
                    None,
                    offline=offline,
                )
                license_members = license_file_members(Path(cargo_record["path"]))
            except CollectionError as exc:
                blockers.append(str(exc))
                cargo_record = {"status": "blocked", "url": crate_url, "error": str(exc)}

        lines = [
            f"Component: {name}",
            f"Version: {version}",
            f"PURL: {component.get('purl', '')}",
            f"License expression: {expression}",
        ]
        for key in ("author", "publisher", "group"):
            if component.get(key):
                lines.append(f"{key.title()}: {component[key]}")
        references = component.get("externalReferences", [])
        for reference in references:
            if reference.get("url"):
                lines.append(f"Source: {reference['url']}")
        lines.append("")
        if license_members:
            lines.append("License files from the exact crates.io archive:")
            for member_name, content in license_members:
                lines.extend(
                    [f"--- {member_name} ---", content.decode("utf-8", errors="replace"), ""]
                )
        else:
            lines.append("Canonical SPDX texts for every option in the declared expression:")
            for identifier in identifiers:
                record = spdx_records.get(identifier)
                if record and Path(str(record["path"])).is_file():
                    lines.extend(
                        [
                            f"--- SPDX {identifier} ({record['url']}) ---",
                            Path(str(record["path"])).read_text(encoding="utf-8", errors="replace"),
                            "",
                        ]
                    )
        safe_name = re.sub(r"[^A-Za-z0-9_.+-]+", "_", f"{name}-{version}")
        notice_path = write_bytes(
            repo_root,
            f"third_party/notices/tokenizers/0.23.3/rust/{safe_name}/NOTICE.txt",
            ("\n".join(lines).rstrip() + "\n").encode("utf-8"),
        )
        component_records.append(
            {
                "name": name,
                "version": version,
                "purl": component.get("purl"),
                "license_expression": expression,
                "spdx_identifiers": identifiers,
                "notice_path": str(notice_path.relative_to(repo_root)),
                "cargo_archive": cargo_record,
                "license_file_count": len(license_members),
                "status": "collected"
                if not unknown_ids and cargo_record.get("status") != "blocked"
                else "blocked",
            }
        )

    mismatch = [
        {
            "component": component["name"],
            "component_version": component["version"],
            "python_version": "0.23.3",
        }
        for component in components
        if component.get("name") == "tokenizers" and component.get("version") != "0.23.3"
    ]
    manifest = {
        "schema": 1,
        "sbom": {
            "archive_member": sbom_name,
            "sha256": hashlib.sha256(sbom_bytes).hexdigest(),
            "component_count": len(components),
        },
        "cargo_lock": {
            "archive_member": cargo_lock_name,
            "sha256": hashlib.sha256(cargo_lock).hexdigest(),
        },
        "source_metadata_mismatch": mismatch,
        "spdx_texts": spdx_records,
        "components": component_records,
        "status": "blocked" if blockers else "collected",
        "blockers": blockers,
    }
    write_json(
        repo_root / "third_party/notices/tokenizers/0.23.3/rust-license-manifest.json", manifest
    )
    return manifest, blockers


def collect(
    spec: dict, inventory: dict, repo_root: Path, artifact_root: Path, offline: bool
) -> dict:
    records: list[dict[str, object]] = []
    blockers: list[str] = []
    downloads = artifact_root / "downloads"

    for item in spec.get("notice_artifacts", []):
        try:
            artifact = download_checked(
                item["url"],
                downloads / f"notice-{item['id']}",
                item.get("sha256"),
                offline=offline,
            )
            destination = safe_path(repo_root, f"third_party/{item['destination']}")
            atomic_copy(Path(str(artifact["path"])), destination)
            record = {
                **item,
                **artifact,
                "destination": str(destination.relative_to(repo_root)),
                "status": "collected",
            }
        except CollectionError as exc:
            record = {**item, "status": "blocked", "error": str(exc)}
            blockers.append(str(exc))
        records.append(record)

    package_records: list[dict[str, object]] = []
    for item in spec.get("package_artifacts", []):
        try:
            record = {
                **item,
                **download_checked(
                    item["url"],
                    downloads / item["artifact_name"],
                    item.get("sha256"),
                    offline=offline,
                ),
                "status": "validated",
            }
        except CollectionError as exc:
            record = {**item, "status": "blocked", "error": str(exc)}
            blockers.append(str(exc))
        package_records.append(record)

    installed_notice_records: list[dict[str, object]] = []
    for item in spec.get("installed_notice_artifacts", []):
        wheel = downloads / item["wheel_artifact"]
        try:
            if not wheel.exists():
                raise CollectionError(f"installed-notice wheel missing: {wheel}")
            content = extract_zip_named(wheel, item["archive_member"])
            actual = hashlib.sha256(content).hexdigest()
            if actual != item["sha256"]:
                raise CollectionError(
                    f"sha256 mismatch for {item['archive_member']}: "
                    f"expected {item['sha256']}, got {actual}"
                )
            destination = write_bytes(repo_root, f"third_party/{item['destination']}", content)
            installed_notice_records.append(
                {
                    **item,
                    "actual_sha256": actual,
                    "bytes": len(content),
                    "destination": str(destination.relative_to(repo_root)),
                    "status": "collected",
                }
            )
        except CollectionError as exc:
            installed_notice_records.append({**item, "status": "blocked", "error": str(exc)})
            blockers.append(str(exc))

    tokenizers_manifest: dict | None = None
    tokenizers_wheel = downloads / "tokenizers-0.23.3-cp310-manylinux_x86_64.whl"
    tokenizers_sdist = downloads / "tokenizers-0.23.3.tar.gz"
    if tokenizers_wheel.exists() and tokenizers_sdist.exists():
        try:
            tokenizers_manifest, tokenizers_blockers = collect_tokenizer_rust_notices(
                spec=spec,
                artifact_root=artifact_root,
                repo_root=repo_root,
                wheel=tokenizers_wheel,
                sdist=tokenizers_sdist,
                offline=offline,
            )
            blockers.extend(tokenizers_blockers)
        except CollectionError as exc:
            blockers.append(str(exc))
    else:
        blockers.append(
            "tokenizers wheel and sdist are required before Rust notices can be rendered"
        )

    runtime_findings = []
    for runtime_blocker in spec.get("runtime_blockers", []):
        if runtime_blocker.get("blocking", True):
            blockers.append(f"{runtime_blocker['id']}: {runtime_blocker['detail']}")
        else:
            runtime_findings.append(runtime_blocker)

    python_inventory = {item["name"].lower(): item for item in inventory.get("python_packages", [])}
    declared_review = {
        "ctranslate2": {
            "declared": python_inventory.get("ctranslate2", {}).get("license_metadata", ""),
            "reviewed": "MIT plus embedded native dependency review",
        },
        "flatbuffers": {
            "declared": python_inventory.get("flatbuffers", {}).get("license_metadata", ""),
            "reviewed": "Apache-2.0",
        },
        "tokenizers": {
            "declared": "Apache classifier",
            "reviewed": "Apache-2.0 root plus 127 cargo expressions",
        },
        "primepy": {
            "declared": python_inventory.get("primepy", {}).get("license_metadata", "UNKNOWN"),
            "reviewed": "MIT at pinned upstream commit",
        },
        "cuda-toolkit": {
            "declared": python_inventory.get("cuda-toolkit", {}).get("license_metadata", ""),
            "reviewed": "resolver-only; no standalone code license",
        },
    }
    manifest = {
        "schema": 1,
        "task": "issue17-license-bundle",
        "inventory_scope": inventory.get("scope"),
        "inventory_counts": {
            "python": len(inventory.get("python_packages", [])),
            "system": len(inventory.get("system_packages", [])),
            "fonts": len(inventory.get("fonts", [])),
            "web_vendor": len(inventory.get("web_vendor", [])),
        },
        "declared_vs_reviewed": declared_review,
        "web_vendor_packages": inventory.get("web_vendor_packages", []),
        "notices": records,
        "package_artifacts": package_records,
        "installed_notices": installed_notice_records,
        "tokenizers_rust": tokenizers_manifest,
        "runtime_blockers": spec.get("runtime_blockers", []),
        "runtime_findings": runtime_findings,
        "status": "blocked" if blockers else "collected",
        "blockers": sorted(set(blockers)),
    }
    write_json(repo_root / "third_party/NOTICE-MANIFEST.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=Path("third_party/bundle-spec.json"))
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/release/runtime-inventory-amd64.json")
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact-root", type=Path, default=Path("/tmp/asr-issue17-bundle"))
    parser.add_argument("--offline", action="store_true", help="validate existing downloads only")
    parser.add_argument(
        "--allow-unresolved", action="store_true", help="write the blocked manifest and exit zero"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    spec = load_json(
        (repo_root / args.spec).resolve() if not args.spec.is_absolute() else args.spec
    )
    inventory = load_json(
        (repo_root / args.inventory).resolve()
        if not args.inventory.is_absolute()
        else args.inventory
    )
    manifest = collect(spec, inventory, repo_root, args.artifact_root.resolve(), args.offline)
    print(
        json.dumps(
            {"status": manifest["status"], "blockers": len(manifest["blockers"])}, sort_keys=True
        )
    )
    if manifest["blockers"] and not args.allow_unresolved:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
