FROM ghcr.io/astral-sh/uv:0.13.5 AS uv-bin

FROM nvidia/cuda:13.4.3-cudnn-runtime-ubuntu24.04 AS python-base
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libgomp1 \
        libpython3.12 \
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

FROM python-base AS omp-bin
ARG TARGETARCH=amd64
ARG OMP_VERSION=18.5.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && case "${TARGETARCH}" in \
        amd64) omp_asset=omp-linux-x64; omp_sha=b8413e6e085a423c7a9b1d7bc025c2af794923b6b6c57330a309639b6176c8a1 ;; \
        arm64) omp_asset=omp-linux-arm64; omp_sha=1244860c58bb68a3a45390d4932e5c7983183ec8c12cb6848c1afd709de38a07 ;; \
        *) echo "Unsupported OMP architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --proto '=https' --tlsv1.2 \
        "https://github.com/can1357/oh-my-pi/releases/download/v${OMP_VERSION}/${omp_asset}" \
        --output /usr/local/bin/omp \
    && echo "${omp_sha}  /usr/local/bin/omp" | sha256sum --check --strict \
    && chmod 0755 /usr/local/bin/omp \
    && mkdir -p /usr/local/share/licenses/omp \
    && curl --fail --location --proto '=https' --tlsv1.2 \
        "https://github.com/can1357/oh-my-pi/releases/download/v${OMP_VERSION}/LICENSE" \
        --output /usr/local/share/licenses/omp/LICENSE \
    && curl --fail --location --proto '=https' --tlsv1.2 \
        "https://github.com/can1357/oh-my-pi/releases/download/v${OMP_VERSION}/THIRD-PARTY-NOTICES.txt" \
        --output /usr/local/share/licenses/omp/THIRD-PARTY-NOTICES.txt

FROM python-base AS runtime
ARG VCS_REF=unknown
ENV PATH="/app/.venv/bin:${PATH}" \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/cache \
    DO_NOT_TRACK=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    PYANNOTE_METRICS_ENABLED=0 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ASR_DATA_DIR=/var/lib/asr-en-vi/data \
    ASR_AUTH_DIR=/var/lib/asr-en-vi/auth
LABEL org.opencontainers.image.revision="${VCS_REF}"
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=omp-bin /usr/local/bin/omp /usr/local/bin/omp
COPY --from=omp-bin /usr/local/share/licenses/omp /usr/local/share/licenses/omp
RUN groupadd --gid 10001 asr \
    && useradd --uid 10001 --gid asr --no-create-home --shell /usr/sbin/nologin asr \
    && mkdir -p /var/lib/asr-en-vi/data /var/lib/asr-en-vi/auth /var/lib/asr-en-vi/provider \
    && chown -R 10001:10001 /var/lib/asr-en-vi \
    && chmod 0700 /var/lib/asr-en-vi/data /var/lib/asr-en-vi/auth /var/lib/asr-en-vi/provider
USER 10001:10001
CMD ["uvicorn", "asr_en_vi.app:app", "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers", "--no-server-header", "--no-access-log"]
