#!/usr/bin/env bash

set -euo pipefail

FONTS_DIR="fonts/ttf"
REPORT_DIR="out/fontbakery"

mkdir -p $REPORT_DIR
fontbakery check-googlefonts --html $REPORT_DIR/report.html \
  -x com.google.fonts/check/iso15008 \
  -x com.google.fonts/check/glyphsets \
  $(find $FONTS_DIR -type f -name "*.ttf")
