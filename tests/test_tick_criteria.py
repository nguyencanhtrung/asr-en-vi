from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "tick-criteria.py"
spec = importlib.util.spec_from_file_location("tick_criteria", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CHECKER = Path(__file__).parents[1] / "scripts" / "check-acceptance-criteria.py"
checker_spec = importlib.util.spec_from_file_location("check_acceptance_criteria", CHECKER)
assert checker_spec and checker_spec.loader
checker = importlib.util.module_from_spec(checker_spec)
checker_spec.loader.exec_module(checker)

BODY = """## What to build

- [ ] Not a criterion.

## Acceptance criteria

- [x] Done.
- [ ] First.
- [ ] Second.

## Blocked by

- [ ] Ignored.
"""


def test_each_open_criterion_needs_a_decision() -> None:
    with pytest.raises(ValueError, match=r"still open.*\[3\]"):
        module.resolve(BODY, {2}, {})
    with pytest.raises(ValueError, match="both"):
        module.resolve(BODY, {2, 3}, {3: "x"})
    with pytest.raises(ValueError, match="no criterion"):
        module.resolve(BODY, {2, 3, 4}, {})


def test_resolved_body_passes_the_merge_gate_and_leaves_other_sections() -> None:
    updated = module.resolve(BODY, {2}, {3: "needs NVIDIA host, #99"})
    assert "- [x] First." in updated
    assert "- [ ] Second. — Not done: needs NVIDIA host, #99" in updated
    assert "- [ ] Not a criterion." in updated and "- [ ] Ignored." in updated
    assert checker.unresolved_criteria(updated) == []
