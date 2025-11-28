#!/usr/bin/env bash
#
# Main entry point for building Iosevka fonts.
# This script initializes the environment and runs the build process.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

CACHE_SCRIPT="sources/scripts/cache_branch.py"
SOURCE_HASH=$(python3 "$CACHE_SCRIPT" hash)
echo "Source tree hash: $SOURCE_HASH"

if python3 "$CACHE_SCRIPT" restore --stage post --hash "$SOURCE_HASH"; then
  echo "Post-processed fonts restored from cache."
  exit 0
fi

# Source the Nix environment
source sources/scripts/setup_shell.sh

if python3 "$CACHE_SCRIPT" restore --stage initial --hash "$SOURCE_HASH"; then
  echo "Initial build artifacts restored from cache; skipping npm build."
else
  echo "Starting Iosevka font build process..."

  # Ensure submodules are available
  git submodule update --init --recursive

  # Run the build script to generate TTFs
  python3 sources/scripts/build_fonts.py

  python3 "$CACHE_SCRIPT" store --stage initial --hash "$SOURCE_HASH" --paths sources/output
fi

echo "Post-processing fonts for GF compliance…"
python3 - <<'PY'
import pathlib
import sys

sys.path.append("sources/scripts")
import fix_fonts

root = pathlib.Path("sources/output")
fonts = sorted(root.glob("**/*.ttf"))
if not fonts:
    raise SystemExit("No TTF files found in sources/output to post-process.")

for font_path in fonts:
    fix_fonts.post_process_font(font_path)
PY

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

python3 "$CACHE_SCRIPT" store --stage post --hash "$SOURCE_HASH" --paths sources/output fonts/ttf

echo "Build complete! Font files are available in fonts/ttf/"
