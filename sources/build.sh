#!/usr/bin/env bash
#
# Main entry point for building Iosevka fonts.
# This script initializes the environment and runs the build process.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

echo "Starting Iosevka font build process..."

# Run the build script to generate TTFs
python3 sources/scripts/build_fonts.py

echo "Build complete! Font files are available in sources/output/"
