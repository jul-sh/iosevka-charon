#!/usr/bin/env bash
#
# Sets up the Nix environment for consistency across systems.
# This script handles different execution contexts (direct or Docker fallback).

set -euo pipefail

# If we're already inside a Nix shell, continue execution
if [ -n "${IN_NIX_SHELL:-}" ]; then
  echo "Already inside a Nix shell. Continuing execution..."
  return 0 2>/dev/null || true
fi

# Command to re-run the script inside a Nix shell
readonly NIX_COMMAND="nix develop --experimental-features 'nix-command flakes' ./sources#default --command bash \"${0:-}\" \"${@:-}\""

if command -v nix >/dev/null 2>&1; then
  echo "Nix is available, entering nix shell..."
  exec bash -c "$NIX_COMMAND"
fi

echo "Nix is not available. Please install Nix to continue." >&2
exit 1
