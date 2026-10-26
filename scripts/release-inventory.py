#!/usr/bin/env python3
"""Inventory the executing runtime; metadata is evidence, not redistribution approval.

Run inside each final image with no network or user volumes. JSON goes to stdout.
License texts remain in the image; their hashes identify the reviewed copies.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path


def file_record(path: Path, name: str) -> dict[str, str]:
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def distribution_record(distribution) -> dict:
    metadata = distribution.metadata
    notices = []
    missing = []
    for relative in distribution.files or []:
        if not re.search(r"license|licence|copying|copyright|notice", str(relative), re.I):
            continue
        path = Path(distribution.locate_file(relative))
        if path.is_file():
            notices.append(file_record(path, str(relative)))
        else:
            missing.append(str(relative))
    classifiers = [
        value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")
    ]
    expression = metadata.get("License-Expression", "")
    legacy = metadata.get("License", "")
    return {
        "name": metadata["Name"],
        "version": distribution.version,
        "license_expression": expression,
        "license_metadata": legacy,
        "license_classifiers": classifiers,
        "notices": sorted(notices, key=lambda item: item["path"]),
        "missing_notice_files": sorted(missing),
        "needs_license_identification": not (
            expression
            or legacy.strip().upper() not in {"", "UNKNOWN", "UNSPECIFIED"}
            or classifiers
        ),
        "redistribution_review": "pending",
    }


def system_packages() -> list[dict]:
    if not shutil.which("dpkg-query"):
        raise RuntimeError("dpkg-query is required; run inside the Ubuntu runtime image")
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\t${Status}\n"],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    packages = []
    for line in result.stdout.splitlines():
        name, version, architecture, status = line.split("\t", 3)
        if status.split()[-1:] != ["installed"]:
            continue
        copyright_path = Path("/usr/share/doc") / name / "copyright"
        license_fields = []
        if copyright_path.is_file():
            copyright_text = copyright_path.read_text(errors="replace")
            license_fields = sorted(
                set(re.findall(r"^License:[ \t]*(.+)$", copyright_text, flags=re.MULTILINE))
            )
            # Older Debian copyright files are prose, not DEP-5 fields.
            # Conservatively include their source obligations as well.
            if re.search(
                r"GNU (?:Lesser |Library )?General Public License|common-licenses/(?:L?GPL)",
                copyright_text,
                re.I,
            ):
                license_fields.append("GPL/LGPL mentioned in copyright text; review exact terms")
        packages.append(
            {
                "name": name,
                "version": version,
                "architecture": architecture,
                "dpkg_status": status,
                "debian_license_fields": license_fields,
                "copyright": file_record(copyright_path, str(copyright_path))
                if copyright_path.is_file()
                else None,
                "redistribution_review": "pending",
            }
        )
    return sorted(packages, key=lambda item: item["name"])


def main() -> None:
    distributions = sorted(importlib.metadata.distributions(), key=lambda d: d.name.lower())
    omp = Path("/usr/local/bin/omp")
    notices = Path("/usr/local/share/licenses/omp")
    fonts = Path(importlib.metadata.distribution("asr-en-vi").locate_file("asr_en_vi/web/fonts"))
    report = {
        "schema": 1,
        "scope": "Installed runtime only; no models, credentials or user data inspected",
        "redistribution_review": "pending",
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_packages": [distribution_record(d) for d in distributions],
        "system_packages": system_packages(),
        "omp": {
            "binary": file_record(omp, str(omp)),
            "notices": [file_record(p, str(p)) for p in sorted(notices.glob("*")) if p.is_file()],
        },
        "fonts": [
            file_record(p, f"asr_en_vi/web/fonts/{p.name}") for p in sorted(fonts.glob("LICENSE*"))
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
