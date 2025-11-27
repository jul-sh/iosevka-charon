#!/usr/bin/env python3
"""
Thin wrapper around fontbakery that patches missing script metadata before
dispatching to the real CLI. This keeps the googlefonts/glyphsets/shape_languages
check from crashing on newer gflanguages entries that reference the Beria Erfe
script code ("Berf").
"""

import sys
from fontTools.unicodedata import Scripts

# Prevent KeyError in glyphsets when encountering the non-standard Berf script.
Scripts.NAMES.setdefault("Berf", "Berf")

from fontbakery.cli import main

if __name__ == "__main__":
    sys.exit(main())
