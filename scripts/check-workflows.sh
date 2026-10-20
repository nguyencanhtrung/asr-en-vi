#!/bin/sh
set -eu

if ! command -v actionlint >/dev/null 2>&1; then
    echo 'actionlint is required. Install v1.7.11; see docs/agents/development.md.' >&2
    exit 1
fi

# Keep optional external linters independent of the host's installed packages.
exec actionlint -shellcheck= -pyflakes= "$@"
