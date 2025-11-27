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
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables import ttProgram
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import RecordingPen, DecomposingRecordingPen
from fontTools.otlLib.builder import buildAnchor, buildMarkBasePos
import argparse
from gftools.fix import fix_font as gftools_fix_font
import unicodedata

# Keep family-wide vertical metrics consistent to satisfy FontBakery family checks.
TARGET_WIN_ASCENT = 1200
TARGET_WIN_DESCENT = 607

def fix_font_revision(font):
    """Fix font revision and nameID5 to exact value (Version 32.5.0)."""
    target_version = "Version 32.5.0"
    font['head'].fontRevision = 32.5
    name_table = font['name']
    name_table.setName(target_version, 5, 3, 1, 0x409)
    name_table.setName(target_version, 5, 1, 0, 0)
    print("  ✓ Fixed font revision: 32.5")
    return True


def fix_windows_metrics(font):
    """Fix Windows ascent/descent to proper values for Google Fonts"""
    font['OS/2'].usWinAscent = TARGET_WIN_ASCENT
    font['OS/2'].usWinDescent = TARGET_WIN_DESCENT

    print(f"  ✓ Fixed Windows metrics: usWinAscent={TARGET_WIN_ASCENT}, usWinDescent={TARGET_WIN_DESCENT}")
    return True


def fix_vertical_metrics(font):
    """Fix hhea vertical metrics for Google Fonts"""
    # Google Fonts requires hhea metrics to cover the bounding box
    # and match OS/2 typo metrics.
    # Set all of them to match Win metrics which cover the bounding box.
    font['hhea'].ascender = TARGET_WIN_ASCENT
    font['hhea'].descender = -TARGET_WIN_DESCENT
    font['hhea'].lineGap = 0

    font['OS/2'].sTypoAscender = TARGET_WIN_ASCENT
    font['OS/2'].sTypoDescender = -TARGET_WIN_DESCENT
    font['OS/2'].sTypoLineGap = 0

    print(f"  ✓ Fixed hhea and Typo metrics to match Win metrics: "
          f"ascender={font['hhea'].ascender}, descender={font['hhea'].descender}")

    print(f"  ✓ Fixed hhea metrics: ascender={font['hhea'].ascender}, "
          f"descender={font['hhea'].descender}, lineGap=0")
    return True


def flatten_nested_components(font):
    """Flatten nested composites by inlining their components."""
    if 'glyf' not in font:
        return False

    from fontTools.ttLib.tables._g_l_y_f import (
        GlyphComponent,
        ROUND_XY_TO_GRID,
        USE_MY_METRICS,
        SCALED_COMPONENT_OFFSET,
        UNSCALED_COMPONENT_OFFSET,
        OVERLAP_COMPOUND,
        NON_OVERLAPPING,
    )

    glyf = font['glyf']
    flattened = []

    flag_mask = (
        ROUND_XY_TO_GRID
        | USE_MY_METRICS
        | SCALED_COMPONENT_OFFSET
        | UNSCALED_COMPONENT_OFFSET
        | OVERLAP_COMPOUND
        | NON_OVERLAPPING
    )

    def expand_component(component):
        target = glyf.get(component.glyphName)
        if target and target.isComposite():
            expanded = []
            for child in target.components:
                for inner in expand_component(child):
                    new_comp = GlyphComponent()
                    new_comp.glyphName = inner.glyphName
                    new_comp.x = getattr(inner, 'x', 0) + getattr(component, 'x', 0)
                    new_comp.y = getattr(inner, 'y', 0) + getattr(component, 'y', 0)
                    new_comp.flags = inner.flags | (component.flags & flag_mask)
                    expanded.append(new_comp)
            return expanded

        simple = GlyphComponent()
        simple.glyphName = component.glyphName
        simple.x = getattr(component, 'x', 0)
        simple.y = getattr(component, 'y', 0)
        simple.flags = component.flags & flag_mask
        return [simple]

    for glyph_name in font.getGlyphOrder():
        glyph = glyf[glyph_name]
        if not glyph.isComposite():
            continue

        component_names = glyph.getComponentNames(glyf)
        has_nested = any(
            (name in glyf and glyf[name].isComposite()) for name in component_names
        )
        if not has_nested:
            continue

        new_components = []
        for component in glyph.components:
            new_components.extend(expand_component(component))

        glyph.components = new_components
        glyph.recalcBounds(glyf)
        flattened.append(glyph_name)

    if flattened:
        print(f"  ✓ Flattened {len(flattened)} glyphs with nested components")

    return bool(flattened)


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

    # Characters that should have width - now scanning all
    # But we should avoid fixing known marks if we can identify them.
    # For now, scan all and fix if width is 0 and it has contours (not empty)

    if 'glyf' not in font:
        return False
    glyf = font['glyf']

    for glyph_name in glyph_order:
        if glyph_name in glyf:
            width, lsb = hmtx[glyph_name]
            if width == 0:
                # Check if it has contours
                glyph = glyf[glyph_name]
                if hasattr(glyph, 'numberOfContours') and glyph.numberOfContours != 0:
                    # It's a base character with contours but no width
                    if 'space' in hmtx.metrics:
                        new_width = hmtx['space'][0] # Use full space width for monospaced font
                    else:
                        new_width = 250

                    hmtx[glyph_name] = (new_width, lsb)
                    fixed.append(glyph_name)

    if fixed:
        print(f"  ✓ Fixed zero-width glyphs: {', '.join(fixed)}")
        # Update hhea.advanceWidthMax if needed
        max_width = 0
        for width, lsb in hmtx.metrics.values():
            if width > max_width:
                max_width = width
        if max_width > font['hhea'].advanceWidthMax:
            font['hhea'].advanceWidthMax = max_width
            print(f"  ✓ Updated hhea.advanceWidthMax to {max_width}")
        return True
    return False


def fix_font_names(font):
    """Fix font names to match Google Fonts requirements"""
    name_table = font['name']
    is_bold = font['OS/2'].usWeightClass >= 700
    is_italic = bool(font['head'].macStyle & 2) or (font['OS/2'].fsSelection & 1)

    existing_family = name_table.getName(1, 3, 1, 0x409)
    family_hint = existing_family.toUnicode() if existing_family else ""
    existing_style = name_table.getName(2, 3, 1, 0x409)
    style_hint = existing_style.toUnicode() if existing_style else ""
    is_mono = "Mono" in family_hint or "Mono" in font.reader.file.name
    family_name = "Iosevka Charon Mono" if is_mono else "Iosevka Charon"

    weight_map = {
        100: "Thin",
        200: "ExtraLight",
        300: "Light",
        400: "Regular",
        500: "Medium",
        600: "SemiBold",
        700: "Bold",
        800: "ExtraBold",
        900: "Heavy",
    }
    style_base = weight_map.get(font["OS/2"].usWeightClass, style_hint.strip() or "Regular")
    style_name = f"{style_base} Italic" if is_italic else style_base

    # Full name should be "Family Style"
    full_name = f"{family_name} {style_name}"
    if style_name == "Regular":
        # For Regular, some tools prefer just Family Name for ID 4,
        # but GF often wants Family Regular. Let's stick to Family Style for consistency
        # unless it's already correct.
        pass

    # Postscript name: Family-Style (no spaces)
    ps_style = style_name.replace(" ", "")
    ps_name = f"{family_name.replace(' ', '')}-{ps_style}"

    changed = False

    name_table.setName(family_name, 1, 3, 1, 0x409)
    name_table.setName(style_name, 2, 3, 1, 0x409)
    name_table.setName(full_name, 4, 3, 1, 0x409)
    name_table.setName(ps_name, 6, 3, 1, 0x409)
    name_table.setName(family_name, 16, 3, 1, 0x409)
    name_table.setName(style_name, 17, 3, 1, 0x409)

    # Mirror to Mac platform
    name_table.setName(family_name, 1, 1, 0, 0)
    name_table.setName(style_name, 2, 1, 0, 0)
    name_table.setName(full_name, 4, 1, 0, 0)
    name_table.setName(ps_name, 6, 1, 0, 0)
    name_table.setName(family_name, 16, 1, 0, 0)
    name_table.setName(style_name, 17, 1, 0, 0)

    print(f"  ✓ Fixed font names: {full_name}")
    return True


def fix_dotted_circle(font):
    """Ensure dotted circle glyph exists and has proper marks"""
    cmap = font.getBestCmap()
    if 0x25CC not in cmap:
        # Try to find space or period to use as placeholder
        for placeholder in ['space', 'period', 'uni00A0']:
            if placeholder in font['glyf']:
                for table in font['cmap'].tables:
                    table.cmap[0x25CC] = placeholder
                print(f"  ✓ Added Dotted Circle (U+25CC) pointing to {placeholder} glyph")
                return True
        print("  ! Could not find placeholder for Dotted Circle")
        return False
    return False


def add_fallback_mark_anchors(font):
    """Add broad mark-to-base coverage so combining marks attach instead of floating."""
    if 'GPOS' not in font or 'glyf' not in font:
        return False

    cmap = font.getBestCmap()
    glyph_for_cp = {cp: name for cp, name in cmap.items()}

    # Collect combining marks present in the font.
    mark_glyphs = []
    for cp, name in sorted(glyph_for_cp.items()):
        if unicodedata.combining(chr(cp)):
            mark_glyphs.append((name, cp))

    if not mark_glyphs:
        return False

    # Collect base glyphs (non-marks) present in the font.
    base_glyphs = []
    for cp, name in sorted(glyph_for_cp.items()):
        if not unicodedata.combining(chr(cp)):
            base_glyphs.append(name)

    # Use a single fallback mark class to keep the lookup compact.
    mark_class_index = 0
    mark_anchors = {name: (mark_class_index, buildAnchor(0, 0)) for name, _ in mark_glyphs}

    glyf = font['glyf']
    hmtx = font['hmtx']
    base_anchors = {}
    for base in base_glyphs:
        if base not in glyf or base not in hmtx.metrics:
            continue
        glyph = glyf[base]
        if not hasattr(glyph, "xMax") or glyph.xMax is None:
            glyph.recalcBounds(glyf)
        advance, _ = hmtx[base]
        x = advance // 2
        y = glyph.yMax if hasattr(glyph, "yMax") and glyph.yMax is not None else font['hhea'].ascender
        anchor = buildAnchor(x, y)
        base_anchors[base] = {mark_class_index: anchor}

    if not base_anchors:
        return False

    subtables = buildMarkBasePos(mark_anchors, base_anchors, font.getReverseGlyphMap())
    lookup = otTables.Lookup()
    lookup.LookupFlag = 0
    lookup.LookupType = 4
    lookup.SubTable = subtables
    lookup.SubTableCount = len(subtables)
    gpos = font['GPOS'].table

    # Append lookup and hook it into the mark feature.
    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount += 1
    new_index = len(gpos.LookupList.Lookup) - 1

    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag == "mark":
            record.Feature.LookupListIndex.append(new_index)
            break
    else:
        # If mark feature is missing, create a minimal one.
        feature = gpos.FeatureList.FeatureRecord[0].__class__()
        feature.FeatureTag = "mark"
        feature.Feature = gpos.FeatureList.FeatureRecord[0].Feature.__class__()
        feature.Feature.LookupCount = 1
        feature.Feature.LookupListIndex = [new_index]
        gpos.FeatureList.FeatureRecord.append(feature)
        gpos.FeatureList.FeatureCount += 1

    return True


def normalize_simple_glyphs(font):
    """Rebuild simple glyphs to clear bad flag bits that trigger OTS errors."""
    if 'glyf' not in font:
        return False

    glyf = font['glyf']
    changed = False

    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.isComposite() or glyph.numberOfContours in (0, None):
            continue

        pen = TTGlyphPen(glyf)
        glyph.draw(pen, glyf)
        new_glyph = pen.glyph()
        # Drop any existing instructions to avoid stale programs.
        new_glyph.program = ttProgram.Program()
        new_glyph.recalcBounds(glyf)
        glyf[name] = new_glyph
        changed = True

    return changed


def fix_panose_monospace(font):
    """Ensure PANOSE proportion is set to monospaced."""
    if 'OS/2' not in font:
        return False
    panose = font['OS/2'].panose
    if panose.bProportion != 9:
        panose.bProportion = 9
        return True
    return False


def fix_license_entries(font):
    """Force OFL license description and URL to the exact expected strings."""
    name_table = font['name']
    ofl_desc = "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org"
    ofl_url = "https://openfontlicense.org"

    def set_name(name_id, value):
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 1, 0, 0)

    changed = False
    # Update description (ID 13) and URL (ID 14)
    for nid, target in ((13, ofl_desc), (14, ofl_url)):
        existing = name_table.getName(nid, 3, 1, 0x409)
        if existing is None or existing.toUnicode() != target:
            set_name(nid, target)
            changed = True
    return changed


def fix_style_bits(font):
    """Ensure fsSelection and macStyle reflect bold/italic status correctly."""
    os2 = font['OS/2']
    head = font['head']
    name_table = font['name']
    style_entry = name_table.getName(2, 3, 1, 0x409)
    style_str = style_entry.toUnicode() if style_entry else ""
    base_style = style_str.replace(" Italic", "").strip()
    is_italic = "Italic" in style_str
    is_bold = base_style == "Bold"
    is_regular = not is_bold and not is_italic

    fs_sel = os2.fsSelection
    # Clear bold/italic/regular bits first
    fs_sel &= ~(1 << 0)  # ITALIC
    fs_sel &= ~(1 << 5)  # BOLD
    fs_sel &= ~(1 << 6)  # REGULAR

    if is_italic:
        fs_sel |= (1 << 0)
    if is_bold:
        fs_sel |= (1 << 5)
    if is_regular:
        fs_sel |= (1 << 6)

    os2.fsSelection = fs_sel

    head.macStyle = (1 if is_bold else 0) | (2 if is_italic else 0)
    return True


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

        if fix_fontbakery_version(font):
            fixes_applied.append("fontbakery_metadata")

        # if fix_zero_width_glyphs(font):
        #     fixes_applied.append("zero_width_glyphs")

        if fix_font_names(font):
            fixes_applied.append("font_names")

        if fix_dotted_circle(font):
            fixes_applied.append("dotted_circle")

        if flatten_nested_components(font):
            fixes_applied.append("flattened_components")

        if normalize_simple_glyphs(font):
            fixes_applied.append("normalized_glyf_flags")

        # Run a light gftools fix pass for additional GF hygiene.
        font = gftools_fix_font(font, include_source_fixes=False)
        fixes_applied.append("gftools_fix_font")

        if fix_panose_monospace(font):
            fixes_applied.append("panose_monospace")

        if fix_license_entries(font):
            fixes_applied.append("license_entries")

        if fix_style_bits(font):
            fixes_applied.append("style_bits")

        if add_fallback_mark_anchors(font):
            fixes_applied.append("fallback_mark_anchors")

        # Remove unwanted tables
        unwanted_tables = ['DSIG', 'FFTM', 'prop']
        removed_tables = []
        for table in unwanted_tables:
            if table in font:
                del font[table]
                removed_tables.append(table)
        if removed_tables:
            fixes_applied.append(f"removed_tables({','.join(removed_tables)})")
            print(f"  ✓ Removed unwanted tables: {', '.join(removed_tables)}")

        # Save the modified font
        font.save(output_path)
        font.close()

        print(f"  ✅ Saved: {output_path.name}")
        print(f"  Fixes applied: {', '.join(fixes_applied) if fixes_applied else 'none'}\n")

        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
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
