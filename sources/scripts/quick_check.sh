#!/usr/bin/env bash
#
# Quick validation script - checks only the Regular weight
# Usage: bash sources/scripts/quick_check.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

readonly FONT_DIR="sources/output/quick"
readonly REPORT_PATH="$FONT_DIR/report.txt"

if [ ! -f "$FONT_DIR/IosevkaCharon-Regular.ttf" ]; then
    echo "ERROR: Regular font not found. Run quick_build.sh first."
    exit 1
fi

echo "Running quick validation on Regular weight only..."

fontbakery check-googlefonts \
    -C --succinct --loglevel FAIL \
    --exclude-checkid opentype/monospace \
    "$FONT_DIR/IosevkaCharon-Regular.ttf" 2>&1 | tee "$REPORT_PATH"

echo ""
echo "Quick validation complete!"
echo "Report saved to $REPORT_PATH"
echo ""
echo "FAIL count:"
grep -c "FAIL" "$REPORT_PATH" || echo "0"
