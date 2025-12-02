#!/usr/bin/env bash
set -euo pipefail

# Run fontspector quality tests
# This script runs fontspector tests and reports results

echo "=== Running Font Quality Tests ==="
echo ""

# Check if fonts exist
if [ ! -d "fonts" ] || [ -z "$(find fonts -name '*.ttf' -type f 2>/dev/null)" ]; then
    echo "❌ No fonts found. Run tests/build-fonts.sh first."
    exit 1
fi

echo "→ Running fontspector tests..."
set +e
make test
TEST_EXIT=$?
set -e

echo ""

# Check if report was generated
REPORT_FILE="out/fontspector/fontspector-report.md"
if [ -f "$REPORT_FILE" ]; then
    echo "📊 Test report generated: $REPORT_FILE"

    # Extract summary
    if command -v head &> /dev/null && command -v tail &> /dev/null; then
        echo ""
        echo "--- Test Summary ---"
        head -30 "$REPORT_FILE" | tail -15
        echo "---"
        echo ""
        echo "Full report: $REPORT_FILE"
        echo "HTML report: out/fontspector/fontspector-report.html"
    fi
else
    echo "⚠️  Test report not found at $REPORT_FILE"
fi

echo ""

if [ $TEST_EXIT -eq 0 ]; then
    echo "✅ All fontspector tests passed!"
    echo ""
    echo "=== Font Quality Tests Complete ==="
    exit 0
else
    echo "❌ fontspector tests failed with exit code $TEST_EXIT"
    echo ""
    echo "Review the report at $REPORT_FILE for details"
    echo ""
    echo "=== Font Quality Tests Failed ==="
    exit 1
fi
