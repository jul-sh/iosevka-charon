#!/usr/bin/env bash
set -euo pipefail

# Validate Nix environment
# This script checks that the Nix flake is valid

echo "=== Validating Nix Environment ==="
echo ""

echo "→ Checking Nix flake..."
if ! nix flake check --show-trace; then
    echo "❌ Nix flake check failed"
    exit 1
fi
echo "✅ Nix flake is valid"
echo ""

echo "=== Environment Validation Complete ==="
exit 0
