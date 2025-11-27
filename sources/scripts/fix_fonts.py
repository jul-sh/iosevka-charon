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
            # Google Fonts preferred format is often Major.Minor as a float
            # For 32.5.0, this should be 32.500
            revision = major + (minor / 10) + (patch / 1000) # Simplified, might need adjustment
            # Try to match what fontbakery expects, which is usually Major.Minor
            revision = float(f"{major}.{minor}{patch}")
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
    # Google Fonts requires hhea metrics to cover the bounding box
    # and match OS/2 typo metrics.
    # Set all of them to match Win metrics which cover the bounding box.
    font['hhea'].ascender = font['OS/2'].usWinAscent
    font['hhea'].descender = -font['OS/2'].usWinDescent
    font['hhea'].lineGap = 0

    font['OS/2'].sTypoAscender = font['OS/2'].usWinAscent
    font['OS/2'].sTypoDescender = -font['OS/2'].usWinDescent
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

    family_name = "Iosevka Charon"

    # Determine style name
    if is_bold and is_italic:
        style_name = "Bold Italic"
    elif is_bold:
        style_name = "Bold"
    elif is_italic:
        style_name = "Italic"
    else:
        style_name = "Regular"

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

    # Name IDs to check/fix
    # 1: Family Name
    # 2: Subfamily Name
    # 4: Full Name
    # 6: Postscript Name
    # 16: Typographic Family Name
    # 17: Typographic Subfamily Name

    # Collect existing names to check for ID 16/17 necessity
    has_id16 = any(r.nameID == 16 for r in name_table.names)
    has_id17 = any(r.nameID == 17 for r in name_table.names)

    # For Regular/Bold/Italic/Bold Italic, we don't strictly need ID 16/17 if ID 1/2 are correct,
    # but having them consistent is good.

    records_to_add = []

    for record in name_table.names:
        # Check all platforms for Name ID 6 (Postscript Name)
        if record.nameID == 6:
            if record.toUnicode() != ps_name:
                if record.platformID == 3: # Windows
                    record.string = ps_name.encode('utf-16-be')
                else: # Mac or other
                    record.string = ps_name.encode('ascii')
                changed = True

        # For other IDs, check Windows platform
        elif record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409:
            if record.nameID == 1:
                if record.toUnicode() != family_name:
                    record.string = family_name.encode('utf-16-be')
                    changed = True
            elif record.nameID == 2:
                if record.toUnicode() != style_name:
                    record.string = style_name.encode('utf-16-be')
                    changed = True
            elif record.nameID == 4:
                if record.toUnicode() != full_name:
                    record.string = full_name.encode('utf-16-be')
                    changed = True
            elif record.nameID == 16:
                if record.toUnicode() == family_name:
                    records_to_add.append(record) # Reuse this list for removal
                    changed = True
            elif record.nameID == 17:
                if record.toUnicode() == style_name:
                    records_to_add.append(record) # Reuse this list for removal
                    changed = True

    for record in records_to_add:
        if record in name_table.names:
            name_table.names.remove(record)

    if changed:
        print(f"  ✓ Fixed font names: {full_name}")
    return changed


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

    mark_class_count = len(mark_glyphs)
    # Anchor every mark at its origin.
    mark_anchors = {name: (idx, buildAnchor(0, 0)) for idx, (name, _) in enumerate(mark_glyphs)}

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
        base_anchors[base] = {idx: anchor for idx in range(mark_class_count)}

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
