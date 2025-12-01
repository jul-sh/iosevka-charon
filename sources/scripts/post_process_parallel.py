#!/usr/bin/env python3
"""
Parallel post-processing of font files.
This script processes all TTF files in the output directory using all available CPU cores.
"""

import pathlib
import sys
from multiprocessing import Pool, cpu_count

# Add scripts directory to path
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fix_fonts


def main():
    root = pathlib.Path("sources/output")
    fonts = sorted(root.glob("**/*.ttf"))

    if not fonts:
        print("ERROR: No TTF files found in sources/output to post-process.", file=sys.stderr)
        sys.exit(1)

    # Parallelize post-processing using all available CPU cores
    num_workers = cpu_count()
    print(f"Post-processing {len(fonts)} fonts using {num_workers} parallel workers...")

    with Pool(num_workers) as pool:
        pool.map(fix_fonts.post_process_font, fonts)

    print("Post-processing complete!")


if __name__ == "__main__":
    main()
