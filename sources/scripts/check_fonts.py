#!/usr/bin/env python3
"""Runs Fontbakery quality checks on generated TTF files."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

def main():
    # Get repository root
    repo_root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True
    ).strip())

    # Set default font directory if not provided
    font_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "fonts" / "ttf"
    report_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else repo_root / "out" / "fontbakery"
    report_path = report_dir / "report.md"
    log_timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_path = report_dir / f"fontbakery-{log_timestamp}.log"

    report_dir.mkdir(parents=True, exist_ok=True)

    # Ensure font directory exists and contains TTF files
    if not font_dir.exists():
        print(f"ERROR: {font_dir} directory does not exist", file=sys.stderr)
        sys.exit(1)

    # Run per-family to avoid cross-family consistency errors
    print(f"Running Fontbakery checks on fonts in {font_dir}...")
    with open(log_path, 'w') as log_file:
        log_file.write(f"Fontbakery log - {datetime.now().isoformat()}\n")

    fontbakery_exit = 0
    family_dirs = [d for d in font_dir.iterdir() if d.is_dir()]

    if not family_dirs:
        with open(log_path, 'a') as log_file:
            msg = f"ERROR: No family directories found under {font_dir}\n"
            log_file.write(msg)
            print(msg, end='', file=sys.stderr)
        sys.exit(1)

    for famdir in family_dirs:
        family_name = famdir.name
        msg = f"Checking family: {family_name}\n"
        print(msg, end='')
        with open(log_path, 'a') as log_file:
            log_file.write(msg)

        # Restrict to Regular/Bold/Italic/BoldItalic to appease GF static-family rules
        files = list(famdir.glob("*-Regular.ttf"))
        files.extend(famdir.glob("*-Bold.ttf"))
        files.extend(famdir.glob("*-Italic.ttf"))
        files.extend(famdir.glob("*-BoldItalic.ttf"))

        if not files:
            msg = f"  Skipping {family_name}; no standard styles found\n"
            print(msg, end='')
            with open(log_path, 'a') as log_file:
                log_file.write(msg)
            continue

        fam_report_dir = report_dir / family_name
        fam_report_dir.mkdir(parents=True, exist_ok=True)

        # Run fontbakery
        cmd = [
            "uv", "run", "sources/scripts/fontbakery_wrapper.py", "check-googlefonts",
            "-C", "--succinct", "--loglevel", "WARN",
            "--exclude-checkid", "opentype/monospace",
            "--exclude-checkid", "opentype/STAT/ital_axis",
            "--exclude-checkid", "name/italic_names",
            "--exclude-checkid", "googlefonts/glyphsets/shape_languages",
            "--exclude-checkid", "googlefonts/font_names",
            "--ghmarkdown", str(fam_report_dir / "report.md"),
        ]
        cmd.extend(str(f) for f in files)

        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True
        )

        # Tee output to both console and log file
        output = result.stdout + result.stderr
        print(output, end='')
        with open(log_path, 'a') as log_file:
            log_file.write(output)

        if result.returncode != 0:
            fontbakery_exit = result.returncode

    with open(log_path, 'a') as log_file:
        log_file.write(f"\nFontbakery exit code: {fontbakery_exit}\n")

    print(f"Font validation complete. Reports saved to {report_dir}/*/report.md")
    sys.exit(fontbakery_exit)

if __name__ == "__main__":
    main()
