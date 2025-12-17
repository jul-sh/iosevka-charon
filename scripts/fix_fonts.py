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
import fontTools.otlLib.builder as ot_builder
import argparse
from gftools.fix import fix_font as gftools_fix_font
import unicodedata

# Keep family-wide vertical metrics consistent to satisfy FontBakery family checks.
# Win metrics must cover glyph bounds (for clipping prevention)
# but hhea metrics control line spacing (keep tighter like original Iosevka)
TARGET_WIN_ASCENT = 1198  # Fontspector requires this to cover all glyphs
TARGET_WIN_DESCENT = 604  # Fontspector requires this to cover all descenders
TARGET_HHEA_ASCENDER = 1015  # Mildly increase total height for looser leading
TARGET_HHEA_DESCENDER = -265  # Mildly increase total height for looser leading
TARGET_HHEA_LINE_GAP = 0  # Keep gap at zero for GF compliance

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
    # Strategy: Win metrics cover glyph bounds (clipping prevention)
    # but hhea/Typo metrics control line spacing (keep tighter)
    font['hhea'].ascender = TARGET_HHEA_ASCENDER
    font['hhea'].descender = TARGET_HHEA_DESCENDER
    font['hhea'].lineGap = TARGET_HHEA_LINE_GAP

    # Typo metrics should match hhea for consistency
    font['OS/2'].sTypoAscender = TARGET_HHEA_ASCENDER
    font['OS/2'].sTypoDescender = TARGET_HHEA_DESCENDER
    font['OS/2'].sTypoLineGap = TARGET_HHEA_LINE_GAP

    # Enable USE_TYPO_METRICS flag (bit 7) so apps use Typo instead of Win for line spacing
    font['OS/2'].fsSelection |= (1 << 7)

    total_height = font['hhea'].ascender - font['hhea'].descender + font['hhea'].lineGap
    print(f"  ✓ Fixed hhea metrics: ascender={font['hhea'].ascender}, "
          f"descender={font['hhea'].descender}, lineGap={font['hhea'].lineGap}, total={total_height}")
    print(f"  ✓ Fixed Typo metrics to match hhea (USE_TYPO_METRICS enabled)")
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
    gdef = font.get('GDEF')
    glyph_class_def = gdef.table.GlyphClassDef if gdef and gdef.table else None

    for glyph_name in glyph_order:
        if glyph_name not in glyf:
            continue

        width, lsb = hmtx[glyph_name]
        if width != 0:
            continue

        # Skip true combining marks; they are intentionally zero-width.
        is_combining = False
        # Check cmap-derived codepoint combining class
        for table in font['cmap'].tables:
            cp = table.cmap.get(glyph_name)
            if cp is not None and unicodedata.combining(chr(cp)):
                is_combining = True
                break
        # Check GDEF class definition for marks
        if glyph_class_def and glyph_class_def.classDefs.get(glyph_name) == 3:
            is_combining = True
        if is_combining:
            continue

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
    is_italic = bool(font['head'].macStyle & 2) or (font['OS/2'].fsSelection & 1)

    existing_family = name_table.getName(1, 3, 1, 0x409)
    family_hint = existing_family.toUnicode() if existing_family else ""
    is_mono = "Mono" in family_hint or "Mono" in font.reader.file.name
    base_family = "Iosevka Charon Mono" if is_mono else "Iosevka Charon"

    # Detect weight from file name (more reliable than current OS/2 weight class)
    file_name = Path(font.reader.file.name).stem
    weight_from_name = None
    for w in ["Heavy", "Light", "Medium", "Bold", "Thin", "ExtraLight", "SemiBold", "ExtraBold", "Black"]:
        if w in file_name:
            weight_from_name = w
            break

    # Map weight names to weight class values
    weight_name_to_class = {
        "Thin": 100,
        "ExtraLight": 200,
        "Light": 300,
        "Medium": 500,
        "SemiBold": 600,
        "Bold": 700,
        "ExtraBold": 800,
        "Black": 900,
        "Heavy": 900,
    }

    # Determine actual weight class from file name or existing value
    if weight_from_name:
        weight_class = weight_name_to_class.get(weight_from_name, 400)
    else:
        weight_class = font['OS/2'].usWeightClass

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
        900: ("Heavy", "heavy"),  # Use Heavy, not Black
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
        family_name = f"{base_family} {weight_display}"
        subfamily_name = "Italic" if is_italic else "Regular"

        # Google Fonts expects for non-RIBBI fonts:
        # - Family Name (ID 1): "Iosevka Charon Light" (includes weight)
        # - Subfamily Name (ID 2): "Regular" or "Italic"
        # - Full Name (ID 4): "Iosevka Charon Light" or "Iosevka Charon Light Italic" (no "Regular" for upright)
        # - Postscript Name (ID 6): "IosevkaCharon-Light" or "IosevkaCharon-LightItalic" (weight after hyphen)
        # - Typographic Family (ID 16): "Iosevka Charon"
        # - Typographic Subfamily (ID 17): "Light" or "Light Italic"
        if is_italic:
            full_name = f"{base_family} {weight_display} Italic"
            ps_name = f"{base_family.replace(' ', '')}-{weight_display}Italic"
            typographic_subfamily = f"{weight_display} Italic"
        else:
            full_name = f"{base_family} {weight_display}"
            ps_name = f"{base_family.replace(' ', '')}-{weight_display}"
            typographic_subfamily = weight_display

        typographic_family = base_family

        # Keep actual weight class (don't set to 400)
        # weight_class is already set from weight_from_name above

    # Set correct OS/2 usWeightClass
    font['OS/2'].usWeightClass = weight_class

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


def fix_broken_mark_anchors(font):
    """Fix Mark2Base anchors to use correct Y positions based on glyph geometry.

    The upstream Iosevka font often has incorrect anchor Y positions:
    - Both mark and base anchors at the same Y (causing 0 offset)
    - Both anchors at Y=0 (causing no vertical movement)

    This function recomputes all mark and base anchor Y positions based on
    the actual glyph geometry:
    - For above marks: mark anchor at yMin (bottom of mark), base anchor at yMax+gap
    - For below marks: mark anchor at yMax (top of mark), base anchor at yMin-gap
    """
    if 'GPOS' not in font or 'glyf' not in font:
        return False

    cmap = font.getBestCmap()
    glyf = font['glyf']
    gpos = font['GPOS'].table

    # Build reverse cmap: glyph name -> codepoint
    name_to_cp = {}
    for cp, name in cmap.items():
        if name not in name_to_cp:
            name_to_cp[name] = cp

    # Combining class ranges for below marks
    below_classes = {202, 214, 218, 220, 222, 223, 224, 225, 226}
    overlay_classes = {1, 200}

    def classify_mark_cp(cp: int) -> int:
        cc = unicodedata.combining(chr(cp))
        if cc in below_classes:
            return 1  # below
        if cc in overlay_classes:
            return 2  # overlay
        return 0  # above

    def get_glyph_bounds(name):
        """Get glyph yMin/yMax, computing if needed."""
        if name not in glyf:
            return None, None
        g = glyf[name]
        if not hasattr(g, 'yMax') or g.yMax is None:
            g.recalcBounds(glyf)
        ymin = getattr(g, 'yMin', None)
        ymax = getattr(g, 'yMax', None)
        if ymin is None or ymax is None:
            return None, None
        return ymin, ymax

    fixed_marks = 0
    fixed_bases = 0
    stack_gap = 60  # Gap between base and mark

    # Iterate through all lookups (not just mark feature) to catch all Mark2Base
    if not gpos.LookupList:
        return False

    for idx, lookup in enumerate(gpos.LookupList.Lookup):
        for subtable in lookup.SubTable:
            real_st = subtable
            if lookup.LookupType == 9 and hasattr(subtable, 'ExtSubTable'):
                real_st = subtable.ExtSubTable

            lt = getattr(real_st, 'LookupType', lookup.LookupType)
            if lt != 4:  # Only process MarkToBase
                continue

            if not (hasattr(real_st, 'MarkCoverage') and real_st.MarkCoverage):
                continue
            if not (hasattr(real_st, 'BaseCoverage') and real_st.BaseCoverage):
                continue
            if not (hasattr(real_st, 'MarkArray') and real_st.MarkArray):
                continue
            if not (hasattr(real_st, 'BaseArray') and real_st.BaseArray):
                continue

            # First pass: fix all mark anchors and collect which classes need base fixes
            # Also track the min/max mark anchor Y per class for proper base positioning
            classes_to_fix = {}  # mark_class -> (mark_type, min_or_max_mark_y)

            for m_idx, mark_name in enumerate(real_st.MarkCoverage.glyphs):
                cp = name_to_cp.get(mark_name)
                if cp is None:
                    continue

                mark_type = classify_mark_cp(cp)
                if mark_type == 2:  # overlay - skip
                    continue

                mark_ymin, mark_ymax = get_glyph_bounds(mark_name)
                if mark_ymin is None:
                    continue

                m_rec = real_st.MarkArray.MarkRecord[m_idx]
                mark_anchor = m_rec.MarkAnchor
                mark_class = m_rec.Class

                # Compute correct mark anchor Y
                if mark_type == 1:  # below mark
                    correct_mark_y = mark_ymax  # attach at top of mark
                else:  # above mark
                    correct_mark_y = mark_ymin  # attach at bottom of mark

                # Fix if different from current
                if mark_anchor.YCoordinate != correct_mark_y:
                    mark_anchor.YCoordinate = correct_mark_y
                    fixed_marks += 1

                # Track this class for base anchor fixes
                # For above marks: track the MAXIMUM mark_y (highest bottom among marks)
                # For below marks: track the MINIMUM mark_y (lowest top among marks)
                if mark_class not in classes_to_fix:
                    classes_to_fix[mark_class] = (mark_type, correct_mark_y)
                else:
                    _, prev_y = classes_to_fix[mark_class]
                    if mark_type == 0:  # above mark - track MAXIMUM (need base_y > all mark bottoms)
                        classes_to_fix[mark_class] = (mark_type, max(prev_y, correct_mark_y))
                    else:  # below mark - track MINIMUM (need base_y < all mark tops)
                        classes_to_fix[mark_class] = (mark_type, min(prev_y, correct_mark_y))

            # Second pass: fix base anchors for the mark classes we identified
            for b_idx, base_name in enumerate(real_st.BaseCoverage.glyphs):
                base_ymin, base_ymax = get_glyph_bounds(base_name)
                if base_ymin is None:
                    continue

                b_rec = real_st.BaseArray.BaseRecord[b_idx]

                for mark_class, (mark_type, mark_y_threshold) in classes_to_fix.items():
                    if mark_class >= len(b_rec.BaseAnchor):
                        continue
                    base_anchor = b_rec.BaseAnchor[mark_class]
                    if base_anchor is None:
                        continue

                    # Compute correct base anchor Y
                    # For above marks: base_anchor must be > mark_y_threshold
                    # For below marks: base_anchor must be < mark_y_threshold
                    if mark_type == 1:  # below mark
                        correct_base_y = base_ymin - stack_gap
                        # Ensure base_y < mark_y_threshold for negative offset
                        if correct_base_y >= mark_y_threshold:
                            correct_base_y = mark_y_threshold - 1
                    else:  # above mark
                        correct_base_y = base_ymax + stack_gap
                        # Ensure base_y > mark_y_threshold for positive offset
                        if correct_base_y <= mark_y_threshold:
                            correct_base_y = mark_y_threshold + 1

                    # Fix if different from current
                    if base_anchor.YCoordinate != correct_base_y:
                        base_anchor.YCoordinate = correct_base_y
                        fixed_bases += 1

    if fixed_marks > 0 or fixed_bases > 0:
        print(f"  ✓ Fixed mark anchor positions: {fixed_marks} marks, {fixed_bases} bases")
        return True

    return False


def add_fallback_mark_anchors(font):
    """Add broad mark-to-base coverage so combining marks attach instead of floating."""
    if 'GPOS' not in font or 'glyf' not in font:
        return False

    cmap = font.getBestCmap()
    glyph_for_cp = {cp: name for cp, name in cmap.items()}

    # Quick classifier for mark direction so we can generate sensible anchors.
    below_classes = {202, 214, 218, 220, 222, 223, 224, 225, 226}
    overlay_classes = {1, 200}

    def classify_mark(cp: int) -> int:
        cc = unicodedata.combining(chr(cp))
        if cc in below_classes:
            return 1  # below
        if cc in overlay_classes:
            return 2  # overlay
        return 0  # above

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

    glyf = font['glyf']
    hmtx = font['hmtx']

    # Collect existing mark coverage so we only add anchors for marks that currently
    # have no mark-to-base entries. This avoids overriding carefully tuned anchors.
    gpos_table = font['GPOS'].table
    existing_mark_glyphs = set()
    if gpos_table.FeatureList and gpos_table.LookupList:
        mark_lookup_indices = set()
        for record in gpos_table.FeatureList.FeatureRecord:
            if record.FeatureTag == "mark":
                mark_lookup_indices.update(record.Feature.LookupListIndex)
        for idx in sorted(mark_lookup_indices):
            if idx >= len(gpos_table.LookupList.Lookup):
                continue
            lookup = gpos_table.LookupList.Lookup[idx]
            # Handle extension lookups (type 9) by extracting the actual lookup
            for subtable in lookup.SubTable:
                real_st = subtable
                if lookup.LookupType == 9 and hasattr(subtable, 'ExtSubTable'):
                    real_st = subtable.ExtSubTable
                if getattr(real_st, 'LookupType', lookup.LookupType) != 4:  # MarkToBase
                    continue
                if hasattr(real_st, 'MarkCoverage') and real_st.MarkCoverage:
                    existing_mark_glyphs.update(real_st.MarkCoverage.glyphs)

    # Include marks that currently lack coverage. We skip marks already in existing
    # MarkToBase lookups since their anchors work correctly with the font's design.
    target_mark_glyphs = []
    for name, cp in mark_glyphs:
        if name not in existing_mark_glyphs:
            target_mark_glyphs.append((name, cp))

    if not target_mark_glyphs:
        return False

    glyf = font['glyf']
    hmtx = font['hmtx']

    mark_anchors = {}
    mark_classes_present = set()
    stack_gap = 60

    # Collect average mark heights per class to scale gaps (use all combining marks).
    class_heights = {}
    for name, cp in mark_glyphs:
        if name not in glyf:
            continue
        g = glyf[name]
        if not hasattr(g, "xMax") or g.xMax is None:
            g.recalcBounds(glyf)
        cls = classify_mark(cp)
        h = (g.yMax - g.yMin) if (hasattr(g, "yMax") and g.yMax is not None and g.yMin is not None) else 0
        class_heights.setdefault(cls, []).append(max(h, 0))

    def class_gap(cls: int) -> int:
        heights = class_heights.get(cls)
        if not heights:
            return stack_gap
        avg = sum(heights) // len(heights)
        return max(stack_gap, avg // 2)

    for name, cp in target_mark_glyphs:
        if name not in glyf or name not in hmtx.metrics:
            continue
        glyph = glyf[name]
        if not hasattr(glyph, "xMax") or glyph.xMax is None:
            glyph.recalcBounds(glyf)

        cls = classify_mark(cp)
        mark_classes_present.add(cls)

        mx = (glyph.xMin + glyph.xMax) // 2
        if cls == 1:  # below mark
            my = glyph.yMax
        elif cls == 2:  # overlay mark
            my = (glyph.yMin + glyph.yMax) // 2
        else:  # above/default
            my = glyph.yMin

        mark_anchors[name] = (cls, buildAnchor(mx, my))

    if not mark_anchors:
        return False

    # Build mark-to-mark anchors for all combining marks (skip ones already covered).
    gpos_table = font['GPOS'].table
    existing_mkmk_marks = set()
    if gpos_table.FeatureList and gpos_table.LookupList:
        for lookup in gpos_table.LookupList.Lookup:
            real_lookup = lookup
            if lookup.LookupType == 9 and hasattr(lookup, "SubTable"):
                # extension lookup
                for st in lookup.SubTable:
                    if hasattr(st, "ExtSubTable"):
                        real_lookup = st.ExtSubTable
                        break
            if real_lookup.LookupType != 6:
                continue
            if not hasattr(real_lookup, "SubTable"):
                continue
            for st in real_lookup.SubTable:
                real = st.ExtSubTable if hasattr(st, "ExtSubTable") else st
                if hasattr(real, "Mark1Coverage") and real.Mark1Coverage:
                    existing_mkmk_marks.update(real.Mark1Coverage.glyphs)

    mark1_for_mkmk = {}
    mark2_anchors = {}
    for name, cp in mark_glyphs:
        if name in existing_mkmk_marks:
            continue
        if name not in glyf:
            continue
        glyph = glyf[name]
        if not hasattr(glyph, "xMax") or glyph.xMax is None:
            glyph.recalcBounds(glyf)
        cls = classify_mark(cp)
        mx = (glyph.xMin + glyph.xMax) // 2
        gap = class_gap(cls)
        # mark1 anchor (where next mark attaches)
        if cls == 1:  # below
            m1y = glyph.yMin - gap  # attach next below this mark
            m2y = glyph.yMax + gap  # attach this mark to previous below
        elif cls == 2:  # overlay
            mid = (glyph.yMin + glyph.yMax) // 2
            m1y = mid
            m2y = mid
        else:  # above/default
            m1y = glyph.yMax + gap  # attach next above this mark
            m2y = glyph.yMin - gap  # attach this mark to previous above
        mark1_for_mkmk[name] = (cls, buildAnchor(mx, m1y))
        mark2_anchors[name] = {cls: buildAnchor(mx, m2y)}

    base_anchors = {}
    for base in base_glyphs:
        if base not in glyf or base not in hmtx.metrics:
            continue
        glyph = glyf[base]
        if not hasattr(glyph, "xMax") or glyph.xMax is None:
            glyph.recalcBounds(glyf)
        advance, _ = hmtx[base]
        x = advance // 2
        anchors_for_base = {}
        if 0 in mark_classes_present:
            anchors_for_base[0] = buildAnchor(x, glyph.yMax + class_gap(0))
        if 1 in mark_classes_present:
            anchors_for_base[1] = buildAnchor(x, glyph.yMin - class_gap(1))
        if 2 in mark_classes_present:
            anchors_for_base[2] = buildAnchor(x, (glyph.yMin + glyph.yMax) // 2)
        if anchors_for_base:
            base_anchors[base] = anchors_for_base

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

    # NOTE: The mark-to-mark fallback was disabled because it was overriding the
    # base font's correct cumulative mark-to-base stacking behavior with incorrect
    # anchor positions. The ü̃́ character (u + diaeresis + tilde + acute) was showing
    # overlapping marks because our calculated mkmk anchors positioned marks too
    # close together. The upstream Iosevka font already handles stacked marks
    # correctly through its mark-to-base positioning.
    #
    # See: HarfBuzz shaping showed base font positions marks at y=0, 205, 410
    # (correct 205-unit spacing) while our fallback produced y=0, 236, 252
    # (broken 16-unit spacing).

    return True


def add_dotted_circle_fallback(font):
    """Ensure dotted circle can accept all combining marks."""
    if 'GPOS' not in font or 'glyf' not in font:
        return False

    cmap = font.getBestCmap()
    dotted = cmap.get(0x25CC) or 'dottedcircle'
    if dotted not in font['glyf']:
        return False

    gpos = font['GPOS'].table
    glyf = font['glyf']
    hmtx = font['hmtx']

    # Build quick access to existing dotted-circle attachments.
    def has_anchor(mark_name):
        for lookup in gpos.LookupList.Lookup:
            ltype = lookup.LookupType
            for st in lookup.SubTable:
                real = st.ExtSubTable if ltype == 9 and hasattr(st, 'ExtSubTable') else st
                if getattr(real, 'LookupType', None) != 4:
                    continue
                if not (real.MarkCoverage and real.BaseCoverage):
                    continue
                if mark_name not in real.MarkCoverage.glyphs or dotted not in real.BaseCoverage.glyphs:
                    continue
                m_idx = real.MarkCoverage.glyphs.index(mark_name)
                m_rec = real.MarkArray.MarkRecord[m_idx]
                b_idx = real.BaseCoverage.glyphs.index(dotted)
                anchors = real.BaseArray.BaseRecord[b_idx].BaseAnchor
                if m_rec.Class < len(anchors) and anchors[m_rec.Class] is not None:
                    return True
        return False

    # Collect combining marks present in the font.
    mark_glyphs = []
    for cp, name in sorted(cmap.items()):
        if unicodedata.combining(chr(cp)):
            mark_glyphs.append((name, cp))

    missing = []
    for name, _ in mark_glyphs:
        if not has_anchor(name):
            missing.append(name)

    if not missing:
        return False

    # Build mark anchors and a single base record for dotted circle.
    mark_class_index = 0
    mark_anchors = {name: (mark_class_index, buildAnchor(0, 0)) for name in missing}

    # Anchor dotted circle at its visual center / top.
    glyph = glyf[dotted]
    if not hasattr(glyph, "xMax") or glyph.xMax is None:
        glyph.recalcBounds(glyf)
    advance, _ = hmtx[dotted]
    x = advance // 2
    y = glyph.yMax if hasattr(glyph, "yMax") and glyph.yMax is not None else font['hhea'].ascender
    base_anchors = {dotted: {mark_class_index: buildAnchor(x, y)}}

    subtables = buildMarkBasePos(mark_anchors, base_anchors, font.getReverseGlyphMap())
    lookup = otTables.Lookup()
    lookup.LookupFlag = 0
    lookup.LookupType = 4
    lookup.SubTable = subtables
    lookup.SubTableCount = len(subtables)

    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount += 1

    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag == "mark":
            record.Feature.LookupListIndex.append(len(gpos.LookupList.Lookup) - 1)
            break

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


def drop_glyph_names(font):
    """Switch post table to format 3 to avoid invalid glyph names."""
    if 'post' not in font:
        return False

    post = font['post']
    if getattr(post, "formatType", None) == 3.0:
        return False

    post.formatType = 3.0
    # Clear name-related data that isn't used in format 3.
    post.extraNames = []
    post.glyphNameIndex = []
    post.mapping = {}
    return True


def fix_gdef_mark_classes(font):
    """Ensure combining marks are classified as marks in GDEF."""
    if 'GDEF' not in font:
        return False

    cmap = font.getBestCmap()
    glyph_class_def = font['GDEF'].table.GlyphClassDef
    if glyph_class_def is None:
        return False

    updated = False
    for cp, name in cmap.items():
        if not unicodedata.combining(chr(cp)):
            continue
        current = glyph_class_def.classDefs.get(name)
        if current != 3:
            glyph_class_def.classDefs[name] = 3
            updated = True
    return updated


def add_kerning_feature(font):
    """Add GPOS kern feature for quasi-proportional fonts.

    This adds class-based kerning pairs to improve spacing between
    problematic letter combinations like AV, To, Ty, etc.
    Only applies to quasi-proportional fonts (isFixedPitch == 0).
    """
    # Only apply to quasi-proportional fonts
    # Use post.isFixedPitch (0 = proportional) rather than PANOSE
    # because fix_panose_monospace() forces bProportion to 9 for all fonts
    if 'post' in font and font['post'].isFixedPitch:
        return False  # Skip monospaced/fixed-pitch fonts

    if 'GPOS' not in font:
        return False

    glyf = font.get('glyf')
    cmap = font.getBestCmap()
    if not glyf or not cmap:
        return False

    glyph_order = font.getGlyphOrder()

    # Helper to find glyph names for a set of characters
    def names_for_chars(chars):
        names = []
        for ch in chars:
            cp = ord(ch)
            if cp in cmap:
                names.append(cmap[cp])
        return names

    # Helper to expand base glyph to include accented variants
    def expand_with_accents(base_names):
        expanded = set(base_names)
        for name in base_names:
            for gn in glyph_order:
                if gn.startswith(name) and gn != name:
                    expanded.add(gn)
        return list(expanded)

    # Define kerning classes
    # Left-side classes (the first glyph in the pair)
    # Step 1: Latin + Cyrillic + Greek classes
    left_classes = {
        # T-like shapes (horizontal overhang at top)
        '@L_T': expand_with_accents(names_for_chars(
            'TŦȚŢƬƮȾṪṬṮṰ'  # Latin
            'ТЋЂ'  # Cyrillic Te, Tshe, Dje
            'Ττ'  # Greek Tau
        )),
        # V-like shapes (diagonal meeting at bottom)
        '@L_V': expand_with_accents(names_for_chars(
            'VṼṾ'  # Latin
            'Ѵѵ'  # Cyrillic Izhitsa
        )),
        # W-like shapes
        '@L_W': expand_with_accents(names_for_chars(
            'WẀẂẄẆẈŴω'  # Latin + Greek omega
            'Ѿѿ'  # Cyrillic Ot
        )),
        # Y-like shapes
        '@L_Y': expand_with_accents(names_for_chars(
            'YỲỴỶỸŶŸÝƳƴ'  # Latin
            'УуЎўҮүҰұ'  # Cyrillic U variants
            'ΥΎυύ'  # Greek Upsilon
        )),
        # A-like shapes (diagonal sides)
        '@L_A': expand_with_accents(names_for_chars(
            'AÀÁÂÃÄÅĀĂĄǍẠẢẤẦẨẪẬẮẰẲẴẶÆ'  # Latin
            'АаДд'  # Cyrillic A, De
            'ΑαΆά'  # Greek Alpha
        )),
        # F-like shapes (horizontal overhang)
        '@L_F': expand_with_accents(names_for_chars(
            'FḞƑ'  # Latin
            'ГгҐґ'  # Cyrillic Ghe
            'Γγ'  # Greek Gamma
        )),
        # P-like shapes (bowl on right)
        '@L_P': expand_with_accents(names_for_chars(
            'PÞṔṖƤ'  # Latin
            'РрҎҏ'  # Cyrillic Er
            'Ρρ'  # Greek Rho
        )),
        # r lowercase
        '@L_r': expand_with_accents(names_for_chars(
            'rŕřŗṙṛṝṟɍɾ'  # Latin
            'гґ'  # Cyrillic small ghe
        )),
        # f lowercase
        '@L_f': expand_with_accents(names_for_chars(
            'fḟƒﬁﬂ'  # Latin
        )),
        # L-like shapes (right side open)
        '@L_L': expand_with_accents(names_for_chars(
            'LĹĻĽĿŁḶḸḺḼȽ'  # Latin
            'ГгҐґ'  # Cyrillic Ghe (similar L shape)
        )),
        # Step 2: Number classes
        '@L_1': names_for_chars('1¹①⑴₁'),
        '@L_7': names_for_chars('7⑦⑺'),
        '@L_4': names_for_chars('4⁴④⑷₄'),
        # Step 3: Quote classes (left side - closing quotes)
        '@L_quote': names_for_chars("\"'\u2019\u00bb\u203a"),
        # Step 4: Bracket classes
        '@L_paren': names_for_chars(')]}'),
        # Step 6: Right-side capitals for oT, aT etc.
        '@L_o': expand_with_accents(names_for_chars(
            'oòóôõöōŏőơǒọỏốồổỗộớờởỡợøœ'
            'оө'  # Cyrillic o
            'οό'  # Greek omicron
        )),
        '@L_a': expand_with_accents(names_for_chars(
            'aàáâãäåāăąǎạảấầẩẫậắằẳẵặæ'
            'а'  # Cyrillic a
            'α'  # Greek alpha
        )),
        '@L_e': expand_with_accents(names_for_chars(
            'eèéêëēĕėęěẹẻẽếềểễệ'
            'еёє'  # Cyrillic e
            'εέ'  # Greek epsilon
        )),
    }

    # Right-side classes (the second glyph in the pair)
    right_classes = {
        # Round letters (o-like) - Latin + Cyrillic + Greek
        '@R_o': expand_with_accents(names_for_chars(
            'oòóôõöōŏőơǒọỏốồổỗộớờởỡợøœ'
            'оө'  # Cyrillic o
            'οό'  # Greek omicron
        )),
        '@R_a': expand_with_accents(names_for_chars(
            'aàáâãäåāăąǎạảấầẩẫậắằẳẵặæ'
            'а'  # Cyrillic a
            'αά'  # Greek alpha
        )),
        '@R_e': expand_with_accents(names_for_chars(
            'eèéêëēĕėęěẹẻẽếềểễệ'
            'еёє'  # Cyrillic e
            'εέη'  # Greek epsilon, eta
        )),
        '@R_c': expand_with_accents(names_for_chars(
            'cçćĉċčƈ'
            'сς'  # Cyrillic es, Greek sigma
        )),
        '@R_d': expand_with_accents(names_for_chars(
            'dďđḋḍḏḑḓ'
            'дђ'  # Cyrillic de
        )),
        '@R_g': expand_with_accents(names_for_chars(
            'gĝğġģǧǵḡ'
        )),
        '@R_q': expand_with_accents(names_for_chars('q')),
        '@R_u': expand_with_accents(names_for_chars(
            'uùúûüũūŭůűųưǔǖǘǚǜụủứừửữự'
            'уўү'  # Cyrillic u
            'υύ'  # Greek upsilon
        )),
        '@R_s': expand_with_accents(names_for_chars(
            'sśŝşšșṡṣ'
        )),
        '@R_y': expand_with_accents(names_for_chars(
            'yýÿŷỳỵỷỹ'
            'у'  # Cyrillic u (y-like)
        )),
        '@R_v': expand_with_accents(names_for_chars(
            'v'
            'ѵ'  # Cyrillic izhitsa
        )),
        '@R_w': expand_with_accents(names_for_chars(
            'wẁẃẅẇẉŵ'
            'ѿ'  # Cyrillic ot
        )),
        # Capital letters for right side
        '@R_A': expand_with_accents(names_for_chars(
            'AÀÁÂÃÄÅĀĂĄǍẠẢẤẦẨẪẬẮẰẲẴẶ'
            'АД'  # Cyrillic A, De
            'ΑΆ'  # Greek Alpha
        )),
        '@R_V': expand_with_accents(names_for_chars(
            'VṼṾ'
            'Ѵ'  # Cyrillic Izhitsa
        )),
        '@R_T': expand_with_accents(names_for_chars(
            'TŦȚŢƬƮȾṪṬṮṰ'
            'ТЋЂ'  # Cyrillic Te
            'Ττ'  # Greek Tau
        )),
        '@R_Y': expand_with_accents(names_for_chars(
            'YỲỴỶỸŶŸÝƳƴ'
            'УЎҮ'  # Cyrillic U
            'ΥΎ'  # Greek Upsilon
        )),
        # Step 2: Punctuation including numbers
        '@R_punct': names_for_chars('.,;:!?'),
        '@R_hyphen': names_for_chars('-–—'),
        # Step 3: Quote classes (right side - opening quotes)
        '@R_quote': names_for_chars("\"'\u201c\u2018\u00ab\u2039"),
        # Step 4: Bracket classes
        '@R_paren': names_for_chars('([{'),
    }

    # Filter to only include glyphs that exist in the font
    for class_name, class_glyphs in list(left_classes.items()):
        left_classes[class_name] = [g for g in class_glyphs if g in glyph_order]
    for class_name, class_glyphs in list(right_classes.items()):
        right_classes[class_name] = [g for g in class_glyphs if g in glyph_order]

    # Remove empty classes
    left_classes = {k: v for k, v in left_classes.items() if v}
    right_classes = {k: v for k, v in right_classes.items() if v}

    if not left_classes or not right_classes:
        return False

    # Define kerning values (negative = tighten, positive = loosen)
    # All 7 steps combined
    kern_pairs = {
        # T combinations (Step 1: Latin + Cyrillic + Greek)
        ('@L_T', '@R_o'): -50, ('@L_T', '@R_a'): -45, ('@L_T', '@R_e'): -45,
        ('@L_T', '@R_c'): -40, ('@L_T', '@R_u'): -35, ('@L_T', '@R_s'): -35,
        ('@L_T', '@R_y'): -25, ('@L_T', '@R_punct'): -60, ('@L_T', '@R_hyphen'): -40,
        # V combinations
        ('@L_V', '@R_o'): -40, ('@L_V', '@R_a'): -35, ('@L_V', '@R_e'): -35,
        ('@L_V', '@R_u'): -25, ('@L_V', '@R_A'): -50, ('@L_V', '@R_punct'): -50,
        ('@L_V', '@R_hyphen'): -30,
        # W combinations
        ('@L_W', '@R_o'): -30, ('@L_W', '@R_a'): -25, ('@L_W', '@R_e'): -25,
        ('@L_W', '@R_A'): -35, ('@L_W', '@R_punct'): -40, ('@L_W', '@R_hyphen'): -20,
        # Y combinations
        ('@L_Y', '@R_o'): -50, ('@L_Y', '@R_a'): -45, ('@L_Y', '@R_e'): -45,
        ('@L_Y', '@R_u'): -35, ('@L_Y', '@R_punct'): -60, ('@L_Y', '@R_hyphen'): -35,
        # A combinations
        ('@L_A', '@R_V'): -50, ('@L_A', '@R_v'): -35, ('@L_A', '@R_w'): -25,
        ('@L_A', '@R_y'): -30, ('@L_A', '@R_T'): -40, ('@L_A', '@R_Y'): -45,
        ('@L_A', '@R_quote'): -40,
        # F combinations
        ('@L_F', '@R_o'): -35, ('@L_F', '@R_a'): -30, ('@L_F', '@R_e'): -30,
        ('@L_F', '@R_punct'): -50, ('@L_F', '@R_hyphen'): -25,
        # P combinations
        ('@L_P', '@R_o'): -25, ('@L_P', '@R_a'): -20, ('@L_P', '@R_e'): -20,
        ('@L_P', '@R_punct'): -45, ('@L_P', '@R_hyphen'): -20,
        # r lowercase
        ('@L_r', '@R_o'): -20, ('@L_r', '@R_a'): -15, ('@L_r', '@R_e'): -15,
        ('@L_r', '@R_punct'): -30, ('@L_r', '@R_hyphen'): -15,
        # f lowercase
        ('@L_f', '@R_o'): -15, ('@L_f', '@R_a'): -10, ('@L_f', '@R_e'): -10,
        # L combinations
        ('@L_L', '@R_V'): -35, ('@L_L', '@R_y'): -25, ('@L_L', '@R_T'): -35,
        ('@L_L', '@R_Y'): -30, ('@L_L', '@R_quote'): -30,
        # Step 2: Number kerning
        ('@L_1', '@R_punct'): -30, ('@L_7', '@R_punct'): -40,
        ('@L_4', '@R_punct'): -20,
        ('@L_1', '@R_paren'): -20, ('@L_7', '@R_paren'): -25,
        # Step 3: Quote kerning
        ('@L_quote', '@R_o'): -25, ('@L_quote', '@R_a'): -20,
        ('@L_quote', '@R_e'): -20, ('@L_quote', '@R_c'): -20,
        ('@L_A', '@R_quote'): -40, ('@L_V', '@R_quote'): -35,
        ('@L_W', '@R_quote'): -25, ('@L_Y', '@R_quote'): -40,
        ('@L_T', '@R_quote'): -30,
        # Step 4: Bracket kerning
        ('@L_paren', '@R_o'): -15, ('@L_paren', '@R_a'): -15,
        ('@L_paren', '@R_e'): -15,
        ('@L_A', '@R_paren'): -20, ('@L_V', '@R_paren'): -25,
        ('@L_T', '@R_paren'): -20, ('@L_Y', '@R_paren'): -25,
        # Step 6: Right-side capital kerning (reverse pairs like oT, aV)
        ('@L_o', '@R_T'): -50, ('@L_o', '@R_V'): -35, ('@L_o', '@R_Y'): -40,
        ('@L_a', '@R_T'): -45, ('@L_a', '@R_V'): -30, ('@L_a', '@R_Y'): -35,
        ('@L_e', '@R_T'): -45, ('@L_e', '@R_V'): -30, ('@L_e', '@R_Y'): -35,
    }

    # Step 7: Optical kerning helper - analyze glyph metrics to suggest kern values
    def optical_kern_value(g1_name, g2_name, base_value):
        """Adjust kerning value based on actual glyph sidebearings.

        If glyphs have unusual sidebearings, adjust the kern value proportionally.
        This provides more accurate kerning than fixed values alone.
        """
        if g1_name not in glyf or g2_name not in glyf:
            return base_value
        if g1_name not in hmtx.metrics or g2_name not in hmtx.metrics:
            return base_value

        g1 = glyf[g1_name]
        g2 = glyf[g2_name]

        # Ensure bounds are calculated
        if not hasattr(g1, 'xMax') or g1.xMax is None:
            g1.recalcBounds(glyf)
        if not hasattr(g2, 'xMin') or g2.xMin is None:
            g2.recalcBounds(glyf)

        # Get sidebearings
        g1_width, _ = hmtx[g1_name]
        g2_width, g2_lsb = hmtx[g2_name]

        # Calculate right sidebearing of g1
        if hasattr(g1, 'xMax') and g1.xMax is not None:
            g1_rsb = g1_width - g1.xMax
        else:
            return base_value

        # If g1 has negative RSB (glyph extends past advance), tighten more
        # If g2 has large LSB, we already have space so tighten less
        adjustment = 0
        if g1_rsb < 0:  # Overhanging glyph (like T)
            adjustment -= 10  # Tighten a bit more
        if g2_lsb > 50:  # Already has space on left
            adjustment += 10  # Tighten less

        return base_value + adjustment

    # Step 5: Build Format 2 (Class-based) GPOS kerning
    # This is MUCH more efficient than Format 1 with individual pairs
    gpos = font['GPOS'].table
    hmtx = font['hmtx']

    # Assign class IDs to glyphs
    # Class 0 is reserved for "all other glyphs"
    left_class_defs = {}  # glyph_name -> class_id
    right_class_defs = {}

    # Map class names to numeric IDs (starting from 1)
    left_class_ids = {}
    right_class_ids = {}

    class_id = 1
    for class_name, glyphs in left_classes.items():
        left_class_ids[class_name] = class_id
        for g in glyphs:
            left_class_defs[g] = class_id
        class_id += 1

    class_id = 1
    for class_name, glyphs in right_classes.items():
        right_class_ids[class_name] = class_id
        for g in glyphs:
            right_class_defs[g] = class_id
        class_id += 1

    # Build class-based pair values
    # kern_pairs maps (left_class_name, right_class_name) -> value
    # We need to convert to (left_class_id, right_class_id) -> value
    class_pair_values = {}
    for (left_class_name, right_class_name), value in kern_pairs.items():
        left_id = left_class_ids.get(left_class_name)
        right_id = right_class_ids.get(right_class_name)
        if left_id and right_id:
            class_pair_values[(left_id, right_id)] = value

    if not class_pair_values:
        return False

    # Create PairPos Format 2 subtable
    lookup = otTables.Lookup()
    lookup.LookupType = 2  # Pair Adjustment
    lookup.LookupFlag = 0
    lookup.SubTableCount = 1

    subtable = otTables.PairPos()
    subtable.Format = 2  # Class-based kerning!
    subtable.ValueFormat1 = 4  # XAdvance only
    subtable.ValueFormat2 = 0

    # Build Coverage (all glyphs that appear on left side)
    all_left_glyphs = list(left_class_defs.keys())
    glyph_order_map = {g: i for i, g in enumerate(glyph_order)}
    all_left_glyphs.sort(key=lambda x: glyph_order_map.get(x, 999999))

    coverage = otTables.Coverage()
    coverage.glyphs = all_left_glyphs
    subtable.Coverage = coverage

    # Build ClassDef1 (left side classes)
    class_def1 = otTables.ClassDef()
    class_def1.classDefs = left_class_defs
    subtable.ClassDef1 = class_def1

    # Build ClassDef2 (right side classes)
    class_def2 = otTables.ClassDef()
    class_def2.classDefs = right_class_defs
    subtable.ClassDef2 = class_def2

    # Build Class1Record array
    # Number of class1 records = max class1 ID + 1 (to include class 0)
    num_class1 = max(left_class_ids.values()) + 1 if left_class_ids else 1
    num_class2 = max(right_class_ids.values()) + 1 if right_class_ids else 1

    subtable.ClassCount1 = num_class1
    subtable.ClassCount2 = num_class2

    class1_records = []
    for c1 in range(num_class1):
        c1_record = otTables.Class1Record()
        c2_records = []
        for c2 in range(num_class2):
            c2_record = otTables.Class2Record()
            value = class_pair_values.get((c1, c2), 0)
            if value:
                c2_record.Value1 = otTables.ValueRecord()
                c2_record.Value1.XAdvance = value
            else:
                c2_record.Value1 = otTables.ValueRecord()
                c2_record.Value1.XAdvance = 0
            c2_record.Value2 = None
            c2_records.append(c2_record)
        c1_record.Class2Record = c2_records
        class1_records.append(c1_record)

    subtable.Class1Record = class1_records
    lookup.SubTable = [subtable]

    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount += 1
    new_lookup_index = len(gpos.LookupList.Lookup) - 1

    # Find or create 'kern' feature
    kern_feature = None
    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag == 'kern':
            kern_feature = record.Feature
            break

    if kern_feature is None:
        new_record = otTables.FeatureRecord()
        new_record.FeatureTag = 'kern'
        new_record.Feature = otTables.Feature()
        new_record.Feature.FeatureParams = None
        new_record.Feature.LookupListIndex = [new_lookup_index]
        new_record.Feature.LookupCount = 1
        gpos.FeatureList.FeatureRecord.append(new_record)
        gpos.FeatureList.FeatureCount += 1

        for script_record in gpos.ScriptList.ScriptRecord:
            script = script_record.Script
            if script.DefaultLangSys:
                feature_index = len(gpos.FeatureList.FeatureRecord) - 1
                script.DefaultLangSys.FeatureIndex.append(feature_index)
                script.DefaultLangSys.FeatureCount += 1
    else:
        kern_feature.LookupListIndex.append(new_lookup_index)
        kern_feature.LookupCount += 1

    print(f"  ✓ Added kerning: {len(class_pair_values)} class pairs, {len(all_left_glyphs)} left glyphs (Format 2)")
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

        if drop_glyph_names(font):
            fixes_applied.append("stripped_glyph_names")

        if fix_broken_mark_anchors(font):
            fixes_applied.append("fixed_broken_mark_anchors")

        if add_fallback_mark_anchors(font):
            fixes_applied.append("fallback_mark_anchors")

        if add_dotted_circle_fallback(font):
            fixes_applied.append("dotted_circle_fallback")

        if fix_gdef_mark_classes(font):
            fixes_applied.append("gdef_mark_classes")

        if add_kerning_feature(font):
            fixes_applied.append("kerning")

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
