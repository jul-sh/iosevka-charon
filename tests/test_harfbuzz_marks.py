#!/usr/bin/env python3
"""
HarfBuzz-based test to verify mark positioning in post-processed fonts.

This test ensures that combining mark stacking (like ü̃́) produces identical
positioning between the post-processed Google Fonts version and the base font.
"""

import sys
import uharfbuzz as hb
from fontTools.ttLib import TTFont


def get_glyph_positions(font_path: str, text: str) -> list[tuple[int, int]]:
    """Shape text using HarfBuzz and return glyph positions."""
    with open(font_path, 'rb') as f:
        face = hb.Face(f.read())
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return [(pos.x_offset, pos.y_offset) for pos in buf.glyph_positions]

# Test cases derived from font-comparison.py - characters that commonly regress
# Format: (description, text)
TEST_CASES = [
    # Stacked combining marks (the original problem case)
    ("ü̃́ - triple stacked marks (diaeresis + tilde + acute)", "ü̃́"),
    ("nüxü̃́ - Vietnamese-style stacking", "nüxü̃́"),

    # Below-base combining marks
    ("X̲ - combining low line", "X̲"),
    ("N̰ - combining tilde below", "N̰"),
    ("a̱ - combining macron below", "a̱"),
    ("p̱ - combining macron below on p", "p̱"),
    ("ɨ̱ - combining macron below on barred i", "ɨ̱"),

    # Above-base combining marks
    ("ɔ̌ - combining caron", "ɔ̌"),
    ("ɔ̂ - combining circumflex", "ɔ̂"),
    ("р̌ - Cyrillic with caron", "р̌"),
    ("ǒ - o with caron", "ǒ"),
    ("ǐ - i with caron", "ǐ"),
    ("ǔ - u with caron", "ǔ"),

    # Vietnamese tones
    ("ẩ - Vietnamese a with circumflex and hook", "ẩ"),
    ("phẩm - Vietnamese word", "phẩm"),

    # Precomposed diacritics (should be stable)
    ("à á â ä æ ã å ā - precomposed Latin", "à á â ä æ ã å ā"),
    ("ç è é ê ë - more precomposed", "ç è é ê ë"),
    ("Åtta - Swedish", "Åtta"),

    # Cyrillic with diacritics
    ("Арганізацыі - Belarusian", "Арганізацыі"),
    ("ӷавргуйныр̌кир̌ - Cyrillic with combining marks", "ӷавргуйныр̌кир̌"),

    # Kazakh
    ("үйелменінің - Kazakh", "үйелменінің"),
    ("құқықтарының - Kazakh with descenders", "құқықтарының"),
    ("Ұлттар Әр Құлдық - Kazakh phrase", "Ұлттар Әр Құлдық"),

    # African languages with combining marks
    ("bɔŋɔ̌ - African language marks", "bɔŋɔ̌"),
    ("Enyiń - with acute", "Enyiń"),
    ("mpɔ̂ - with circumflex", "mpɔ̂"),
    ("Ṱhalutshezo - Venda", "Ṱhalutshezo"),

    # Edge cases
    ("malɇ - barred e", "malɇ"),
    ("éyaltai - simple acute", "éyaltai"),
]


def test_mark_positioning():
    """Test that mark positions match between GF and base fonts."""
    gf_font = "fonts/iosevkacharon/IosevkaCharon-Regular.ttf"
    base_font = "general_use_fonts/IosevkaCharon/ttf/IosevkaCharon-Regular.ttf"

    passed = 0
    failed = 0
    failures = []

    print("=" * 60)
    print("HarfBuzz Mark Positioning Test")
    print("=" * 60)

    for desc, text in TEST_CASES:
        gf_pos = get_glyph_positions(gf_font, text)
        base_pos = get_glyph_positions(base_font, text)

        if gf_pos == base_pos:
            passed += 1
            print(f"✓ {desc}")
        else:
            failed += 1
            failures.append((desc, gf_pos, base_pos))
            print(f"✗ {desc}")
            print(f"    GF:   {gf_pos}")
            print(f"    Base: {base_pos}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("All tests PASSED! Mark positioning matches base font.")
    else:
        print("\nFailed tests indicate post-processing changed mark positioning.")
        print("This may cause visual differences compared to the base font.")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(test_mark_positioning())
