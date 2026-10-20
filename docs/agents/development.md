# Development checks

For changes to `.github/workflows/pipeline.yml`, include
`tests/test_delivery_contract.py` in the work scope. Run the contract tests before
handoff so assertions describe the intended workflow behavior:

```sh
uv run --no-sync pytest -q tests/test_delivery_contract.py
./scripts/check-workflows.sh
```

The workflow linter is [actionlint](https://github.com/rhysd/actionlint), pinned to
v1.7.11 in CI. Install that version locally and put it on `PATH`, for example with
a recent Go toolchain:

```sh
go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.11
```

`check-workflows.sh` checks Actions syntax, expressions and matrix references.
Optional shellcheck and pyflakes integrations are disabled so installed host
packages do not change the gate. The repository's shell syntax gate runs
separately. `./scripts/check.sh` and the quality CI job run this workflow check.

## Environment preflight

Before a full test run, use the existing Python environment:

```sh
.venv/bin/python scripts/check-environment.py
```

The bounded child processes check the effective uv cache, loopback sockets and
async `FileResponse` I/O. JSON output distinguishes a test-environment blocker
from a passing preflight. A deadline failure does not establish a code regression.
Record the failing probe, command and result in the task handoff. Check its cause
before retrying the suite; permission changes require the normal authorization.

If the default uv cache is read-only, select a writable cache explicitly:

```sh
UV_CACHE_DIR=/tmp/asr-uv-cache .venv/bin/python scripts/check-environment.py
```

`check.sh` checks cache access before dependency synchronization and the remaining
probes before pytest. Probes are isolated from application state and live models;
they do not change sandbox permissions or application configuration.

## Pull request cleanup

After GitHub reports a PR as merged, run `./scripts/finish-pr.sh <PR_NUMBER>`.
The script verifies remote merge and head-branch cleanup, updates the local base,
and deletes the local source branch only when safe. It does not merge a PR.
