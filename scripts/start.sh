#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$script_dir"

compose_build() {
    docker compose -f compose.yaml "$@"
}

gpu_compose_file=""
compose_runtime() {
    if [ -n "$gpu_compose_file" ]; then
        docker compose -f compose.yaml -f "$gpu_compose_file" "$@"
    else
        docker compose -f compose.yaml "$@"
    fi
}

compose_build build
requested_device=$(compose_build config --environment | sed -n 's/^ASR_DEVICE=//p')
requested_device=${requested_device:-auto}
if [ "$requested_device" = "cpu" ]; then
    echo "CPU backend requested; selecting whisper-small."
elif docker run --rm --gpus all --entrypoint python asr-en-vi:local -c \
    'import ctranslate2; raise SystemExit(0 if ctranslate2.get_cuda_device_count() else 1)' \
    >/dev/null 2>&1; then
    gpu_compose_file="compose.gpu.yaml"
    echo "Detected NVIDIA GPU; selecting CUDA and whisper-large-v3."
elif [ "$requested_device" = "cuda" ] || \
    { command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; }; then
    echo "NVIDIA GPU requested or detected, but Docker cannot expose it." >&2
    echo "Check the NVIDIA driver and NVIDIA Container Toolkit." >&2
    exit 1
else
    echo "No NVIDIA GPU detected; selecting CPU and whisper-small."
fi

model_host_path=$(compose_build config --environment | sed -n 's/^ASR_MODEL_HOST_PATH=//p')
model_host_path=${model_host_path:-./models}
mkdir -p "$model_host_path"
model_host_path=$(CDPATH= cd -- "$model_host_path" && pwd)

compose_runtime run --rm --no-deps --user "$(id -u):$(id -g)" \
    -e HF_HOME=/tmp/huggingface -v "$model_host_path:/models:rw" \
    worker python -m asr_en_vi.cli model prepare
compose_runtime run --rm --no-deps worker python -m asr_en_vi.cli runtime check
compose_runtime up --detach --wait --wait-timeout "${ASR_STARTUP_TIMEOUT:-120}"
compose_runtime exec -T app python -m asr_en_vi.cli access show
