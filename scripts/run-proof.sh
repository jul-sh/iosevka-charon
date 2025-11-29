#!/usr/bin/env bash

set -euo pipefail

FONTS_DIR="fonts/ttf"
PROOF_DIR="out/proof"

TOCHECK=$(find $FONTS_DIR -type f -name "*.ttf")
mkdir -p $PROOF_DIR
diffenator2 proof $TOCHECK -o $PROOF_DIR
