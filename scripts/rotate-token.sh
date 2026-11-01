#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$script_dir"

exec docker compose exec -T app python -m asr_studio.cli access rotate
