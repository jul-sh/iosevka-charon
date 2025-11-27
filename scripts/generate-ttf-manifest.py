#!/usr/bin/env python3

import json
from pathlib import Path


def main() -> None:
    root = Path("out")
    manifest = [str(path.relative_to(root)) for path in (root / "ttf").rglob("*.ttf")]
    (root / "ttf_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
