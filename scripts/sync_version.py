#!/usr/bin/env python3
"""
Sync the font version from the upstream Iosevka source to a Google Fonts
compliant version constant.

Reads the semver version from sources/iosevka/package.json, converts it to
Google Fonts format (MAJOR.SIGNIFICANTMINORPATCH), and writes the result
to sources/version.json.

Google Fonts versioning (from gf-guide/requirements.html#font-versioning):
    semver  MAJOR.MINOR.PATCH
    GF      MAJOR.SIGNIFICANTMINORPATCH

    Example: 33.3.5  →  33.305
             33.3.15 →  33.315
              2.0.0  →   2.000
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_PACKAGE_JSON = REPO_ROOT / "sources" / "iosevka" / "package.json"
VERSION_JSON = REPO_ROOT / "sources" / "version.json"


def semver_to_gf(semver: str) -> str:
    """Convert a semver string to Google Fonts version format.

    Args:
        semver: Version string like "33.3.5".

    Returns:
        GF version string like "33.305".
    """
    parts = semver.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected semver with 3 parts, got: {semver!r}")

    major, minor, patch = parts
    # SIGNIFICANTMINORPATCH = MINOR (1 digit) + PATCH (2 digits, zero-padded)
    # This gives 3 decimal digits total, matching GF convention.
    gf_decimal = f"{int(minor)}{int(patch):02d}"
    return f"{int(major)}.{gf_decimal}"


def read_upstream_version() -> str:
    """Read the version field from the upstream Iosevka package.json."""
    if not UPSTREAM_PACKAGE_JSON.exists():
        print(f"ERROR: {UPSTREAM_PACKAGE_JSON} not found.", file=sys.stderr)
        print("Is the Iosevka subtree present at sources/iosevka/?", file=sys.stderr)
        sys.exit(1)

    data = json.loads(UPSTREAM_PACKAGE_JSON.read_text(encoding="utf-8"))
    version = data.get("version")
    if not version:
        print("ERROR: No 'version' field in package.json.", file=sys.stderr)
        sys.exit(1)

    return version


def write_version_json(upstream: str, gf_version: str) -> None:
    """Write the version constants to sources/version.json."""
    payload = {
        "upstream": upstream,
        "gf_version": gf_version,
        "gf_version_string": f"Version {gf_version}",
    }
    VERSION_JSON.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {VERSION_JSON}")
    print(f"  upstream:          {upstream}")
    print(f"  gf_version:        {gf_version}")
    print(f"  gf_version_string: Version {gf_version}")


def check_mode() -> None:
    """Verify version.json is up-to-date with upstream. Exit 1 if stale."""
    upstream = read_upstream_version()
    gf_version = semver_to_gf(upstream)

    if not VERSION_JSON.exists():
        print(f"FAIL: {VERSION_JSON} does not exist. Run sync_version.py first.", file=sys.stderr)
        sys.exit(1)

    existing = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
    if existing.get("upstream") != upstream or existing.get("gf_version") != gf_version:
        print(
            f"FAIL: version.json is stale.\n"
            f"  Expected upstream={upstream}, gf_version={gf_version}\n"
            f"  Got      upstream={existing.get('upstream')}, gf_version={existing.get('gf_version')}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"OK: version.json is up-to-date (upstream={upstream}, gf={gf_version})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync upstream Iosevka version to Google Fonts format."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify version.json is up-to-date; exit 1 if stale.",
    )
    args = parser.parse_args()

    if args.check:
        check_mode()
        return

    upstream = read_upstream_version()
    gf_version = semver_to_gf(upstream)
    write_version_json(upstream, gf_version)


if __name__ == "__main__":
    main()
