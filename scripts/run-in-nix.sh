#!/usr/bin/env bash
#
# Run a command inside the Nix + uv development environment.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${ROOT_DIR}"

if [ -n "${IN_NIX_SHELL:-}" ]; then
  exec "$@"
fi

exec nix develop --experimental-features 'nix-command flakes' "$ROOT_DIR/sources#default" \
  --command bash "$0" "$@"
