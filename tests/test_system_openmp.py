import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "system_openmp", ROOT / "scripts/use-system-openmp.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "filename,bundled_name",
    [
        ("libgomp.so.1.0.0", "libgomp-vendor.so.1.0.0"),
        ("libgfortran.so.5.0.0", "libgfortran-vendor.so.5.0.0"),
        ("libquadmath.so.0.0.0", "libquadmath-vendor.so.0.0.0"),
    ],
)
def test_replacement_preserves_filename_and_records_hashes(
    tmp_path, monkeypatch, filename, bundled_name
):
    system = tmp_path / "usr/lib/architecture" / filename
    system.parent.mkdir(parents=True)
    system.write_bytes(b"system package binary")
    root = tmp_path / "site-packages"
    target = root / "nested.libs" / bundled_name
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unidentified vendor binary")
    monkeypatch.setattr(module, "exports", lambda path: {"symbol@VERSION_1"})
    record = module.replace_runtime(system.parent.parent, root, tmp_path / "record.json")
    assert target.read_bytes() == system.read_bytes()
    item = record["replacements"][0]
    assert item["source"] == str(system)
    assert item["original_sha256"] != item["replacement_sha256"]


def test_missing_required_system_library_fails_closed(tmp_path):
    (tmp_path / "libgomp-vendor.so.1").write_bytes(b"bundled")
    with pytest.raises(RuntimeError, match="exactly one"):
        module.replace_runtime(tmp_path / "missing", tmp_path, tmp_path / "record.json")


def test_missing_export_rejects_replacement_without_changing_binary(tmp_path, monkeypatch):
    system = tmp_path / "system/arch/libgomp.so.1.0.0"
    system.parent.mkdir(parents=True)
    system.write_bytes(b"system")
    root = tmp_path / "packages"
    root.mkdir()
    bundled = root / "libgomp-vendor.so.1"
    bundled.write_bytes(b"original")
    monkeypatch.setattr(
        module, "exports", lambda p: {"new@VERSION_2"} if p == bundled else {"old@VERSION_1"}
    )
    with pytest.raises(RuntimeError, match="lacks required symbols"):
        module.replace_runtime(system.parent.parent, root, tmp_path / "record.json")
    assert bundled.read_bytes() == b"original"
