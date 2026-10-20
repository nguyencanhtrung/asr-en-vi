#!/bin/sh

set -eu

./scripts/check-shell-syntax.sh
./scripts/check-workflows.sh
python3 scripts/check-environment.py --cache-only

uv sync --all-groups --locked
uv run --no-sync python scripts/check-environment.py
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync pytest

find src/asr_en_vi/web -type f -name '*.js' -print | while IFS= read -r javascript_file; do
    node --check "$javascript_file"
done

docker compose config --quiet
