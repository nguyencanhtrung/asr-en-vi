#!/usr/bin/env python3
"""Resolve an issue's acceptance criteria one by one before a merge.

Every unticked criterion must be named, either ticked or explained, so no blanket
tick can satisfy the "Check linked issue criteria" gate:

    scripts/tick-criteria.py 132 --list
    scripts/tick-criteria.py 132 --tick 1 2 4 --not-done 3 "needs NVIDIA host, #99"
"""

from __future__ import annotations

import argparse
import re
import subprocess

HEADING = re.compile(r"^#{1,6}\s+acceptance criteria\s*$", re.IGNORECASE)
CRITERION = re.compile(r"^(\s*[-*+]\s+)\[( |x|X)\](\s+)(.*)$")


def criteria(body: str) -> list[tuple[int, bool, str]]:
    """Return (line index, ticked, text) for each checkbox in the criteria section."""
    found = []
    in_section = False
    for index, line in enumerate(body.splitlines()):
        if line.startswith("#"):
            in_section = bool(HEADING.match(line.strip()))
            continue
        match = CRITERION.match(line) if in_section else None
        if match:
            found.append((index, match.group(2) != " ", match.group(4)))
    return found


def resolve(body: str, tick: set[int], not_done: dict[int, str]) -> str:
    """Apply 1-based tick and not-done decisions; every open criterion needs one."""
    items = criteria(body)
    if tick & not_done.keys():
        raise ValueError(f"criteria both ticked and not done: {sorted(tick & not_done.keys())}")
    unknown = sorted(n for n in tick | not_done.keys() if not 1 <= n <= len(items))
    if unknown:
        raise ValueError(f"no criterion numbered {unknown}; the issue has {len(items)}")
    open_items = [
        n
        for n, (_, ticked, text) in enumerate(items, 1)
        if not ticked and "not done:" not in text.lower()
    ]
    missing = [n for n in open_items if n not in tick and n not in not_done]
    if missing:
        raise ValueError(f"criteria still open, tick or explain each: {missing}")
    lines = body.splitlines(keepends=True)
    for number, (index, _, _) in enumerate(items, 1):
        prefix, _, space, text = CRITERION.match(lines[index].rstrip("\r\n")).groups()
        ending = lines[index][len(lines[index].rstrip("\r\n")) :]
        if number in tick:
            lines[index] = f"{prefix}[x]{space}{text}{ending}"
        elif number in not_done:
            lines[index] = f"{prefix}[ ]{space}{text} — Not done: {not_done[number]}{ending}"
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("issue", type=int)
    parser.add_argument("--list", action="store_true", help="print numbered criteria and exit")
    parser.add_argument("--tick", type=int, nargs="*", default=[], metavar="N")
    parser.add_argument("--not-done", nargs=2, action="append", default=[], metavar=("N", "REASON"))
    args = parser.parse_args()
    body = subprocess.run(
        ["gh", "issue", "view", str(args.issue), "--json", "body", "--jq", ".body"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if args.list:
        for number, (_, ticked, text) in enumerate(criteria(body), 1):
            print(f"{number}. [{'x' if ticked else ' '}] {text}")
        return 0
    try:
        updated = resolve(body, set(args.tick), {int(n): reason for n, reason in args.not_done})
    except ValueError as error:
        parser.error(str(error))
    subprocess.run(
        ["gh", "issue", "edit", str(args.issue), "--body-file", "-"],
        input=updated,
        check=True,
        text=True,
    )
    print(f"Issue #{args.issue}: criteria resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
