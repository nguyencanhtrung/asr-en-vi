from __future__ import annotations

import importlib.util
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "release_inventory", ROOT / "scripts/release-inventory.py"
)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_inventory_preserves_bundled_notices_and_reports_missing_files(tmp_path):
    metadata = Message()
    metadata["Name"] = "example"
    metadata["License-Expression"] = "MIT"
    license_path = tmp_path / "LICENSE"
    license_path.write_text("upstream license")
    distribution = SimpleNamespace(
        metadata=metadata,
        version="1.0",
        files=[Path("LICENSE"), Path("NOTICE-missing"), Path("module.py")],
        locate_file=lambda relative: tmp_path / relative,
    )
    record = inventory.distribution_record(distribution)
    assert record["license_expression"] == "MIT"
    assert record["notices"] == [inventory.file_record(license_path, "LICENSE")]
    assert record["missing_notice_files"] == ["NOTICE-missing"]
    assert record["redistribution_review"] == "pending"


def test_inventory_does_not_infer_license_from_presence_of_notice(tmp_path):
    metadata = Message()
    metadata["Name"] = "unknown"
    (tmp_path / "LICENSE").write_text("Terms require review")
    distribution = SimpleNamespace(
        metadata=metadata,
        version="1",
        files=[Path("LICENSE")],
        locate_file=lambda relative: tmp_path / relative,
    )
    assert inventory.distribution_record(distribution)["needs_license_identification"]
    metadata["License"] = "UNKNOWN"
    assert inventory.distribution_record(distribution)["needs_license_identification"]


def test_system_inventory_includes_held_installed_packages(monkeypatch):
    monkeypatch.setattr(inventory.shutil, "which", lambda name: "/usr/bin/dpkg-query")
    monkeypatch.setattr(
        inventory.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                "example-installed\t1\tamd64\tinstall ok installed\n"
                "example-held\t2\tamd64\thold ok installed\n"
                "example-removed\t3\tamd64\tdeinstall ok config-files\n"
            )
        ),
    )
    packages = inventory.system_packages()
    assert [package["name"] for package in packages] == ["example-held", "example-installed"]
    assert packages[0]["dpkg_status"] == "hold ok installed"
