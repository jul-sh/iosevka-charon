#!/usr/bin/env bash
#
# Main entry point for building Iosevka fonts.
# This script initializes the environment and runs the build process.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

# Accept build plan file as optional argument (defaults to private-build-plans.toml)
BUILD_PLAN="${1:-sources/private-build-plans.toml}"

echo "Starting Iosevka font build process..."
echo "Using build plan: $BUILD_PLAN"

# Ensure submodules are available
git submodule update --init --recursive

# Run the build script to generate TTFs
python3 sources/scripts/build_fonts.py "$BUILD_PLAN"

echo "Post-processing fonts for GF compliance…"
python3 sources/scripts/post_process_parallel.py

echo "Syncing fonts into fonts/ttf/…"
rm -rf fonts
mkdir -p fonts/ttf
found=0
while IFS= read -r -d '' font; do
  plan_dir="$(basename "$(dirname "$(dirname "$font")")")"
  # Convert directory name to lowercase and remove spaces for Google Fonts compliance
  dest_dir_name="$(echo "$plan_dir" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
  dest_dir="fonts/ttf/$dest_dir_name"
  mkdir -p "$dest_dir"

  # Normalize filename for Google Fonts compliance
  # ExtraBold -> Extrabold, ExtraLight -> Extralight, SemiBold -> Semibold
  filename="$(basename "$font")"
  filename="${filename//ExtraBold/Extrabold}"
  filename="${filename//ExtraLight/Extralight}"
  filename="${filename//SemiBold/Semibold}"

  cp "$font" "$dest_dir/$filename"
  found=1
done < <(find sources/output -type f -name "*.ttf" -print0)

if [ "$found" -eq 0 ]; then
  echo "ERROR: No TTF files were produced under sources/output."
  exit 1
fi

echo "Build complete! Font files are available in fonts/ttf/"
