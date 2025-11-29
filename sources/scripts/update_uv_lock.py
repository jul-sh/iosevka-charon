#!/usr/bin/env python3
"""Updates the Python dependency lockfile using uv."""

import subprocess
from pathlib import Path

def main():
    # Get repository root
    repo_root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True
    ).strip())

    requirements = repo_root / "sources" / "requirements.txt"
    uv_lockfile = repo_root / "sources" / "requirements.lock"

    print("Updating Python dependencies lockfile...")

    # Generate new lockfile from requirements.txt
    subprocess.check_call([
        "uv", "pip", "compile",
        str(requirements),
        "--output-file", str(uv_lockfile),
        "--prerelease=allow"
    ])

    print(f"Successfully updated {uv_lockfile} from {requirements}")

if __name__ == "__main__":
    main()
