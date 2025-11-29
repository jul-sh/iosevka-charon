#!/usr/bin/env bash
#
# Quick build script for fast iteration - builds only IosevkaCharon Regular
# Usage: bash sources/scripts/quick_build.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

echo "Quick build: IosevkaCharon Regular only..."

# Run the build for just Regular weight
uv run sources/scripts/quick_build_fonts.py
