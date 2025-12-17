#!/usr/bin/env python3
"""
Generate WOFF2 webfonts with character set subsets.

This script processes TTF fonts from fonts/ and generates WOFF2 webfonts
in three variants:
  - full: Complete character set (no subsetting)
  - latin-ext: Basic Latin + Latin Extended A/B (U+0000-024F)
  - latin: Basic Latin only (U+0000-00FF)

Output is written to webfonts/<subset>/<family>/ with subset-first directory structure.
"""

import pathlib
import shutil
import sys
from multiprocessing import Pool, cpu_count

from fontTools import subset
from fontTools.ttLib import TTFont


# Unicode ranges for subsetting
SUBSETS = {
    "full": None,  # No subsetting - keep all glyphs
    "latin-ext": "U+0000-024F",  # Basic Latin + Latin-1 Supplement + Latin Extended-A/B
    "latin": "U+0000-00FF",  # Basic Latin + Latin-1 Supplement
}


def generate_webfont(args):
    """
    Generate a single WOFF2 webfont, optionally with subsetting.

    Args:
        args: Tuple of (font_path, subset_name, unicode_range)

    Returns:
        tuple: (success: bool, input_path: Path, output_path: Path, subset_name: str)
    """
    font_path, subset_name, unicode_range = args

    try:
        # Determine output path
        # Input: fonts/<family>/Font-Weight.ttf
        # Output: webfonts/<subset>/<family>/Font-Weight.woff2
        family_dir = font_path.parent.name
        stem = font_path.stem  # e.g., "IosevkaCharon-Regular"
        output_filename = f"{stem}.woff2"

        output_dir = pathlib.Path("webfonts") / subset_name / family_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename

        if unicode_range is None:
            # Full variant - just convert to WOFF2 without subsetting
            font = TTFont(font_path)
            font.flavor = "woff2"
            font.save(output_path)
        else:
            # Subset variant - use fontTools.subset
            options = subset.Options()
            options.flavor = "woff2"
            options.layout_features = ["*"]  # Keep all OpenType features
            options.glyph_names = False  # Strip glyph names for smaller file
            options.name_IDs = ["*"]  # Keep all name table entries
            options.name_legacy = True
            options.name_languages = ["*"]
            options.notdef_outline = True  # Keep .notdef glyph outline
            options.recommended_glyphs = True  # Keep .notdef, space, etc.

            font = subset.load_font(font_path, options)
            subsetter = subset.Subsetter(options)
            subsetter.populate(unicodes=subset.parse_unicodes(unicode_range))
            subsetter.subset(font)
            subset.save_font(font, output_path, options)

        return (True, font_path, output_path, subset_name)

    except Exception as e:
        import traceback

        print(f"ERROR generating {subset_name} for {font_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return (False, font_path, None, subset_name)


def main():
    input_root = pathlib.Path("fonts")
    output_root = pathlib.Path("webfonts")

    fonts = sorted(input_root.glob("**/*.ttf"))

    if not fonts:
        print(
            "ERROR: No TTF files found in fonts/ to process.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clean and prepare output directory
    if output_root.exists():
        print(f"Cleaning existing output directory: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # Build work queue: each font × each subset variant
    work_items = []
    for font_path in fonts:
        for subset_name, unicode_range in SUBSETS.items():
            work_items.append((font_path, subset_name, unicode_range))

    # Parallelize generation using all available CPU cores
    num_workers = cpu_count()
    print(f"Generating {len(work_items)} WOFF2 files ({len(fonts)} fonts × {len(SUBSETS)} subsets)")
    print(f"Using {num_workers} parallel workers...")
    print(f"Input:  fonts/")
    print(f"Output: webfonts/")
    print()

    with Pool(num_workers) as pool:
        results = pool.map(generate_webfont, work_items)

    # Summary
    successful = sum(1 for success, _, _, _ in results if success)
    failed = len(results) - successful

    print()
    print("=" * 60)
    print(f"WOFF2 generation complete!")
    print(f"  Successful: {successful}/{len(results)}")

    if failed > 0:
        print(f"  Failed: {failed}")
        print("\nFailed items:")
        for success, input_path, _, subset_name in results:
            if not success:
                print(f"  - {input_path} ({subset_name})")
        sys.exit(1)

    # Print file size summary for one font as a sanity check
    print()
    print("Sample file sizes (IosevkaCharon-Regular):")
    for subset_name in SUBSETS.keys():
        sample_file = output_root / subset_name / "iosevkacharon" / "IosevkaCharon-Regular.woff2"
        if sample_file.exists():
            size_kb = sample_file.stat().st_size / 1024
            print(f"  {subset_name}: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
