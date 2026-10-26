from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_release_notices", ROOT / "scripts/collect-release-notices.py"
)
assert SPEC and SPEC.loader
notices = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notices)


def test_spec_keeps_declared_and_reviewed_license_distinct():
    spec = json.loads((ROOT / "third_party/bundle-spec.json").read_text())
    prime = next(item for item in spec["notice_artifacts"] if item["id"] == "primepy-license")
    assert prime["declared_license"].startswith("UNKNOWN")
    assert prime["reviewed_license"].startswith("MIT at upstream")


def test_download_checked_validates_exact_bytes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("exact bytes\n")
    destination = tmp_path / "downloads" / "copy.txt"
    expected = notices.sha256_path(source)

    record = notices.download_checked(source.as_uri(), destination, expected, offline=False)

    assert record["validated"] is True
    assert record["actual_sha256"] == expected
    assert destination.read_text() == source.read_text()


def test_download_checked_rejects_mismatched_hash(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("not the expected bytes\n")

    with pytest.raises(notices.CollectionError, match="sha256 mismatch"):
        notices.download_checked(source.as_uri(), tmp_path / "copy.txt", "0" * 64, offline=False)


def test_expression_ids_handles_compound_spdx_expression():
    expression = "(MIT OR Apache-2.0) AND Unicode-3.0"
    assert notices.expression_ids(expression) == ["Apache-2.0", "MIT", "Unicode-3.0"]


def test_safe_path_rejects_escape(tmp_path):
    with pytest.raises(notices.CollectionError, match="escapes root"):
        notices.safe_path(tmp_path, "../outside.txt")


def test_tokenizer_spec_carries_audit_sbom_hash_inputs():
    spec = json.loads((ROOT / "third_party/bundle-spec.json").read_text())
    assert spec["tokenizers_spdx"]["sha256"]["MIT.txt"]
    tokenizers = next(
        item for item in spec["package_artifacts"] if item["id"] == "tokenizers-wheel-amd64"
    )
    assert (
        tokenizers["sha256"] == "376851d22bcf9d650a5c3090bb83e6cf9e895fbf0595369fa4cd43c1f69b5f87"
    )


def test_extract_zip_named_requires_the_exact_notice_member(tmp_path):
    archive = tmp_path / "package.whl"
    with ZipFile(archive, "w") as wheel:
        wheel.writestr("dist-info/LICENSE", "license\n")

    assert notices.extract_zip_named(archive, "dist-info/LICENSE") == b"license\n"
    with pytest.raises(notices.CollectionError, match="missing"):
        notices.extract_zip_named(archive, "dist-info/NOTICE")


def test_collected_notice_is_readable_by_container_runtime_user(tmp_path):
    source = tmp_path / "upstream-license"
    source.write_text("public license terms")
    source.chmod(0o600)
    destination = tmp_path / "release" / "LICENSE"
    notices.atomic_copy(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_mode & 0o444 == 0o444
