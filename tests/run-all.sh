#!/usr/bin/env bash
set -euo pipefail

# Run all tests in sequence
# This script runs the complete test suite locally

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          Running Complete Font Test Suite                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

FAILED_TESTS=()

# Run validate-environment
echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ 1/4: Validate Environment                                      │"
echo "└────────────────────────────────────────────────────────────────┘"
if bash "$SCRIPT_DIR/validate-environment.sh"; then
    echo ""
else
    FAILED_TESTS+=("validate-environment")
    echo ""
    echo "⚠️  Environment validation failed, but continuing..."
    echo ""
fi

# Run build-fonts
echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ 2/4: Build Fonts                                               │"
echo "└────────────────────────────────────────────────────────────────┘"
if bash "$SCRIPT_DIR/build-fonts.sh"; then
    echo ""
else
    FAILED_TESTS+=("build-fonts")
    echo ""
    echo "❌ Font build failed - cannot continue"
    exit 1
fi

# Run test-fonts
echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ 3/4: Test Fonts                                                │"
echo "└────────────────────────────────────────────────────────────────┘"
if bash "$SCRIPT_DIR/test-fonts.sh"; then
    echo ""
else
    FAILED_TESTS+=("test-fonts")
    echo ""
    echo "⚠️  Font tests failed, but continuing with proofs..."
    echo ""
fi

# Run generate-proofs
echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ 4/4: Generate Proofs                                           │"
echo "└────────────────────────────────────────────────────────────────┘"
if bash "$SCRIPT_DIR/generate-proofs.sh"; then
    echo ""
else
    FAILED_TESTS+=("generate-proofs")
    echo ""
fi

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     Test Suite Summary                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    echo "✅ All tests passed!"
    echo ""
    echo "Generated artifacts:"
    echo "  - Fonts: fonts/"
    echo "  - Test reports: out/fontspector/"
    echo "  - Proof documents: out/proof/"
    echo ""
    exit 0
else
    echo "❌ Some tests failed:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    echo ""
    echo "Review the output above for details"
    echo ""
    exit 1
fi
