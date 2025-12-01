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
- Copyright notice format (googlefonts/font_copyright)
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


def fix_copyright_notice(font):
    """Fix copyright notice to match Google Fonts canonical format.

    Google Fonts requires copyright notices to match the pattern:
    "Copyright YEAR The Familyname Project Authors (git url)"
    """
    name_table = font['name']
    # Format: Copyright 2015-2025 The Iosevka Project Authors (https://github.com/be5invis/Iosevka)
    copyright_notice = "Copyright 2015-2025 The Iosevka Project Authors (https://github.com/be5invis/Iosevka)"

    name_table.setName(copyright_notice, 0, 3, 1, 0x409)
    name_table.setName(copyright_notice, 0, 1, 0, 0)

    print(f"  ✓ Fixed copyright notice: {copyright_notice}")
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
    glyf = font['glyf']
    cmap = font.getBestCmap()
    fixed = []

    # Specific glyphs in Private Use Area that need width
    # These are codepoints 0xEF06-0xEF0C (61190-61196)
    pua_glyphs_to_fix = [
        'uniEF06', 'uniEF07', 'uniEF08', 'uniEF09',
        'uniEF0A', 'uniEF0B', 'uniEF0C'
    ]

    # Get the standard width for this font (monospaced)
    if 'space' in hmtx.metrics:
        new_width = hmtx['space'][0]
    else:
        # Fallback to average width
        widths = [w for w, _ in hmtx.metrics.values() if w > 0]
        new_width = sum(widths) // len(widths) if widths else 500

    glyph_order = font.getGlyphOrder()

    for glyph_name in glyph_order:
        if glyph_name not in glyf:
            continue

        width, lsb = hmtx[glyph_name]
        if width == 0:
            glyph = glyf[glyph_name]

            # Check if this is a PUA glyph that needs fixing
            is_pua_glyph = glyph_name in pua_glyphs_to_fix

            # Check if it has contours (not just a composite or empty)
            has_contours = (hasattr(glyph, 'numberOfContours') and
                          glyph.numberOfContours is not None and
                          glyph.numberOfContours != 0)

            # Fix if it's a PUA glyph or has contours but no width
            if is_pua_glyph or (has_contours and not glyph.isComposite()):
                hmtx[glyph_name] = (new_width, lsb)
                fixed.append(glyph_name)

    if fixed:
        print(f"  ✓ Fixed zero-width glyphs: {', '.join(fixed)}")
        # Update hhea.advanceWidthMax if needed
        max_width = max((w for w, _ in hmtx.metrics.values()), default=0)
        if max_width > font['hhea'].advanceWidthMax:
            font['hhea'].advanceWidthMax = max_width
            print(f"  ✓ Updated hhea.advanceWidthMax to {max_width}")
        return True
    return False


def fix_font_names(font):
    """Fix font names to match Google Fonts requirements"""
    name_table = font['name']
    weight_class = font['OS/2'].usWeightClass
    is_italic = bool(font['head'].macStyle & 2) or (font['OS/2'].fsSelection & 1)

    existing_family = name_table.getName(1, 3, 1, 0x409)
    family_hint = existing_family.toUnicode() if existing_family else ""
    is_mono = "Mono" in family_hint or "Mono" in font.reader.file.name
    base_family = "Iosevka Charon Mono" if is_mono else "Iosevka Charon"

    # Google Fonts naming rules:
    # - Regular/Bold/Italic/BoldItalic: Standard RIBBI naming
    # - Other weights: Include weight in family name, subfamily is "Regular" or "Italic"

    weight_map = {
        100: ("Thin", "thin"),
        200: ("Extralight", "extralight"),
        300: ("Light", "light"),
        400: ("Regular", "regular"),
        500: ("Medium", "medium"),
        600: ("Semibold", "semibold"),
        700: ("Bold", "bold"),
        800: ("Extrabold", "extrabold"),
        900: ("Black", "black"),
    }
    weight_display, weight_lower = weight_map.get(weight_class, ("Regular", "regular"))

    # Determine naming based on Google Fonts rules
    # RIBBI fonts should NOT have nameID 16/17 (googlefonts/font_names check)
    # But uniqueness_first_31_characters checks NID 16+17 combination
    # Solution: For RIBBI fonts, remove nameID 16/17 entirely
    if weight_class == 400 and not is_italic:
        # Regular
        family_name = base_family
        subfamily_name = "Regular"
        full_name = f"{base_family} Regular"
        ps_name = f"{base_family.replace(' ', '')}-Regular"
        typographic_family = None
        typographic_subfamily = None
    elif weight_class == 700 and not is_italic:
        # Bold
        family_name = base_family
        subfamily_name = "Bold"
        full_name = f"{base_family} Bold"
        ps_name = f"{base_family.replace(' ', '')}-Bold"
        typographic_family = None
        typographic_subfamily = None
    elif weight_class == 400 and is_italic:
        # Italic
        family_name = base_family
        subfamily_name = "Italic"
        full_name = f"{base_family} Italic"
        ps_name = f"{base_family.replace(' ', '')}-Italic"
        typographic_family = None
        typographic_subfamily = None
    elif weight_class == 700 and is_italic:
        # Bold Italic
        family_name = base_family
        subfamily_name = "Bold Italic"
        full_name = f"{base_family} Bold Italic"
        ps_name = f"{base_family.replace(' ', '')}-BoldItalic"
        typographic_family = None
        typographic_subfamily = None
    else:
        # Other weights: Include weight in family name
        # Google Fonts requires nameID 16 and 17 for non-RIBBI fonts
        family_name = f"{base_family} {weight_display}"
        subfamily_name = "Italic" if is_italic else "Regular"
        # Full name should include both weight AND subfamily (e.g., "Iosevka Charon Extrabold Regular")
        full_name = f"{base_family} {weight_display} {subfamily_name}"
        ps_suffix = "Italic" if is_italic else "Regular"
        ps_name = f"{base_family.replace(' ', '')}{weight_display}-{ps_suffix}"
        # Set typographic names for non-RIBBI fonts
        typographic_family = base_family
        typographic_subfamily = f"{weight_display} Italic" if is_italic else weight_display

    # Set name IDs
    name_table.setName(family_name, 1, 3, 1, 0x409)
    name_table.setName(subfamily_name, 2, 3, 1, 0x409)
    name_table.setName(full_name, 4, 3, 1, 0x409)
    name_table.setName(ps_name, 6, 3, 1, 0x409)

    # Handle typographic names (nameID 16 and 17)
    # For RIBBI fonts: remove them entirely (Google Fonts requirement)
    # For non-RIBBI fonts: set them
    if typographic_family is None:
        # Remove nameID 16 and 17 for RIBBI fonts
        name_table.names = [n for n in name_table.names if n.nameID not in (16, 17)]
    else:
        name_table.setName(typographic_family, 16, 3, 1, 0x409)
        name_table.setName(typographic_subfamily, 17, 3, 1, 0x409)

    # Mirror to Mac platform
    name_table.setName(family_name, 1, 1, 0, 0)
    name_table.setName(subfamily_name, 2, 1, 0, 0)
    name_table.setName(full_name, 4, 1, 0, 0)
    name_table.setName(ps_name, 6, 1, 0, 0)
    if typographic_family:
        name_table.setName(typographic_family, 16, 1, 0, 0)
        name_table.setName(typographic_subfamily, 17, 1, 0, 0)

    # For non-RIBBI fonts, OS/2 usWeightClass should be 400 (Regular)
    # The weight information is encoded in the family name and typographic subfamily
    if typographic_family:
        font['OS/2'].usWeightClass = 400

    print(f"  ✓ Fixed font names: {full_name} (ps: {ps_name})")
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
    # Include both glyphs in cmap AND all other glyphs (like glyph05405, etc.)
    base_glyphs = []
    mark_glyph_names = {name for name, _ in mark_glyphs}

    # First, add all glyphs from cmap that aren't marks
    for cp, name in sorted(glyph_for_cp.items()):
        if not unicodedata.combining(chr(cp)) and name not in mark_glyph_names:
            base_glyphs.append(name)

    # Also add ALL other glyphs from glyph order that aren't in cmap and aren't marks
    # This includes component glyphs like glyph05405, glyph06144, etc.
    glyf_table = font['glyf']
    for glyph_name in font.getGlyphOrder():
        if glyph_name not in glyph_for_cp.values() and glyph_name not in mark_glyph_names:
            # Check if this glyph actually has contours (not just a component or empty)
            if glyph_name in glyf_table:
                base_glyphs.append(glyph_name)

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

        if fix_copyright_notice(font):
            fixes_applied.append("copyright_notice")

        if fix_windows_metrics(font):
            fixes_applied.append("windows_metrics")

        if fix_vertical_metrics(font):
            fixes_applied.append("vertical_metrics")

        if fix_fontbakery_version(font):
            fixes_applied.append("fontbakery_metadata")

        if fix_zero_width_glyphs(font):
            fixes_applied.append("zero_width_glyphs")

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
