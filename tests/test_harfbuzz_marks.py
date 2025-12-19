#!/usr/bin/env python3
"""
Comprehensive HarfBuzz test for mark positioning divergence detection.

Tests ALL combining marks in the font against base characters to detect
any positioning differences between post-processed and base fonts.
Uses multiprocessing for speed.
"""

import sys
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

import uharfbuzz as hb
from fontTools.ttLib import TTFont


# Paths
GF_FONT = "fonts/iosevkacharon/IosevkaCharon-Regular.ttf"
BASE_FONT = "unprocessed_fonts/IosevkaCharon/ttf/IosevkaCharon-Regular.ttf"


def load_font_data(font_path: str) -> bytes:
    """Load font file into memory."""
    with open(font_path, 'rb') as f:
        return f.read()


def shape_text(font_data: bytes, text: str) -> list[tuple[int, int]]:
    """Shape text and return glyph positions."""
    face = hb.Face(font_data)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return [(pos.x_offset, pos.y_offset) for pos in buf.glyph_positions]


def get_combining_marks(font_path: str) -> list[tuple[int, str]]:
    """Get all combining marks from the font's cmap."""
    font = TTFont(font_path)
    cmap = font.getBestCmap()

    marks = []
    for cp, glyph_name in cmap.items():
        # Unicode combining marks are in these ranges:
        # 0x0300-0x036F: Combining Diacritical Marks
        # 0x1AB0-0x1AFF: Combining Diacritical Marks Extended
        # 0x1DC0-0x1DFF: Combining Diacritical Marks Supplement
        # 0x20D0-0x20FF: Combining Diacritical Marks for Symbols
        # 0xFE20-0xFE2F: Combining Half Marks
        if (0x0300 <= cp <= 0x036F or
            0x1AB0 <= cp <= 0x1AFF or
            0x1DC0 <= cp <= 0x1DFF or
            0x20D0 <= cp <= 0x20FF or
            0xFE20 <= cp <= 0xFE2F):
            marks.append((cp, glyph_name))

    font.close()
    return marks


def get_base_chars() -> list[str]:
    """Get a representative set of base characters to test with marks."""
    return [
        # Latin
        'A', 'E', 'I', 'O', 'U', 'a', 'e', 'i', 'o', 'u',
        'B', 'C', 'D', 'N', 'P', 'X', 'n', 'p', 'x',
        # Extended Latin
        'ü', 'ö', 'ä', 'ẩ', 'ǒ',
        # Cyrillic
        'А', 'О', 'Е', 'а', 'о', 'е', 'р', 'ӷ',
        # Greek
        'Α', 'Ο', 'α', 'ο',
    ]


def test_single_combination(args: tuple) -> tuple[str, bool, str]:
    """Test a single base+mark combination. Returns (text, passed, detail)."""
    base_char, mark_cp, gf_data, base_data = args
    text = base_char + chr(mark_cp)

    try:
        gf_pos = shape_text(gf_data, text)
        base_pos = shape_text(base_data, text)

        if gf_pos == base_pos:
            return (text, True, "")
        else:
            return (text, False, f"GF={gf_pos} vs Base={base_pos}")
    except Exception as e:
        return (text, False, f"Error: {e}")


def test_stacked_marks(gf_data: bytes, base_data: bytes) -> list[tuple[str, bool, str]]:
    """Test stacked combining marks (multiple marks on one base)."""
    results = []

    # Common stacked mark combinations
    stacked_tests = [
        ("ü̃́", "u + diaeresis + tilde + acute"),
        ("ä̃́", "a + diaeresis + tilde + acute"),
        ("ö̃́", "o + diaeresis + tilde + acute"),
        ("ẩ̄", "a-circumflex-hook + macron"),
        ("ǒ̄", "o-caron + macron"),
        ("р̌̄", "Cyrillic r + caron + macron"),
    ]

    for text, desc in stacked_tests:
        try:
            gf_pos = shape_text(gf_data, text)
            base_pos = shape_text(base_data, text)
            passed = gf_pos == base_pos
            detail = "" if passed else f"GF={gf_pos} vs Base={base_pos}"
            results.append((f"{text} ({desc})", passed, detail))
        except Exception as e:
            results.append((f"{text} ({desc})", False, f"Error: {e}"))

    return results


def main():
    start_time = time.time()

    print("=" * 70)
    print("Comprehensive HarfBuzz Mark Positioning Test")
    print("=" * 70)

    # Check fonts exist
    if not os.path.exists(GF_FONT):
        print(f"Error: GF font not found: {GF_FONT}")
        return 1
    if not os.path.exists(BASE_FONT):
        print(f"Error: Base font not found: {BASE_FONT}")
        return 1

    # Load font data
    print("\nLoading fonts...")
    gf_data = load_font_data(GF_FONT)
    base_data = load_font_data(BASE_FONT)

    # Get combining marks
    print("Scanning for combining marks...")
    marks = get_combining_marks(GF_FONT)
    base_chars = get_base_chars()

    print(f"Found {len(marks)} combining marks")
    print(f"Testing with {len(base_chars)} base characters")
    print(f"Total combinations: {len(marks) * len(base_chars)}")

    # Build test cases
    test_cases = []
    for base_char in base_chars:
        for mark_cp, _ in marks:
            test_cases.append((base_char, mark_cp, gf_data, base_data))

    # Run tests in parallel
    print(f"\nRunning tests with {os.cpu_count()} parallel workers...")

    passed = 0
    failed = 0
    failures = []

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(test_single_combination, tc): tc for tc in test_cases}

        for future in as_completed(futures):
            text, success, detail = future.result()
            if success:
                passed += 1
            else:
                failed += 1
                failures.append((text, detail))

    # Test stacked marks
    print("\nTesting stacked mark combinations...")
    stacked_results = test_stacked_marks(gf_data, base_data)
    for text, success, detail in stacked_results:
        if success:
            passed += 1
            print(f"  ✓ {text}")
        else:
            failed += 1
            failures.append((text, detail))
            print(f"  ✗ {text}: {detail}")

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print(f"Time: {elapsed:.2f}s ({len(test_cases) + len(stacked_results)} tests)")

    if failures:
        print(f"\nFirst 20 failures:")
        for text, detail in failures[:20]:
            print(f"  ✗ {repr(text)}: {detail}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")
    else:
        print("\n✓ All tests PASSED! No mark positioning divergence detected.")

    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
