#!/usr/bin/env bash
set -euo pipefail

# Run all make targets in sequence for testing
# This script runs the complete test suite locally or in CI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          Running Complete Font Test Suite                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Extract PHONY targets from Makefile
if [ ! -f "Makefile" ]; then
    echo "❌ Makefile not found"
    exit 1
fi

# Get all PHONY targets and filter out non-test targets
PHONY_LINE=$(grep "^\.PHONY:" Makefile | head -1)
ALL_TARGETS=$(echo "$PHONY_LINE" | sed 's/\.PHONY://g' | tr ' ' '\n' | grep -v '^$')

# Filter out targets we don't want to run in tests
# Exclude: help (informational), clean (destructive)
EXCLUDE_PATTERN="^(help|clean)$"
TARGETS=($(echo "$ALL_TARGETS" | grep -Ev "$EXCLUDE_PATTERN" || true))

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "❌ No test targets found in Makefile"
    exit 1
fi

echo "Test targets: ${TARGETS[*]}"
echo ""

FAILED_TARGETS=()

for i in "${!TARGETS[@]}"; do
    target="${TARGETS[$i]}"
    num=$((i + 1))
    total=${#TARGETS[@]}

    echo "┌────────────────────────────────────────────────────────────────┐"
    printf "│ %d/%d: make %-50s │\n" "$num" "$total" "$target"
    echo "└────────────────────────────────────────────────────────────────┘"

    if make "$target"; then
        echo ""
    else
        FAILED_TARGETS+=("$target")
        echo ""
        echo "❌ make $target failed"
        echo ""

        # Stop on build failures, continue on test/proof failures
        if [ "$target" = "build" ]; then
            echo "Cannot continue without successful build"
            exit 1
        fi
    fi
done

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     Test Suite Summary                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ ${#FAILED_TARGETS[@]} -eq 0 ]; then
    echo "✅ All targets completed successfully!"
    echo ""
    echo "Generated artifacts:"
    echo "  - Fonts: fonts/"
    if [ -d "out/fontspector" ]; then
        echo "  - Test reports: out/fontspector/"
    fi
    if [ -d "out/proof" ]; then
        echo "  - Proof documents: out/proof/"
    fi
    echo ""
    exit 0
else
    echo "❌ Some targets failed:"
    for target in "${FAILED_TARGETS[@]}"; do
        echo "  - make $target"
    done
    echo ""
    echo "Review the output above for details"
    echo ""
    exit 1
fi
