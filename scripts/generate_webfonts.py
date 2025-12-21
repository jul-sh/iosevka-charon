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

import logging
import pathlib
import shutil
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fontTools import subset
from fontTools.ttLib import TTFont

# Constants
# ----------------------------------------------------------------------------

INPUT_ROOT = Path("fonts")
OUTPUT_ROOT = Path("webfonts")

# Unicode ranges for subsetting
SUBSETS: Dict[str, Optional[str]] = {
    "full": None,  # No subsetting - keep all glyphs
    "latin-ext": "U+0000-024F",  # Basic Latin + Latin-1 Supplement + Latin Extended-A/B
    "latin": "U+0000-00FF",  # Basic Latin + Latin-1 Supplement
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# Core Functions
# ----------------------------------------------------------------------------


def generate_webfont(args: Tuple[Path, str, Optional[str]]) -> Tuple[bool, Path, Optional[Path], str]:
    """
    Generate a single WOFF2 webfont, optionally with subsetting.

    Args:
        args: Tuple of (font_path, subset_name, unicode_range)

    Returns:
        tuple: (success, input_path, output_path, subset_name)
    """
    font_path, subset_name, unicode_range = args

    try:
        # Determine output path
        # Input: fonts/<family>/Font-Weight.ttf
        # Output: webfonts/<subset>/<family>/Font-Weight.woff2
        family_dir = font_path.parent.name
        stem = font_path.stem  # e.g., "IosevkaCharon-Regular"
        output_filename = f"{stem}.woff2"

        output_dir = OUTPUT_ROOT / subset_name / family_dir
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

        return True, font_path, output_path, subset_name

    except Exception as e:
        logger.error(f"ERROR generating {subset_name} for {font_path}: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc()
        return False, font_path, None, subset_name


# Main Entry Point
# ----------------------------------------------------------------------------


def main() -> None:
    """Main execution block."""
    fonts = sorted(INPUT_ROOT.glob("**/*.ttf"))

    if not fonts:
        logger.error(f"ERROR: No TTF files found in {INPUT_ROOT} to process.")
        sys.exit(1)

    # Clean and prepare output directory
    if OUTPUT_ROOT.exists():
        logger.info(f"Cleaning existing output directory: {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # Build work queue: each font × each subset variant
    work_items: List[Tuple[Path, str, Optional[str]]] = []
    for font_path in fonts:
        for subset_name, unicode_range in SUBSETS.items():
            work_items.append((font_path, subset_name, unicode_range))

    # Parallelize generation using all available CPU cores
    num_workers = cpu_count()
    logger.info(f"Generating {len(work_items)} WOFF2 files ({len(fonts)} fonts × {len(SUBSETS)} subsets)")
    logger.info(f"Using {num_workers} parallel workers...")
    logger.info(f"Input:  {INPUT_ROOT}/")
    logger.info(f"Output: {OUTPUT_ROOT}/")
    logger.info("")

    with Pool(num_workers) as pool:
        results = pool.map(generate_webfont, work_items)

    # Summary
    successful = sum(1 for success, _, _, _ in results if success)
    failed = len(results) - successful

    logger.info("")
    logger.info("=" * 60)
    logger.info("WOFF2 generation complete!")
    logger.info(f"  Successful: {successful}/{len(results)}")

    if failed > 0:
        logger.error(f"  Failed: {failed}")
        logger.error("\nFailed items:")
        for success, input_path, _, subset_name in results:
            if not success:
                logger.error(f"  - {input_path} ({subset_name})")
        sys.exit(1)

    # Print file size summary for one font as a sanity check
    logger.info("")
    logger.info("Sample file sizes (IosevkaCharon-Regular):")
    for subset_name in SUBSETS.keys():
        sample_file = OUTPUT_ROOT / subset_name / "iosevkacharon" / "IosevkaCharon-Regular.woff2"
        if sample_file.exists():
            size_kb = sample_file.stat().st_size / 1024
            logger.info(f"  {subset_name}: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
