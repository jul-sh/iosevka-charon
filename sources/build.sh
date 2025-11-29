#!/usr/bin/env bash
#
# Main entry point for building Iosevka fonts.
# This script initializes the environment and runs the build process.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

echo "Starting Iosevka font build process..."

# Ensure submodules are available
git submodule update --init --recursive

# Run the build script to generate TTFs
python3 sources/scripts/build_fonts.py

echo "Post-processing fonts for GF compliance…"
uv run sources/scripts/post_process_fonts.py

echo "Syncing fonts into fonts/ttf/…"
rm -rf fonts
mkdir -p fonts/ttf
found=0
while IFS= read -r -d '' font; do
  plan_dir="$(basename "$(dirname "$(dirname "$font")")")"
  dest_dir="fonts/ttf/$plan_dir"
  mkdir -p "$dest_dir"
  cp "$font" "$dest_dir/"
  found=1
done < <(find sources/output -type f -name "*.ttf" -print0)

if [ "$found" -eq 0 ]; then
  echo "ERROR: No TTF files were produced under sources/output."
  exit 1
fi

echo "Build complete! Font files are available in fonts/ttf/"
