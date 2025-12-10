#!/usr/bin/env python3
"""
Parallel post-processing of font files.
This script processes all TTF files in general_use_fonts/, applies Google Fonts
compliance fixes, and outputs them to output/ with proper naming.
"""

import pathlib
import shutil
import sys
from multiprocessing import Pool, cpu_count

# Add scripts directory to path
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fix_fonts


def process_and_copy_font(font_path):
    """
    Post-process a font and copy it to the final output directory.

    Args:
        font_path: Path to the source font in general_use_fonts/

    Returns:
        tuple: (success: bool, input_path: Path, output_path: Path)
    """
    try:
        # Determine the plan directory and output location
        # font_path structure: general_use_fonts/<plan_name>/ttf/<font>.ttf
        plan_dir = font_path.parent.parent.name

        # Convert directory name to lowercase and remove spaces for Google Fonts compliance
        dest_dir_name = plan_dir.lower().replace(" ", "")
        dest_dir = pathlib.Path("fonts") / dest_dir_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Normalize filename for Google Fonts compliance
        # ExtraBold -> Extrabold, ExtraLight -> Extralight, SemiBold -> Semibold
        filename = font_path.name
        filename = filename.replace("ExtraBold", "Extrabold")
        filename = filename.replace("ExtraLight", "Extralight")
        filename = filename.replace("SemiBold", "Semibold")

        output_path = dest_dir / filename

        # Apply all post-processing fixes and write to output
        success = fix_fonts.post_process_font(font_path, output_path)

        return (success, font_path, output_path)

    except Exception as e:
        import traceback

        print(f"ERROR processing {font_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return (False, font_path, None)


def main():
    root = pathlib.Path("general_use_fonts")
    fonts = sorted(root.glob("**/*.ttf"))

    if not fonts:
        print(
            "ERROR: No TTF files found in general_use_fonts/ to post-process.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clean and prepare output directory
    output_root = pathlib.Path("fonts")
    if output_root.exists():
        print(f"Cleaning existing output directory: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # Parallelize post-processing using all available CPU cores
    num_workers = cpu_count()
    print(f"Post-processing {len(fonts)} fonts using {num_workers} parallel workers...")
    print(f"Input:  general_use_fonts/")
    print(f"Output: fonts/")
    print()

    with Pool(num_workers) as pool:
        results = pool.map(process_and_copy_font, fonts)

    # Summary
    successful = sum(1 for success, _, _ in results if success)
    failed = len(results) - successful

    print()
    print("=" * 60)
    print(f"Post-processing complete!")
    print(f"  Successful: {successful}/{len(fonts)}")
    if failed > 0:
        print(f"  Failed: {failed}")
        print("\nFailed fonts:")
        for success, input_path, _ in results:
            if not success:
                print(f"  - {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
