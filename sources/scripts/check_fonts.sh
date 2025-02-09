#!/usr/bin/env bash

set -e

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

# Set default font directory if not provided
FONT_DIR=${1:-"sources/output"}

# Ensure font directory exists and contains TTF files
if [ ! -d "$FONT_DIR" ]; then
    echo "ERROR: $FONT_DIR directory does not exist"
    exit 1
fi

# Find all TTF files recursively
TTF_FILES=$(find "$FONT_DIR" -type f -name "*.ttf")
if [ -z "$TTF_FILES" ]; then
    echo "ERROR: No TTF files found in $FONT_DIR directory or subdirectories"
    exit 1
fi

# Run Fontbakery checks on fonts, disabling the mono-bad-panose check.

# Disable opentype/monospace because it incorrectly flags our quasi-proportional font as monospaced.
# This is due to a majority of glyphs sharing a common width, even though the font is not intended to be monospaced.
# See https://github.com/fonttools/fontbakery/blob/ffe83a2824631ddbabdbf69c47b8128647de30d1/Lib/fontbakery/checks/conditions.py#L50
fontbakery check-googlefonts \
    -C --succinct --loglevel FAIL \
    --exclude-checkid opentype/monospace \
    --ghmarkdown "$FONT_DIR/report.md" \
    $TTF_FILES || true
