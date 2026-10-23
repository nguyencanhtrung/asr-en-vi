from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-acceptance-criteria.py"
spec = importlib.util.spec_from_file_location("check_acceptance_criteria", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_only_unexplained_unticked_criteria_block() -> None:
    body = """## What to build

- [ ] Not a criterion.

## Acceptance criteria

- [x] Done.
- [ ] Missing.
- [ ] Deferred — Not done: needs NVIDIA host, follow-up #99.
* [ ] Also missing.

## Blocked by

- [ ] Ignored.
"""
    assert module.unresolved_criteria(body) == ["Missing.", "Also missing."]


def test_issue_without_criteria_passes() -> None:
    assert module.unresolved_criteria("No checklist here.") == []
