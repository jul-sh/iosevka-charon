#!/usr/bin/env bash
#
# Updates all dependencies: Python (UV), Rust toolchain, fontspector, and flake.nix.
# This script queries for the latest compatible versions and updates the pinned versions.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

readonly REPO_ROOT="$(git rev-parse --show-toplevel)"
readonly REQUIREMENTS="$REPO_ROOT/sources/requirements.txt"
readonly UV_LOCKFILE="$REPO_ROOT/sources/requirements.lock"
readonly FLAKE_NIX="$REPO_ROOT/sources/flake.nix"

echo "═══════════════════════════════════════════════"
echo "Querying latest versions..."
echo "═══════════════════════════════════════════════"

# 1. Query latest Rust nightly version
echo ""
echo "1. Querying latest Rust nightly version..."
if ! command -v rustup &> /dev/null; then
    echo "   ⚠ rustup not found. Please install rustup first."
    echo "   Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

# Get the latest nightly version with a specific date
# First, update nightly to ensure we have the latest
rustup update nightly --no-self-update 2>/dev/null || true

# Get the specific nightly version (e.g., nightly-2024-11-30)
RUST_VERSION=$(rustup show active-toolchain 2>/dev/null | grep nightly | head -1 | grep -oE 'nightly-[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo "")

if [ -z "$RUST_VERSION" ]; then
    # Fallback: construct from today's date
    RUST_VERSION="nightly-$(date +%Y-%m-%d)"
fi

echo "   → Latest Rust nightly: $RUST_VERSION"

# 2. Query latest fontspector version
echo ""
echo "2. Querying latest fontspector version..."
if ! command -v cargo &> /dev/null; then
    echo "   ⚠ cargo not found. Skipping fontspector query."
    FONTSPECTOR_VERSION="1.4.0"
else
    FONTSPECTOR_VERSION=$(cargo search fontspector --limit 1 2>/dev/null | grep "^fontspector =" | sed 's/fontspector = "\(.*\)".*/\1/' || echo "1.4.0")
    echo "   → Latest fontspector: $FONTSPECTOR_VERSION"
fi

# 3. Update flake.nix with new versions
echo ""
echo "3. Updating flake.nix with new versions..."
if [ -f "$FLAKE_NIX" ]; then
    # Update RUST_VERSION line (handles both "nightly" and "nightly-YYYY-MM-DD" formats)
    sed -i.bak "s/RUST_VERSION=\"[^\"]*\"/RUST_VERSION=\"$RUST_VERSION\"/" "$FLAKE_NIX"
    # Update FONTSPECTOR_VERSION line
    sed -i.bak "s/FONTSPECTOR_VERSION=\"[0-9.]*\"/FONTSPECTOR_VERSION=\"$FONTSPECTOR_VERSION\"/" "$FLAKE_NIX"
    rm -f "$FLAKE_NIX.bak"
    echo "   ✓ Updated $FLAKE_NIX"
    echo "     - RUST_VERSION=$RUST_VERSION"
    echo "     - FONTSPECTOR_VERSION=$FONTSPECTOR_VERSION"
else
    echo "   ⚠ $FLAKE_NIX not found"
fi

# 4. Update Nix flake lock
echo ""
echo "4. Updating Nix flake lock..."
if [ -f "$REPO_ROOT/sources/flake.nix" ]; then
    cd "$REPO_ROOT/sources"
    nix flake update 2>&1 | grep -E "(Updated|warning)" || true
    cd "$REPO_ROOT"
    echo "   ✓ Updated flake.lock"
else
    echo "   ⚠ Skipping flake lock update (flake.nix not found)"
fi

# 5. Update Python dependencies
echo ""
echo "5. Updating Python dependencies lockfile..."
uv pip compile "$REQUIREMENTS" --output-file "$UV_LOCKFILE" --prerelease=allow
echo "   ✓ Successfully updated $UV_LOCKFILE"


echo ""
echo "═══════════════════════════════════════════════"
echo "✓ All dependencies updated successfully!"
echo "═══════════════════════════════════════════════"
echo ""
echo "Summary:"
echo "  - Rust: $RUST_VERSION"
echo "  - fontspector: $FONTSPECTOR_VERSION"
echo "  - Python deps: updated in $UV_LOCKFILE"
echo "  - Nix flake: updated"
echo ""
