#!/bin/sh

set -eu

uv sync --all-groups --locked
uv run --no-sync ruff check src tests
uv run --no-sync ruff format --check src tests
uv run --no-sync pytest

find src/asr_en_vi/web -type f -name '*.js' -print | while IFS= read -r javascript_file; do
    node --check "$javascript_file"
done

docker compose config --quiet
