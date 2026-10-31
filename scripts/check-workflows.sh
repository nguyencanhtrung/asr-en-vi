#!/bin/sh
set -eu

if ! command -v actionlint >/dev/null 2>&1; then
    echo 'actionlint is required. Install v1.7.11; see docs/agents/development.md.' >&2
    exit 1
fi

# The pinned copy from the uv dev group keeps the host shellcheck out of the gate.
shellcheck="$(cd "${0%/*}/.." && pwd)/.venv/bin/shellcheck"
if [ ! -x "$shellcheck" ]; then
    echo 'shellcheck is required. Run uv sync --all-groups --locked.' >&2
    exit 1
fi
exec actionlint -shellcheck="$shellcheck" -pyflakes= "$@"
