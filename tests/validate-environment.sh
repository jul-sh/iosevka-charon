#!/usr/bin/env bash
set -euo pipefail

# Validate Nix environment and dependencies
# This script checks that the Nix flake is valid and all required tools are available

echo "=== Validating Nix Environment ==="
echo ""

echo "→ Checking Nix flake..."
if ! nix flake check --show-trace; then
    echo "❌ Nix flake check failed"
    exit 1
fi
echo "✅ Nix flake is valid"
echo ""

echo "→ Verifying fontspector builds..."
if ! nix build .#fontspector --print-build-logs; then
    echo "❌ fontspector failed to build"
    exit 1
fi
echo "✅ fontspector builds successfully"
echo ""

echo "→ Verifying development shell..."
nix develop --command bash -c '
    echo "Rust: $(rustc --version)"
    echo "Node: $(node --version)"
    echo "Python: $(python --version)"
    echo "fontspector: $(fontspector --version)"
    if command -v diffenator2 &> /dev/null; then
        echo "diffenator2: $(diffenator2 --version 2>&1 | head -1 || echo "available")"
    else
        echo "diffenator2: command not found"
        exit 1
    fi
'

if [ $? -eq 0 ]; then
    echo "✅ Development shell is valid"
    echo ""
    echo "=== Environment Validation Complete ==="
    exit 0
else
    echo "❌ Development shell validation failed"
    exit 1
fi
