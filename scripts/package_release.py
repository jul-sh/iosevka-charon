#!/usr/bin/env python3
"""Build separate Charon and Caleuche download archives from CI artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


CHARON_FAMILIES = ("iosevkacharon", "iosevkacharonmono")
CALEUCHE_FAMILY = "iosevkacaleuche"
SUBSETS = ("full", "latin-ext", "latin")


def font_files(directory: Path, suffix: str) -> list[Path]:
    files = sorted(directory.rglob(f"*{suffix}"))
    if not files:
        raise ValueError(f"No {suffix} fonts found in {directory}")
    return files


def caleuche_fonts(fonts: Path, webfonts: Path) -> tuple[list[Path], list[Path]]:
    family = fonts / CALEUCHE_FAMILY
    static = sorted(family.glob("*.ttf"))
    variable = sorted((family / "variable").glob("*.ttf"))
    if not static or {p.stem for p in variable} != {
        f"{p.stem}[YTLC,opsz]" for p in static
    }:
        raise ValueError("Caleuche needs a matching opsz/YTLC variable font for every static font")

    webfont_files: list[Path] = []
    for subset in SUBSETS:
        subset_family = webfonts / subset / CALEUCHE_FAMILY
        static_webfonts = sorted(subset_family.glob("*.woff2"))
        variable_webfonts = sorted((subset_family / "variable").glob("*.woff2"))
        if {p.stem for p in static_webfonts} != {p.stem for p in static} or {
            p.stem for p in variable_webfonts
        } != {p.stem for p in variable}:
            raise ValueError(f"Incomplete Caleuche {subset} webfonts")
        webfont_files.extend(static_webfonts + variable_webfonts)
    return static + variable, webfont_files


def write_archive(path: Path, entries: list[tuple[Path, Path]]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for source, name in sorted(entries, key=lambda entry: str(entry[1])):
            archive.write(source, name)
    print(f"Created {path} ({len(entries)} files)")


def package(fonts: Path, webfonts: Path, output: Path, license_file: Path, article: Path | None) -> None:
    if not license_file.is_file():
        raise ValueError(f"Missing license: {license_file}")
    output.mkdir(parents=True, exist_ok=True)

    charon_fonts = [p for family in CHARON_FAMILIES for p in font_files(fonts / family, ".ttf")]
    charon_webfonts = [
        p
        for subset in SUBSETS
        for family in CHARON_FAMILIES
        for p in font_files(webfonts / subset / family, ".woff2")
    ]
    caleuche_ttf, caleuche_woff2 = caleuche_fonts(fonts, webfonts)

    general = [(p, p.relative_to(fonts)) for p in charon_fonts]
    general.append((license_file, Path("OFL.txt")))
    if article is not None and article.is_file():
        general.append((article, Path("ARTICLE.en_us.html")))
    write_archive(output / "iosevka-charon.zip", general)

    web = [(p, p.relative_to(webfonts)) for p in charon_webfonts]
    web.append((license_file, Path("OFL.txt")))
    write_archive(output / "iosevka-charon-webfonts.zip", web)

    caleuche = [(p, Path("fonts") / p.relative_to(fonts)) for p in caleuche_ttf]
    caleuche.extend((p, Path("webfonts") / p.relative_to(webfonts)) for p in caleuche_woff2)
    caleuche.append((license_file, Path("OFL.txt")))
    write_archive(output / "iosevka-caleuche.zip", caleuche)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument("--webfonts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license", type=Path, required=True)
    parser.add_argument("--article", type=Path)
    args = parser.parse_args()
    package(args.fonts, args.webfonts, args.output, args.license, args.article)


if __name__ == "__main__":
    main()
