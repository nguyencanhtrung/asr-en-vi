#!/bin/sh

set -eu

scripts_root=${1:-scripts}
find "$scripts_root" -type f -name '*.sh' -exec sh -c '
    for script_path do
        sh -n "$script_path" || exit 1
    done
' sh {} +
