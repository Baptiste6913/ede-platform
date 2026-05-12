# syntax=docker/dockerfile:1.7
# Multi-stage build for EDE platform.
# Base image pinned to python:3.12-slim-bookworm for ARM64 (Oracle Ampere) + AMD64 compat.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ---------- builder ----------
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip wheel \
 && pip install ".[dev]"

# ---------- runtime ----------
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_HOME=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 ede \
 && useradd --system --uid 1001 --gid 1001 --home ${APP_HOME} --shell /usr/sbin/nologin ede

WORKDIR ${APP_HOME}

COPY --from=builder /opt/venv /opt/venv
COPY --chown=ede:ede src ./src
COPY --chown=ede:ede alembic ./alembic
COPY --chown=ede:ede pyproject.toml ./

USER ede

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
