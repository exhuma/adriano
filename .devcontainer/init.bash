#!/usr/bin/env bash
# Post-create setup for the adriano devcontainer: installs uv and
# go-task if missing, then syncs the backend (and the frontend, once
# phase 01's Task 2 has scaffolded it).
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v task >/dev/null 2>&1; then
  echo "Installing go-task..."
  sh -c "$(curl -LsSf https://taskfile.dev/install.sh)" -- -d -b \
    "$HOME/.local/bin"
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Syncing backend dependencies (uv sync)..."
(cd backend && uv sync)

if [ -f frontend/package.json ]; then
  echo "Installing frontend dependencies (npm ci)..."
  (cd frontend && npm ci)
else
  echo "frontend/package.json not found; skipping npm ci" \
    "(frontend not scaffolded yet)."
fi

echo "Devcontainer setup complete."
