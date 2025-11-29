#!/usr/bin/env python3
"""Main entry point for building Iosevka fonts."""

import subprocess
import sys
from pathlib import Path

# Import the build scripts directly
sys.path.insert(0, str(Path(__file__).parent))
import build_fonts
import post_process_fonts

def main():
    print("Starting Iosevka font build process...")

    # Get repository root
    repo_root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True
    ).strip())

    # Ensure submodules are available
    print("Updating submodules...")
    subprocess.check_call(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=repo_root
    )

    # Run the build script to generate TTFs
    print("Building fonts...")
    build_fonts.main()

    # Post-process fonts for GF compliance
    print("Post-processing fonts for GF compliance…")
    post_process_fonts.main()

    # Sync fonts into fonts/ttf/
    print("Syncing fonts into fonts/ttf/…")
    fonts_dir = repo_root / "fonts"
    if fonts_dir.exists():
        import shutil
        shutil.rmtree(fonts_dir)

    ttf_dir = fonts_dir / "ttf"
    ttf_dir.mkdir(parents=True, exist_ok=True)

    # Find and copy all TTF files
    output_dir = repo_root / "sources" / "output"
    ttf_files = list(output_dir.glob("**/*.ttf"))

    if not ttf_files:
        print("ERROR: No TTF files were produced under sources/output.", file=sys.stderr)
        sys.exit(1)

    for font_path in ttf_files:
        # Extract plan directory (two levels up from the font file)
        plan_dir = font_path.parent.parent.name
        dest_dir = ttf_dir / plan_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy2(font_path, dest_dir / font_path.name)

    print("Build complete! Font files are available in fonts/ttf/")

if __name__ == "__main__":
    main()
