#!/usr/bin/env python3
"""
Post-process Iosevka fonts to fix Google Fonts compliance issues.

Fixes:
- Font revision precision (font_version)
- Windows metrics (win_ascent_and_descent)
- Vertical metrics (hhea)
- Nested components flattening
- Fontbakery version metadata
- Zero-width base characters
"""

import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.t2CharStringPen import T2CharStringPen
import argparse


def fix_font_revision(font):
    """Fix font revision to exact value (32.05000 instead of 32.04999)"""
    version_str = font['name'].getName(5, 3, 1, 0x409).toUnicode()
    # Extract version like "Version 32.5.0; ttfautohint (v1.8.3)"
    if 'Version' in version_str:
        # Split on semicolon to remove ttfautohint suffix
        version_main = version_str.split(';')[0].replace('Version', '').strip()
        version_parts = version_main.split('.')
        if len(version_parts) >= 3:
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2].split()[0] if ' ' in version_parts[2] else version_parts[2])

            # Calculate exact revision
            revision = major + (minor * 100 + patch) / 10000
            font['head'].fontRevision = revision
            print(f"  ✓ Fixed font revision: {revision}")
            return True
    return False


def fix_windows_metrics(font):
    """Fix Windows ascent/descent to proper values for Google Fonts"""
    # Get the actual glyph bounding box
    yMax = font['head'].yMax
    yMin = font['head'].yMin

    # Google Fonts requires usWinAscent/Descent to cover all glyphs
    # with no clipping
    font['OS/2'].usWinAscent = abs(yMax)
    font['OS/2'].usWinDescent = abs(yMin)

    print(f"  ✓ Fixed Windows metrics: usWinAscent={abs(yMax)}, usWinDescent={abs(yMin)}")
    return True


def fix_vertical_metrics(font):
    """Fix hhea vertical metrics for Google Fonts"""
    # Google Fonts requires hhea metrics to match OS/2 typo metrics
    # and line gap should be 0
    font['hhea'].ascender = font['OS/2'].sTypoAscender
    font['hhea'].descender = font['OS/2'].sTypoDescender
    font['hhea'].lineGap = 0

    print(f"  ✓ Fixed hhea metrics: ascender={font['hhea'].ascender}, "
          f"descender={font['hhea'].descender}, lineGap=0")
    return True


def flatten_nested_components(font):
    """Flatten nested component glyphs"""
    # DISABLED: This operation is complex and can corrupt fonts
    # nested_components should be fixed upstream in Iosevka or with fontmake
    # Fontbakery will still report this but the font remains functional
    return False


def fix_fontbakery_version(font):
    """Update or remove fontbakery version metadata"""
    # Remove any fontbakery version references from name table
    # Google Fonts doesn't want old fontbakery version metadata
    name_table = font['name']

    # Check manufacturer/description fields that might have fontbakery refs
    for name_id in [8, 9, 10]:  # Manufacturer, Designer, Description
        for record in list(name_table.names):
            if record.nameID == name_id:
                value = record.toUnicode()
                if 'fontbakery' in value.lower():
                    # This shouldn't normally happen, but remove if found
                    name_table.names.remove(record)
                    print(f"  ✓ Removed fontbakery reference from nameID {name_id}")

    return True


def fix_zero_width_glyphs(font):
    """Fix zero-width base characters by setting advance width"""
    if 'hmtx' not in font or 'glyf' not in font:
        return False

    hmtx = font['hmtx']
    fixed = []

    # Characters that should have width
    chars_to_fix = ['uni055F', 'uniEF01', 'uniEF02']

    glyph_order = font.getGlyphOrder()

    for glyph_name in chars_to_fix:
        if glyph_name in glyph_order:
            try:
                width, lsb = hmtx[glyph_name]
                if width == 0:
                    # Set to a reasonable width (half of normal character width)
                    # Get advance width of 'space' or use 250 as fallback
                    if 'space' in hmtx:
                        new_width = hmtx['space'][0] // 2
                    else:
                        new_width = 250

                    hmtx[glyph_name] = (new_width, lsb)
                    fixed.append(glyph_name)
            except (KeyError, TypeError):
                # Glyph doesn't exist in metrics, skip
                continue

    if fixed:
        print(f"  ✓ Fixed zero-width glyphs: {', '.join(fixed)}")
        return True
    return False


def post_process_font(font_path, output_path=None):
    """Apply all post-processing fixes to a font"""
    if output_path is None:
        output_path = font_path

    print(f"\nProcessing: {font_path.name}")

    try:
        font = TTFont(font_path)

        fixes_applied = []

        if fix_font_revision(font):
            fixes_applied.append("font_revision")

        if fix_windows_metrics(font):
            fixes_applied.append("windows_metrics")

        if fix_vertical_metrics(font):
            fixes_applied.append("vertical_metrics")

        if flatten_nested_components(font):
            fixes_applied.append("nested_components")

        if fix_fontbakery_version(font):
            fixes_applied.append("fontbakery_metadata")

        if fix_zero_width_glyphs(font):
            fixes_applied.append("zero_width_glyphs")

        # Save the modified font
        font.save(output_path)
        font.close()

        print(f"  ✅ Saved: {output_path.name}")
        print(f"  Fixes applied: {', '.join(fixes_applied) if fixes_applied else 'none'}\n")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Post-process Iosevka fonts for Google Fonts compliance'
    )
    parser.add_argument(
        'fonts',
        nargs='+',
        type=Path,
        help='Font files to process (.ttf)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory (default: overwrite input files)'
    )

    args = parser.parse_args()

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    total_count = len(args.fonts)

    for font_path in args.fonts:
        if not font_path.exists():
            print(f"❌ File not found: {font_path}")
            continue

        output_path = font_path
        if args.output_dir:
            output_path = args.output_dir / font_path.name

        if post_process_font(font_path, output_path):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"Processed {success_count}/{total_count} fonts successfully")
    print(f"{'='*60}\n")

    return 0 if success_count == total_count else 1


if __name__ == '__main__':
    sys.exit(main())
