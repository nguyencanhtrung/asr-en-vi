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

compose_environment=$(compose_build config --environment)
model_host_path=$(printf '%s\n' "$compose_environment" | sed -n 's/^ASR_MODEL_HOST_PATH=//p')
model_host_path=${model_host_path:-./models}
mkdir -p "$model_host_path"
model_host_path=$(CDPATH= cd -- "$model_host_path" && pwd)
diarization_container_path=$(printf '%s\n' "$compose_environment" | sed -n 's/^ASR_DIARIZATION_MODEL_PATH=//p')
diarization_container_path=${diarization_container_path:-/models/speaker-diarization-community-1}
case "$diarization_container_path" in
    /models/*)
        diarization_relative_path=${diarization_container_path#/models/}
        ;;
    *)
        echo "ASR_DIARIZATION_MODEL_PATH must be below /models inside the container." >&2
        exit 1
        ;;
esac
case "$diarization_relative_path" in
    ""|..|../*|*/..|*/../*)
        echo "ASR_DIARIZATION_MODEL_PATH must not escape /models." >&2
        exit 1
        ;;
esac
diarization_model_path="$model_host_path/$diarization_relative_path"
for required_model_file in \
    config.yaml \
    embedding/pytorch_model.bin \
    plda/plda.npz \
    plda/xvec_transform.npz \
    segmentation/pytorch_model.bin
do
    if [ ! -f "$diarization_model_path/$required_model_file" ]; then
        echo "Community-1 is incomplete at: $diarization_model_path" >&2
        echo "Missing required file: $required_model_file" >&2
        echo "Accept the model terms, authenticate on the host, and download it before starting." >&2
        echo "See the 'Model speaker diarization local' section in README.md." >&2
        exit 1
    fi
done

compose_runtime run --rm --no-deps --user "$(id -u):$(id -g)" \
    -e HF_HOME=/tmp/huggingface -v "$model_host_path:/models:rw" \
    worker python -m asr_en_vi.cli model prepare
compose_runtime run --rm --no-deps worker python -m asr_en_vi.cli runtime check
compose_runtime up --detach --wait --wait-timeout "${ASR_STARTUP_TIMEOUT:-120}"
compose_runtime exec -T app python -m asr_en_vi.cli access show
