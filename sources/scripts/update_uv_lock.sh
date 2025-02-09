#!/usr/bin/env bash

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

readonly REPO_ROOT="$(git rev-parse --show-toplevel)"
readonly REQUIREMENTS="$REPO_ROOT/sources/requirements.txt"
readonly UV_LOCKFILE="$REPO_ROOT/sources/requirements.lock"

# Generate new lockfile from requirements.txt
uv pip compile "$REQUIREMENTS" --output-file "$UV_LOCKFILE" --prerelease=allow

echo "Updated $UV_LOCKFILE from $REQUIREMENTS"
