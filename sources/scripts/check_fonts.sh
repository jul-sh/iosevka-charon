#!/usr/bin/env bash
#
# Runs Fontbakery quality checks on generated TTF files.
# Generates a report in Markdown format.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

# Set default font directory if not provided
readonly FONT_DIR=${1:-"sources/output"}
readonly REPORT_PATH="$FONT_DIR/report.md"
readonly LOG_TIMESTAMP=$(date +'%Y%m%d-%H%M%S')
readonly LOG_PATH="$FONT_DIR/fontbakery-$LOG_TIMESTAMP.log"

# Ensure font directory exists and contains TTF files
if [ ! -d "$FONT_DIR" ]; then
    echo "ERROR: $FONT_DIR directory does not exist"
    exit 1
fi

# Find all TTF files recursively
readonly TTF_FILES=$(find "$FONT_DIR" -type f -name "*.ttf")
if [ -z "$TTF_FILES" ]; then
    echo "ERROR: No TTF files found in $FONT_DIR directory or subdirectories"
    exit 1
fi

# Run Fontbakery checks on fonts
echo "Running Fontbakery checks on fonts in $FONT_DIR..."
{
    echo "Fontbakery log - $(date -Iseconds)"
    echo "Font directory: $FONT_DIR"
    echo
} > "$LOG_PATH"

# Note: We disable opentype/monospace because it incorrectly flags our
# quasi-proportional font as monospaced. This is due to a majority of glyphs
# sharing a common width, even though the font is not intended to be monospaced.
# See: https://github.com/fonttools/fontbakery/blob/ffe83a2824631ddbabdbf69c47b8128647de30d1/Lib/fontbakery/checks/conditions.py#L50
set +e
uv run sources/scripts/fontbakery_wrapper.py check-googlefonts \
    -C --succinct --loglevel FAIL \
    --exclude-checkid opentype/monospace \
    --ghmarkdown "$REPORT_PATH" \
    $TTF_FILES 2>&1 | tee -a "$LOG_PATH"
FONTBAKERY_EXIT=${PIPESTATUS[0]}
set -e

echo >> "$LOG_PATH"
echo "Fontbakery exit code: $FONTBAKERY_EXIT" >> "$LOG_PATH"

echo "Font validation complete. Report saved to $REPORT_PATH"
