from __future__ import annotations

import importlib.util
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_release_sources", ROOT / "scripts/collect-release-sources.py"
)
assert SPEC and SPEC.loader
sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sources)


def test_control_parser_retains_multiline_source_checksums():
    raw = (
        "Package: example\nVersion: 1\nChecksums-Sha256: abc 12 example.dsc\n"
        " def 34 example.tar.xz\n\n"
    )

    record = sources.parse_control_records(raw)[0]

    assert record["Package"] == "example"
    assert "def 34 example.tar.xz" in record["Checksums-Sha256"]
    assert sources.checksum_entries(record) == [
        {"sha256": "abc", "size": "12", "filename": "example.dsc"},
        {"sha256": "def", "size": "34", "filename": "example.tar.xz"},
    ]


def test_source_field_preserves_explicit_source_version():
    binary = {"Package": "libexample1", "Version": "2:1.2-3", "Source": "example (1.2-3)"}
    assert sources.source_from_binary_field(binary) == ("example", "1.2-3")


def test_source_field_defaults_to_binary_version():
    binary = {"Package": "example", "Version": "1.2-3"}
    assert sources.source_from_binary_field(binary) == ("example", "1.2-3")


def test_validate_archive_reads_real_tar_input(tmp_path):
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        member = tarfile.TarInfo("example-1.0/COPYING")
        content = b"license\n"
        member.size = len(content)
        output.addfile(member, __import__("io").BytesIO(content))

    assert sources.validate_archive(archive) == "example-1.0/COPYING"


def test_validate_archive_rejects_corrupt_archive(tmp_path):
    archive = tmp_path / "broken.tar.gz"
    archive.write_bytes(b"not a tar archive")

    with pytest.raises(sources.CollectionError, match="invalid source archive"):
        sources.validate_archive(archive)


def test_source_index_filename_matches_official_layout():
    assert sources.index_filename("noble-updates", "main", "binary") == (
        "noble-updates-main-binary-amd64-Packages.gz"
    )
    assert sources.index_filename("noble-updates", "main", "source") == (
        "noble-updates-main-source-Sources.gz"
    )


def test_launchpad_fallback_extracts_file_hashes_and_aliases():
    page = """
    <tr><td><a href="https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/
    util-linux/2.39.3-9ubuntu6.2/util-linux_2.39.3.dsc">file</a></td>
    <td>abc</td><td>0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef</td></tr>
    """

    files = sources.parse_launchpad_files(page)

    assert files[0]["filename"] == "util-linux_2.39.3.dsc"
    assert files[0]["sha256"] == (
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    assert sources.launchpad_source_alias("libuuid1") == "util-linux"
