#!/usr/bin/env python3
"""
Generate WOFF2 webfonts from TTF files.

For each TTF in input_folder:
  - Subsets to Basic Latin (U+0000..U+007F)
  - Generates .woff2 in output_folder/woff2
"""

import os
import sys
from fontTools import subset
from fontTools.ttLib import TTFont

def generate_webfonts(input_folder: str, output_folder: str) -> None:
    """Generates WOFF2 webfonts from TTF files.

    Args:
        input_folder: Directory containing source TTF files.
        output_folder: Top-level directory for the font family.
    """
    woff2_output_folder = os.path.join(output_folder, "woff2")
    os.makedirs(woff2_output_folder, exist_ok=True)

    for file_name in os.listdir(input_folder):
        if not file_name.endswith(".ttf"):
            continue

        input_path = os.path.join(input_folder, file_name)
        woff2_path = os.path.join(woff2_output_folder, file_name.replace(".ttf", ".woff2"))

        print(f"[webfont] Processing {file_name}...")

        # Load font and subset
        font = TTFont(input_path)
        subsetter = subset.Subsetter()

        # Configure subsetter for Basic Latin range
        unicodes = list(range(0x0000, 0x0080))  # U+0000 to U+007F
        subsetter.populate(unicodes=unicodes)
        subsetter.subset(font)

        # Save as WOFF2
        font.flavor = "woff2"
        font.save(woff2_path)
        font.close()

        print(f"[webfont] Saved WOFF2 webfont: {woff2_path}")

    print("[webfont] Processing complete. All webfonts have been generated.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: generate_webfonts.py <input_folder> <output_folder>")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2]

    if not os.path.isdir(input_folder):
        print(f"Error: Input folder does not exist: {input_folder}")
        sys.exit(1)

    generate_webfonts(input_folder, output_folder)
