#!/usr/bin/env bash
set -euo pipefail

# Build fonts and verify output
# This script builds the fonts and ensures TTF files were generated

echo "=== Building Fonts ==="
echo ""

echo "→ Running make build..."
if ! make build; then
    echo "❌ Font build failed"
    exit 1
fi
echo "✅ Build completed"
echo ""

echo "→ Checking for generated font files..."
if [ ! -d "fonts" ]; then
    echo "❌ fonts/ directory does not exist"
    exit 1
fi

TTF_COUNT=$(find fonts -name '*.ttf' -type f | wc -l | tr -d ' ')
if [ "$TTF_COUNT" -eq 0 ]; then
    echo "❌ No TTF font files were generated"
    exit 1
fi

echo "✅ Found $TTF_COUNT TTF font files:"
find fonts -name '*.ttf' -type f | sort
echo ""

echo "=== Font Build Complete ==="
exit 0
