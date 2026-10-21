# syntax=docker/dockerfile:1
#
# Single standalone image: the FastAPI backend and the built Vue SPA
# in one process (uvicorn serves both on port 8000).
#
# Build context: the repository root.
#   docker build -t adriano --build-arg ADRIANO_VERSION=1.2.3 .
#
# Stages (module-twelve-factor "build, release, run"):
#   1. spa      builds the frontend bundle once; per-environment values
#               are injected at runtime through /config.js, rendered by
#               the backend from ADRIANO_* settings
#               (module-runtime-config-spa). No VITE_* build argument
#               exists on purpose.
#   2. build    builds the backend virtualenv with uv.
#   3. runtime  slim image holding only the venv, the code and the
#               bundle; runs as a non-root user.
#
# HEALTHCHECK: the stack kit's deployment guidance treats healthcheck
# stanzas as opt-in, added only by a dedicated observability kit. This
# project requires documented container health checks, so this is a
# deliberate, documented deviation from that default -- see
# docs/operator/health-and-logging.rst.

# --- Stage 1: frontend bundle ---------------------------------------
FROM node:24-slim AS spa

WORKDIR /frontend

# Dependencies first (cached while only sources change).
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# `npm run build` is `vite build` followed by
# scripts/check-no-dev-auth.sh, which fails the build if any dev-login
# code leaked into dist/. VITE_DEV_AUTH is never set here.
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend virtualenv ------------------------------------
FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (separate layer, cached while only
# application code changes).
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then install the project itself (and its `adriano` console script)
# into the same venv.
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage 3: runtime -----------------------------------------------
FROM python:3.14-slim AS runtime

ARG ADRIANO_VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="adriano" \
      org.opencontainers.image.description="ADR governance catalog: API and web UI in one image" \
      org.opencontainers.image.source="https://github.com/exhuma/adriano" \
      org.opencontainers.image.version="${ADRIANO_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

# Non-root application user (module-twelve-factor "processes":
# stateless, share-nothing; no reason to run as root).
RUN groupadd --system --gid 10001 adriano \
    && useradd --system --uid 10001 --gid adriano --no-create-home adriano

WORKDIR /app

# alembic.ini must stay next to the `app` package: the backend
# locates it relative to the package (see alembic_ini_path()).
COPY --from=build --chown=adriano:adriano /app/.venv /app/.venv
COPY --from=build --chown=adriano:adriano /app/app /app/app
COPY --from=build --chown=adriano:adriano /app/alembic /app/alembic
COPY --from=build --chown=adriano:adriano /app/alembic.ini /app/alembic.ini
COPY --from=spa --chown=adriano:adriano /frontend/dist /app/static

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ADRIANO_STATIC_DIR=/app/static \
    ADRIANO_VERSION=${ADRIANO_VERSION}

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

# CMD only (no ENTRYPOINT): admin processes such as
# `docker run --rm <image> adriano poll` or `adriano migrate` replace
# this whole command instead of being swallowed by a fixed entrypoint
# (module-twelve-factor "admin processes"). `adriano serve` applies
# the migrations under a lock, then execs uvicorn; tune it with
# ADRIANO_WORKERS, ADRIANO_MIGRATE_ON_START and
# ADRIANO_FORWARDED_ALLOW_IPS (docs/operator/configuration.rst).
CMD ["adriano", "serve"]
