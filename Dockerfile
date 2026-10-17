FROM ghcr.io/astral-sh/uv:0.13.1 AS uv-bin

FROM nvidia/cuda:13.4.2-cudnn-runtime-ubuntu24.04 AS python-base
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libgomp1 \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

FROM python-base AS builder
COPY --from=uv-bin /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON=/usr/bin/python3
WORKDIR /app
COPY pyproject.toml README.md uv.lock ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable

FROM python-base AS runtime
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ASR_DATA_DIR=/var/lib/asr-en-vi/data \
    ASR_AUTH_DIR=/var/lib/asr-en-vi/auth
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
RUN groupadd --gid 10001 asr \
    && useradd --uid 10001 --gid asr --no-create-home --shell /usr/sbin/nologin asr \
    && mkdir -p /var/lib/asr-en-vi/data /var/lib/asr-en-vi/auth \
    && chown -R 10001:10001 /var/lib/asr-en-vi \
    && chmod 0700 /var/lib/asr-en-vi/data /var/lib/asr-en-vi/auth
USER 10001:10001
CMD ["uvicorn", "asr_en_vi.app:app", "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers", "--no-server-header"]
