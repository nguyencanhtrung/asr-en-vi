#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$script_dir"

docker compose build
docker compose run --rm --no-deps app python -m asr_en_vi.cli model check
docker compose up --detach --wait --wait-timeout "${ASR_STARTUP_TIMEOUT:-120}"
docker compose exec -T app python -m asr_en_vi.cli access show
