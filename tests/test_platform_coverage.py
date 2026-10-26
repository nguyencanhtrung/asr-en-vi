from __future__ import annotations

import importlib.util
import json
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_platform_coverage", ROOT / "scripts/check-platform-coverage.py"
)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


def test_manifest_records_both_native_platforms_and_arm_recipe():
    manifest = json.loads((ROOT / "third_party/platform-coverage.json").read_text())

    assert manifest["source_evidence"]["official_arm_recipe"]["openblas_version"] == "0.3.26"
    assert manifest["source_evidence"]["official_arm_recipe"]["ruy_commit"].startswith("363f252")
    for platform_name in ("amd64", "arm64"):
        packages = {
            item["distribution"]: item for item in manifest["platforms"][platform_name]["packages"]
        }
        assert set(packages) == {
            "ctranslate2",
            "tokenizers",
            "torch",
            "torchaudio",
            "torchcodec",
        }
        assert all(item["native_files"] for item in packages.values())
        assert all(len(item["wheel"]["sha256"]) == 64 for item in packages.values())
        required = manifest["platforms"][platform_name]["required_notice_hashes"]
        rust_manifest = json.loads(
            (ROOT / "third_party/notices/tokenizers/0.23.3/rust-license-manifest.json").read_text()
        )
        component_notices = {
            item["notice_path"].removeprefix("third_party/notices/")
            for item in rust_manifest["components"]
        }
        assert component_notices <= set(required)
        assert len(component_notices) == 127
        assert manifest["platforms"][platform_name]["tokenizers_rust"]["component_count"] == 127
    assert (
        manifest["platforms"]["amd64"]["packages"][1]["sbom"]["sha256"]
        != manifest["platforms"]["arm64"]["packages"][1]["sbom"]["sha256"]
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    purelib = tmp_path / "purelib"
    notice_root = tmp_path / "licenses" / "third-party"
    notice_root.mkdir(parents=True)
    (notice_root / "notice.txt").write_text("reviewed notice\n")
    rust_notice = notice_root / "tokenizers/0.23.3/rust/demo-1.0/NOTICE.txt"
    rust_notice.parent.mkdir(parents=True)
    rust_notice.write_text("demo Rust notice\n")
    rust_notice_path = "third_party/notices/tokenizers/0.23.3/rust/demo-1.0/NOTICE.txt"
    component = {
        "name": "demo",
        "version": "1.0",
        "purl": "pkg:cargo/demo@1.0",
        "notice_path": rust_notice_path,
    }
    component_count, component_digest, _ = coverage.component_purls_digest([component], "fixture")
    rust_manifest_path = notice_root / "tokenizers/0.23.3/rust-license-manifest.json"
    rust_manifest_path.write_text(json.dumps({"components": [component]}))
    sbom_relative = "tokenizers-0.23.3.dist-info/sboms/tokenizers-python.cyclonedx.json"
    sbom_path = purelib / sbom_relative
    sbom_path.parent.mkdir(parents=True)
    sbom_path.write_text(json.dumps({"components": [component]}))
    distributions: dict[str, object] = {}
    packages = []
    for name in sorted(coverage.REQUIRED_DISTRIBUTIONS):
        version = "0.23.3" if name == "tokenizers" else "1.0"
        native = purelib / name / "native.so"
        native.parent.mkdir(parents=True, exist_ok=True)
        native.write_bytes(f"reviewed {name} native bytes".encode())
        native_relative = f"{name}/native.so"
        files = [PurePosixPath(native_relative)]
        package = {
            "distribution": name,
            "version": version,
            "wheel": {"url": f"https://example.invalid/{name}.whl", "sha256": "a" * 64},
            "native_files": [{"path": native_relative, "sha256": coverage.sha256_path(native)}],
            "license_files": [],
        }
        if name == "tokenizers":
            files.append(PurePosixPath(sbom_relative))
            package["sbom"] = {
                "path": sbom_relative,
                "sha256": coverage.sha256_path(sbom_path),
                "component_count": component_count,
                "component_purls_sha256": component_digest,
            }
        packages.append(package)

        class Distribution:
            def __init__(self, package_version: str, package_files: list[PurePosixPath]):
                self.version = package_version
                self.files = package_files

            @staticmethod
            def locate_file(path: str) -> Path:
                return purelib / path

        distributions[name] = Distribution(version, files)

    manifest = {
        "schema": 1,
        "platforms": {
            "amd64": {
                "machines": ["x86_64"],
                "required_notice_hashes": {
                    "notice.txt": coverage.sha256_path(notice_root / "notice.txt"),
                    "tokenizers/0.23.3/rust/demo-1.0/NOTICE.txt": coverage.sha256_path(rust_notice),
                    "tokenizers/0.23.3/rust-license-manifest.json": coverage.sha256_path(
                        rust_manifest_path
                    ),
                },
                "packages": packages,
                "tokenizers_rust": {
                    "rust_manifest_path": "tokenizers/0.23.3/rust-license-manifest.json",
                    "rust_manifest_sha256": coverage.sha256_path(rust_manifest_path),
                    "component_count": component_count,
                    "component_purls_sha256": component_digest,
                },
            }
        },
    }
    manifest_path = tmp_path / "platform-coverage.json"
    manifest_path.write_text(json.dumps(manifest))
    (tmp_path / "licenses" / "openmp-runtime.json").write_text('{"replacements": []}\n')

    return manifest_path, purelib, distributions


def test_coverage_gate_rejects_changed_native_bytes(tmp_path):
    manifest_path, purelib, distributions = _fixture(tmp_path)
    license_root = tmp_path / "licenses"
    result = coverage.check_coverage(
        manifest_path,
        machine="x86_64",
        license_root=license_root,
        purelib=purelib,
        distribution_getter=distributions.__getitem__,
    )
    assert result["status"] == "passed"

    (purelib / "ctranslate2/native.so").write_bytes(b"altered native bytes")
    with pytest.raises(coverage.CoverageError, match="native hash mismatch"):
        coverage.check_coverage(
            manifest_path,
            machine="x86_64",
            license_root=license_root,
            purelib=purelib,
            distribution_getter=distributions.__getitem__,
        )


def test_coverage_gate_rejects_missing_required_distribution(tmp_path):
    manifest_path, purelib, distributions = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["platforms"]["amd64"]["packages"].pop()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(coverage.CoverageError, match="required distribution set mismatch"):
        coverage.check_coverage(
            manifest_path,
            machine="x86_64",
            license_root=tmp_path / "licenses",
            purelib=purelib,
            distribution_getter=distributions.__getitem__,
        )


def test_coverage_gate_rejects_duplicate_distribution_record(tmp_path):
    manifest_path, purelib, distributions = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    packages = manifest["platforms"]["amd64"]["packages"]
    packages.append(dict(packages[0]))
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(coverage.CoverageError, match="duplicate distribution record"):
        coverage.check_coverage(
            manifest_path,
            machine="x86_64",
            license_root=tmp_path / "licenses",
            purelib=purelib,
            distribution_getter=distributions.__getitem__,
        )


def test_coverage_gate_rejects_missing_rust_component_notice(tmp_path):
    manifest_path, purelib, distributions = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    del manifest["platforms"]["amd64"]["required_notice_hashes"][
        "tokenizers/0.23.3/rust/demo-1.0/NOTICE.txt"
    ]
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(coverage.CoverageError, match="missing tokenizers Rust notice"):
        coverage.check_coverage(
            manifest_path,
            machine="x86_64",
            license_root=tmp_path / "licenses",
            purelib=purelib,
            distribution_getter=distributions.__getitem__,
        )
