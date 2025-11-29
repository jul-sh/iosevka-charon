#!/usr/bin/env bash

set -euo pipefail

FONTS_DIR="fonts/ttf"

for f in $(find $FONTS_DIR -type f -name "*.ttf"); do
  gftools post-process --autohint "$f"
done
