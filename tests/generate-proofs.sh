#!/usr/bin/env bash
set -euo pipefail

# Generate proof documents
# This script generates HTML proof documents using diffenator2

echo "=== Generating Proof Documents ==="
echo ""

# Check if fonts exist
if [ ! -d "fonts" ] || [ -z "$(find fonts -name '*.ttf' -type f 2>/dev/null)" ]; then
    echo "❌ No fonts found. Run tests/build-fonts.sh first."
    exit 1
fi

echo "→ Running make proof..."
if ! make proof; then
    echo "❌ Proof generation failed"
    exit 1
fi
echo "✅ Proof generation completed"
echo ""

echo "→ Checking for generated proof files..."
if [ ! -d "out/proof" ]; then
    echo "⚠️  out/proof/ directory does not exist"
    exit 1
fi

HTML_COUNT=$(find out/proof -name '*.html' -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$HTML_COUNT" -eq 0 ]; then
    echo "⚠️  No HTML proof files were generated"
    exit 1
fi

echo "✅ Generated $HTML_COUNT HTML proof files:"
find out/proof -name '*.html' -type f | sort | head -10
if [ "$HTML_COUNT" -gt 10 ]; then
    echo "... and $((HTML_COUNT - 10)) more"
fi
echo ""

if [ -f "out/proof/diffenator2-report.html" ]; then
    echo "📊 Main report: out/proof/diffenator2-report.html"
    echo ""
    echo "To view locally, open: file://$(pwd)/out/proof/diffenator2-report.html"
fi

echo ""
echo "=== Proof Generation Complete ==="
exit 0
