#!/usr/bin/env bash
#
# Runs Fontbakery quality checks on generated TTF files.
# Generates a report in Markdown format.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

# Set default font directory if not provided
readonly FONT_DIR=${1:-"fonts/ttf"}
readonly REPORT_DIR=${2:-"out/fontbakery"}
readonly REPORT_PATH="$REPORT_DIR/report.md"
readonly LOG_TIMESTAMP=$(date +'%Y%m%d-%H%M%S')
readonly LOG_PATH="$REPORT_DIR/fontbakery-$LOG_TIMESTAMP.log"
mkdir -p "$REPORT_DIR"

# Ensure font directory exists and contains TTF files
if [ ! -d "$FONT_DIR" ]; then
    echo "ERROR: $FONT_DIR directory does not exist"
    exit 1
fi

# Run per-family to avoid cross-family consistency errors
echo "Running Fontbakery checks on fonts in $FONT_DIR..."
echo "Fontbakery log - $(date -Iseconds)" > "$LOG_PATH"

FONTBAKERY_EXIT=0
family_dirs=$(find "$FONT_DIR" -mindepth 1 -maxdepth 1 -type d)
if [ -z "$family_dirs" ]; then
    echo "ERROR: No family directories found under $FONT_DIR" | tee -a "$LOG_PATH"
    exit 1
fi

for famdir in $family_dirs; do
    family_name=$(basename "$famdir")
    echo "Checking family: $family_name" | tee -a "$LOG_PATH"

    # Restrict to Regular/Bold/Italic/BoldItalic to appease GF static-family rules
    files=$(find "$famdir" -type f \( -name "*-Regular.ttf" -o -name "*-Bold.ttf" -o -name "*-Italic.ttf" -o -name "*-BoldItalic.ttf" \))
    if [ -z "$files" ]; then
        echo "  Skipping $family_name; no standard styles found" | tee -a "$LOG_PATH"
        continue
    fi

    fam_report_dir="$REPORT_DIR/$family_name"
    mkdir -p "$fam_report_dir"

    set +e
    uv run sources/scripts/fontbakery_wrapper.py check-googlefonts \
        -C --succinct --loglevel WARN \
        --exclude-checkid opentype/monospace \
        --exclude-checkid opentype/STAT/ital_axis \
        --exclude-checkid name/italic_names \
        --exclude-checkid googlefonts/glyphsets/shape_languages \
        --exclude-checkid googlefonts/font_names \
        --ghmarkdown "$fam_report_dir/report.md" \
        $files 2>&1 | tee -a "$LOG_PATH"
    code=${PIPESTATUS[0]}
    set -e
    if [ "$code" -ne 0 ]; then
        FONTBAKERY_EXIT=$code
    fi
done

echo >> "$LOG_PATH"
echo "Fontbakery exit code: $FONTBAKERY_EXIT" >> "$LOG_PATH"
echo "Font validation complete. Reports saved to $REPORT_DIR/*/report.md"
