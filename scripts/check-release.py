#!/usr/bin/env python3
"""Check that release tags and application metadata identify the same version."""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).parents[1]


def _source_version(path: Path) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            )
        ):
            return statement.value.value
    raise ValueError(f"{path} does not define a string __version__")


def check_release_metadata(
    pyproject_path: Path = ROOT / "pyproject.toml",
    source_path: Path = ROOT / "src" / "asr_studio" / "__init__.py",
    lock_path: Path = ROOT / "uv.lock",
    tag: str | None = None,
) -> dict[str, str]:
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_version = project["project"]["version"]
    source_version = _source_version(source_path)
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    app_packages = [package for package in lock["package"] if package["name"] == "asr-studio"]
    if len(app_packages) != 1:
        raise ValueError("uv.lock must contain exactly one asr-studio package entry")
    lock_version = app_packages[0]["version"]

    try:
        normalized_project = Version(project_version)
        normalized_source = Version(source_version)
        normalized_lock = Version(lock_version)
    except InvalidVersion as error:
        raise ValueError(f"Invalid application version: {error}") from None

    if normalized_project != normalized_source:
        raise ValueError(
            f"pyproject version {project_version!r} does not match "
            f"source version {source_version!r}"
        )
    if normalized_project != normalized_lock:
        raise ValueError(
            f"pyproject version {project_version!r} does not match uv.lock version {lock_version!r}"
        )

    if tag is not None:
        canonical_tag = f"v{source_version}"
        if tag != canonical_tag:
            raise ValueError(
                f"release tag {tag!r} must exactly match canonical tag {canonical_tag!r}"
            )
        try:
            normalized_tag = Version(tag[1:])
        except InvalidVersion as error:
            raise ValueError(f"Invalid release tag {tag!r}: {error}") from None
        if normalized_project != normalized_tag:
            raise ValueError(
                f"release tag {tag!r} does not match application version {project_version!r}"
            )

    return {
        "version": source_version,
        "normalized_version": str(normalized_project),
        "lock_version": lock_version,
        "tag": tag or "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", nargs="?", help="release tag, such as v0.1.0-rc.1")
    arguments = parser.parse_args(argv)
    try:
        result = check_release_metadata(tag=arguments.tag)
    except (KeyError, OSError, SyntaxError, ValueError) as error:
        print(f"Release version check failed: {error}", file=sys.stderr)
        return 1
    print(
        "Release version check passed: "
        f"source={result['version']} lock={result['lock_version']}"
        + (f" tag={result['tag']}" if result["tag"] else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
