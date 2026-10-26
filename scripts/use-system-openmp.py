#!/usr/bin/env python3
"""Replace wheel-bundled GNU runtimes with corresponding Ubuntu runtime packages."""

import hashlib
import json
import shutil
import subprocess
import sysconfig
from pathlib import Path

RUNTIMES = (
    ("libgomp*.so*", "libgomp.so.1.0.0", "libgomp1"),
    ("libgfortran*.so*", "libgfortran.so.5.0.0", "libgfortran5"),
    ("libquadmath*.so*", "libquadmath.so.0.0.0", "libquadmath0"),
)


def exports(path: Path) -> set[str]:
    output = subprocess.check_output(["readelf", "--dyn-syms", "--wide", str(path)], text=True)
    result = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[6] not in {"UND", "ABS"} and fields[4] in {"GLOBAL", "WEAK"}:
            result.add(fields[-1].replace("@@", "@"))
    return result


def replace_runtime(system_root: Path, package_root: Path, output: Path) -> dict:
    replacements = []
    for pattern, filename, package in RUNTIMES:
        bundled = sorted(package_root.rglob(pattern))
        if not bundled:
            continue
        system = list(system_root.glob("*/" + filename))
        if len(system) != 1:
            raise RuntimeError(f"Expected exactly one installed system runtime: {filename}")
        source = system[0]
        supported = exports(source)
        for target in bundled:
            missing = exports(target) - supported
            if missing:
                raise RuntimeError(f"System runtime lacks required symbols: {sorted(missing)}")
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            shutil.copyfile(source, target)
            replacements.append(
                {
                    "path": str(target.relative_to(package_root)),
                    "source": str(source),
                    "package": package,
                    "original_sha256": before,
                    "replacement_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            )
    record = {"replacements": replacements}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    replace_runtime(
        Path("/usr/lib"), Path(sysconfig.get_paths()["purelib"]), Path("/app/openmp-runtime.json")
    )
