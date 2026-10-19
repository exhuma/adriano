# syntax=docker/dockerfile:1
#
# Multi-stage build for the adriano backend (FastAPI + uv).
#
# Stage 1 builds the virtualenv and installs the project with uv;
# stage 2 copies only the built venv and application code into a
# slim runtime image and runs as a non-root user (module-twelve-factor
# "build, release, run", "disposability").
#
# HEALTHCHECK: the stack kit's deployment guidance treats healthcheck
# stanzas as opt-in, added only by a dedicated observability kit. This
# project's SPEC.md acceptance criterion 27 ("container health checks
# ... are documented") requires one, so this is a deliberate,
# documented deviation from that default -- see docs/operator.md
# "Health checks".

FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (separate layer, cached while only
# application code changes).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then install the project itself into the same venv.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime

# Non-root application user (module-twelve-factor "processes":
# stateless, share-nothing; no reason to run as root).
RUN groupadd --system --gid 10001 adriano \
    && useradd --system --uid 10001 --gid adriano --no-create-home adriano

WORKDIR /app

COPY --from=build --chown=adriano:adriano /app/.venv /app/.venv
COPY --from=build --chown=adriano:adriano /app/app /app/app
COPY --from=build --chown=adriano:adriano /app/alembic /app/alembic
COPY --from=build --chown=adriano:adriano /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
# The legacy application ran 5 Uvicorn workers in its container
# entrypoint (see SPEC.md "Legacy application behavior"); this image
# defaults to 4 and makes the worker count configurable -- documented
# in docs/operator.md.
ENV ADRIANO_WORKERS=4

USER adriano

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

# CMD only (no ENTRYPOINT): `docker compose run --rm backend adriano poll`
# and similar admin-process invocations (module-twelve-factor "admin
# processes") replace this whole command instead of being swallowed by
# a fixed entrypoint shell.
CMD ["/bin/sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers \"${ADRIANO_WORKERS:-4}\""]
