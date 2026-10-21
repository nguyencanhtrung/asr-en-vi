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

## OMP contract

Run the opt-in real-binary contract test with:

```sh
ASR_RUN_OMP_CONTRACT=1 .venv/bin/python -m pytest -q tests/test_omp_contract.py
```

Run it when changing OMP adapter or RPC code in
`src/asr_en_vi/antigravity.py`, or when bumping `OMP_VERSION` and the OMP
checksums in `Dockerfile`. The contract runs offline and sends no prompt or
inference request.

For OMP v18.5.0, source facts that the contract cannot test are:

- S-1: the auth-broker logout path deletes only local SQLite credentials and
  does not revoke a remote token. Read the tagged
  [`auth-broker-cli.ts` source](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/cli/auth-broker-cli.ts#L277).
- S-2: an RPC `prompt_result` error has `status: "error"` and an `error`
  object with `message` and `retryable`. Provider-run errors also carry
  `provider`, `model`, and optional `httpStatus`; pre-agent rejections carry
  only `message` and `retryable`. Read the tagged
  [`rpc-prompt-results.ts` source](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/modes/rpc/rpc-prompt-results.ts#L108-L110)
  for pre-agent rejections and [provider-run errors](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/modes/rpc/rpc-prompt-results.ts#L181-L199).
- S-3: a Gemini provider error finish reason (`SAFETY`, `MALFORMED_FUNCTION_CALL`, ...)
  sets the assistant error message `Generation failed with finish reason: <REASON>`. A
  stream that ends without any finish reason says `stream ended without a finish reason`.
  Read the tagged
  [error finish reasons](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/ai/src/providers/google-gemini-cli.ts#L866-L879)
  and [missing finish reason](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/ai/src/providers/google-gemini-cli.ts#L1054-L1057).

- S-4: the RPC command `{type: "set_thinking_level", level}` answers
  `{type: "response", command: "set_thinking_level", success: true}`, and `get_state` returns
  `thinkingLevel`. OMP uses level `high` when none is set. Read the tagged
  [RPC command types](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/modes/rpc/rpc-types.ts#L75),
  [response types](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/modes/rpc/rpc-types.ts#L404)
  and [default level](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/coding-agent/src/main.ts#L1013-L1020).

Read the tagged source, not `strings` on the binary.

The CI-equivalent full suite is
`ASR_RUN_BROWSER_TESTS=1 ASR_REQUIRE_MEDIA_TOOLS=1 .venv/bin/python -m pytest -q`;
read-only review runs add `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

## Pull request cleanup

After GitHub reports a PR as merged, run `./scripts/finish-pr.sh <PR_NUMBER>`.
The script verifies remote merge and head-branch cleanup, updates the local base,
and deletes the local source branch only when safe. It does not merge a PR.
