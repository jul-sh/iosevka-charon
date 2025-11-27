#!/usr/bin/env bash
#
# Run a command inside the Nix + uv development environment with a Docker fallback.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${ROOT_DIR}"

if [ -n "${IN_NIX_SHELL:-}" ]; then
  echo "Already inside a Nix shell. Continuing execution..."
  exec "$@"
fi

if command -v nix >/dev/null 2>&1; then
  echo "Nix is available, entering nix shell..."
  exec nix develop --experimental-features 'nix-command flakes' "$ROOT_DIR/sources#default" --command "$ROOT_DIR/scripts/run-in-nix.sh" "$@"
else
  echo "Nix is not available. Attempting to use Docker with Nix image."
  if command -v docker >/dev/null 2>&1; then
    echo "Docker is available, running script inside a Nix container."
    exec docker run --rm -v "$ROOT_DIR:/app" -w /app nixos/nix \
      nix develop --experimental-features 'nix-command flakes' ./sources#default --command /app/scripts/run-in-nix.sh "$@"
  else
    echo "Docker is not available. Please install either Nix or Docker to proceed."
    exit 1
  fi
fi
