#!/bin/sh
# Runtime smoke test for a built image: proves ffmpeg/ffprobe work in the
# container (a successful build does not) and that the server answers /healthz.
set -eu

image="${1:?usage: container-smoke.sh IMAGE}"

docker run --rm --entrypoint python "$image" -c '
import tempfile
import wave
from pathlib import Path

from asr_studio.media import normalize_media
from torchcodec.decoders import AudioDecoder

with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "in.wav"
    target = Path(directory) / "out.m4a"
    with wave.open(str(source), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000)
    result = normalize_media(source, target, max_duration_seconds=60)
    assert result.duration_seconds > 0 and target.stat().st_size > 0
    decoded = AudioDecoder(target).get_all_samples()
    assert decoded.data.numel() > 0
print("torchcodec decode ok")
print("media ok")
'

# The app rejects Host headers that differ from its public URL, so keep them equal.
port="${ASR_SMOKE_PORT:-8765}"
container="$(docker run -d -p "127.0.0.1:${port}:8765" \
    -e "ASR_PUBLIC_URL=http://127.0.0.1:${port}" "$image")"
trap 'docker rm -f "$container" >/dev/null' EXIT
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then
        echo "healthz ok"
        exit 0
    fi
    sleep 1
done
docker logs "$container" >&2
echo "container did not become healthy" >&2
exit 1
