#!/usr/bin/env python3
"""Post-process all TTF fonts for Google Fonts compliance."""

import pathlib
import sys

# Add scripts directory to path to import fix_fonts
sys.path.append(str(pathlib.Path(__file__).parent))
import fix_fonts

def main():
    root = pathlib.Path("sources/output")
    fonts = sorted(root.glob("**/*.ttf"))

    if not fonts:
        raise SystemExit("No TTF files found in sources/output to post-process.")

    for font_path in fonts:
        fix_fonts.post_process_font(font_path)

if __name__ == "__main__":
    main()
