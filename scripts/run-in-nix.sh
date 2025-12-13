#!/usr/bin/env bash
#
# Run a command inside the Nix development environment with a Docker fallback.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${ROOT_DIR}"

# Handle standard SHELL interface: -c "command"
if [ "$1" = "-c" ]; then
  shift
  set -- bash -c "$@"
fi

if [ -n "${IN_NIX_SHELL:-}" ]; then
  exec "$@"
fi

if command -v nix >/dev/null 2>&1; then
  exec nix develop --experimental-features 'nix-command flakes' "$ROOT_DIR#default" --command "$ROOT_DIR/scripts/run-in-nix.sh" "$@" 2>/dev/null
else
  echo "Nix is not available. Attempting to use Docker with Nix image."
  if command -v docker >/dev/null 2>&1; then
    echo "Docker is available, running script inside a Nix container."
    exec docker run --rm -v "$ROOT_DIR:/app" -w /app nixos/nix \
      nix develop --experimental-features 'nix-command flakes' .#default --command /app/scripts/run-in-nix.sh "$@"
  else
    echo "Docker is not available. Please install either Nix or Docker to proceed."
    exit 1
  fi
fi
