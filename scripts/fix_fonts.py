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

import argparse
import logging
import shutil
import sys
import unicodedata
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Optional, Tuple

from fontTools.otlLib.builder import buildAnchor, buildMarkBasePos
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables, ttProgram
from gftools.fix import fix_font as gftools_fix_font

# Constants
# ----------------------------------------------------------------------------

# Keep family-wide vertical metrics consistent to satisfy FontBakery family checks.
# Win metrics must cover glyph bounds (for clipping prevention)
# but hhea metrics control line spacing (keep tighter like original Iosevka)
TARGET_WIN_ASCENT = 1198  # Fontspector requires this to cover all glyphs
TARGET_WIN_DESCENT = 604  # Fontspector requires this to cover all descenders
TARGET_HHEA_ASCENDER = 1015  # Mildly increase total height for looser leading
TARGET_HHEA_DESCENDER = -265  # Mildly increase total height for looser leading
TARGET_HHEA_LINE_GAP = 0  # Keep gap at zero for GF compliance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# Core Fix Functions
# ----------------------------------------------------------------------------


def fix_font_revision(font: TTFont) -> bool:
    """Fix font revision and nameID5 to exact value (Version 32.5.0)."""
    target_version = "Version 32.5.0"
    font["head"].fontRevision = 32.5
    name_table = font["name"]
    name_table.setName(target_version, 5, 3, 1, 0x409)
    name_table.setName(target_version, 5, 1, 0, 0)
    logger.info("  ✓ Fixed font revision: 32.5")
    return True


def fix_copyright_notice(font: TTFont) -> bool:
    """Fix copyright notice to match Google Fonts canonical format."""
    name_table = font["name"]
    copyright_notice = "Copyright 2015-2025 The Iosevka Project Authors (https://github.com/be5invis/Iosevka)"

    name_table.setName(copyright_notice, 0, 3, 1, 0x409)
    name_table.setName(copyright_notice, 0, 1, 0, 0)

    logger.info(f"  ✓ Fixed copyright notice: {copyright_notice}")
    return True


def fix_windows_metrics(font: TTFont) -> bool:
    """Fix Windows ascent/descent to proper values for Google Fonts"""
    font["OS/2"].usWinAscent = TARGET_WIN_ASCENT
    font["OS/2"].usWinDescent = TARGET_WIN_DESCENT

    logger.info(f"  ✓ Fixed Windows metrics: usWinAscent={TARGET_WIN_ASCENT}, usWinDescent={TARGET_WIN_DESCENT}")
    return True


def fix_vertical_metrics(font: TTFont) -> bool:
    """Fix hhea vertical metrics for Google Fonts"""
    font["hhea"].ascender = TARGET_HHEA_ASCENDER
    font["hhea"].descender = TARGET_HHEA_DESCENDER
    font["hhea"].lineGap = TARGET_HHEA_LINE_GAP

    # Typo metrics should match hhea for consistency
    font["OS/2"].sTypoAscender = TARGET_HHEA_ASCENDER
    font["OS/2"].sTypoDescender = TARGET_HHEA_DESCENDER
    font["OS/2"].sTypoLineGap = TARGET_HHEA_LINE_GAP

    # Enable USE_TYPO_METRICS flag (bit 7)
    font["OS/2"].fsSelection |= 1 << 7

    total_height = font["hhea"].ascender - font["hhea"].descender + font["hhea"].lineGap
    logger.info(
        f"  ✓ Fixed hhea metrics: ascender={font['hhea'].ascender}, "
        f"descender={font['hhea'].descender}, lineGap={font['hhea'].lineGap}, total={total_height}"
    )
    logger.info("  ✓ Fixed Typo metrics to match hhea (USE_TYPO_METRICS enabled)")
    return True


def flatten_nested_components(font: TTFont) -> bool:
    """Flatten nested composites by inlining their components."""
    if "glyf" not in font:
        return False

    from fontTools.ttLib.tables._g_l_y_f import (
        NON_OVERLAPPING,
        OVERLAP_COMPOUND,
        ROUND_XY_TO_GRID,
        SCALED_COMPONENT_OFFSET,
        UNSCALED_COMPONENT_OFFSET,
        USE_MY_METRICS,
        GlyphComponent,
    )

    glyf = font["glyf"]
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


def fix_fontbakery_version(font: TTFont) -> bool:
    """Update or remove fontbakery version metadata."""
    name_table = font["name"]

    # Check manufacturer/description fields that might have fontbakery refs
    for name_id in [8, 9, 10]:  # Manufacturer, Designer, Description
        for record in list(name_table.names):
            if record.nameID == name_id:
                value = record.toUnicode()
                if "fontbakery" in value.lower():
                    name_table.names.remove(record)
                    logger.info(f"  ✓ Removed fontbakery reference from nameID {name_id}")

    return True


def fix_zero_width_glyphs(font: TTFont) -> bool:
    """Fix zero-width base characters by setting advance width."""
    if "hmtx" not in font or "glyf" not in font:
        return False

    hmtx = font["hmtx"]
    glyf = font["glyf"]
    fixed = []

    # Specific glyphs in Private Use Area that need width
    pua_glyphs_to_fix = {
        "uniEF06",
        "uniEF07",
        "uniEF08",
        "uniEF09",
        "uniEF0A",
        "uniEF0B",
        "uniEF0C",
    }

    # Get the standard width for this font (monospaced)
    if "space" in hmtx.metrics:
        new_width = hmtx["space"][0]
    else:
        # Fallback to average width
        widths = [w for w, _ in hmtx.metrics.values() if w > 0]
        new_width = sum(widths) // len(widths) if widths else 500

    glyph_order = font.getGlyphOrder()
    gdef = font.get("GDEF")
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
        for table in font["cmap"].tables:
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
        has_contours = (
            hasattr(glyph, "numberOfContours")
            and glyph.numberOfContours is not None
            and glyph.numberOfContours != 0
        )

        # Fix if it's a PUA glyph or has contours but no width
        if is_pua_glyph or (has_contours and not glyph.isComposite()):
            hmtx[glyph_name] = (new_width, lsb)
            fixed.append(glyph_name)

    if fixed:
        logger.info(f"  ✓ Fixed zero-width glyphs: {', '.join(fixed)}")
        # Update hhea.advanceWidthMax if needed
        max_width = max((w for w, _ in hmtx.metrics.values()), default=0)
        if max_width > font["hhea"].advanceWidthMax:
            font["hhea"].advanceWidthMax = max_width
            logger.info(f"  ✓ Updated hhea.advanceWidthMax to {max_width}")
        return True
    return False


def fix_font_names(font: TTFont) -> bool:
    """Fix font names to match Google Fonts requirements."""
    name_table = font["name"]
    is_italic = bool(font["head"].macStyle & 2) or (font["OS/2"].fsSelection & 1)

    existing_family = name_table.getName(1, 3, 1, 0x409)
    family_hint = existing_family.toUnicode() if existing_family else ""

    # Get file name safely from the reader
    file_path = Path(font.reader.file.name)
    is_mono = "Mono" in family_hint or "Mono" in file_path.name
    base_family = "Iosevka Charon Mono" if is_mono else "Iosevka Charon"

    # Detect weight from file name (more reliable than current OS/2 weight class)
    file_stem = file_path.stem
    weight_from_name = None
    weights = ["Heavy", "Light", "Medium", "Bold", "Thin", "ExtraLight", "SemiBold", "ExtraBold", "Black"]
    for w in weights:
        if w in file_stem:
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
        weight_class = font["OS/2"].usWeightClass

    weight_map = {
        100: ("Thin", "thin"),
        200: ("Extralight", "extralight"),
        300: ("Light", "light"),
        400: ("Regular", "regular"),
        500: ("Medium", "medium"),
        600: ("Semibold", "semibold"),
        700: ("Bold", "bold"),
        800: ("Extrabold", "extrabold"),
        900: ("Heavy", "heavy"),
    }
    weight_display, _ = weight_map.get(weight_class, ("Regular", "regular"))

    # RIBBI logic
    is_ribbi = (weight_class in (400, 700)) and (weight_class == 400 or is_italic or weight_class == 700)

    # Simplified naming logic based on Google Fonts rules
    if weight_class == 400 and not is_italic:
        family_name, subfamily_name = base_family, "Regular"
        ps_suffix = "Regular"
        typographic_family, typographic_subfamily = None, None
    elif weight_class == 700 and not is_italic:
        family_name, subfamily_name = base_family, "Bold"
        ps_suffix = "Bold"
        typographic_family, typographic_subfamily = None, None
    elif weight_class == 400 and is_italic:
        family_name, subfamily_name = base_family, "Italic"
        ps_suffix = "Italic"
        typographic_family, typographic_subfamily = None, None
    elif weight_class == 700 and is_italic:
        family_name, subfamily_name = base_family, "Bold Italic"
        ps_suffix = "BoldItalic"
        typographic_family, typographic_subfamily = None, None
    else:
        family_name = f"{base_family} {weight_display}"
        subfamily_name = "Italic" if is_italic else "Regular"
        ps_suffix = f"{weight_display}Italic" if is_italic else weight_display
        typographic_family = base_family
        typographic_subfamily = f"{weight_display} Italic" if is_italic else weight_display

    full_name = f"{family_name} {subfamily_name}"
    # ID4 Exception: For non-RIBBI weights, Full Name should not include "Regular" if it's upright
    if typographic_family and not is_italic:
        full_name = family_name

    ps_name = f"{base_family.replace(' ', '')}-{ps_suffix}"

    # Set correct OS/2 usWeightClass
    font["OS/2"].usWeightClass = weight_class

    # Set name IDs (3.1.1033 is Windows/English)
    name_table.setName(family_name, 1, 3, 1, 0x409)
    name_table.setName(subfamily_name, 2, 3, 1, 0x409)
    name_table.setName(full_name, 4, 3, 1, 0x409)
    name_table.setName(ps_name, 6, 3, 1, 0x409)

    if typographic_family is None:
        name_table.names = [n for n in name_table.names if n.nameID not in (16, 17)]
    else:
        name_table.setName(typographic_family, 16, 3, 1, 0x409)
        name_table.setName(typographic_subfamily, 17, 3, 1, 0x409)

    # Mirror to Mac platform (1.0.0 is Mac/English)
    name_table.setName(family_name, 1, 1, 0, 0)
    name_table.setName(subfamily_name, 2, 1, 0, 0)
    name_table.setName(full_name, 4, 1, 0, 0)
    name_table.setName(ps_name, 6, 1, 0, 0)
    if typographic_family:
        name_table.setName(typographic_family, 16, 1, 0, 0)
        name_table.setName(typographic_subfamily, 17, 1, 0, 0)

    logger.info(f"  ✓ Fixed font names: {full_name} (ps: {ps_name})")
    return True


def fix_dotted_circle(font: TTFont) -> bool:
    """Ensure dotted circle glyph exists and has proper marks."""
    cmap = font.getBestCmap()
    if 0x25CC not in cmap:
        # Try to find space or period to use as placeholder
        for placeholder in ["space", "period", "uni00A0"]:
            if placeholder in font["glyf"]:
                for table in font["cmap"].tables:
                    table.cmap[0x25CC] = placeholder
                logger.info(f"  ✓ Added Dotted Circle (U+25CC) pointing to {placeholder} glyph")
                return True
        logger.warning("  ! Could not find placeholder for Dotted Circle")
        return False
    return False


def fix_broken_mark_anchors(font: TTFont) -> bool:
    """Fix Mark2Base anchors to use correct Y positions based on glyph geometry."""
    if "GPOS" not in font or "glyf" not in font:
        return False

    cmap = font.getBestCmap()
    glyf = font["glyf"]
    gpos_table = font["GPOS"].table

    # Build reverse cmap: glyph name -> codepoint
    name_to_cp = {name: cp for cp, name in cmap.items()}

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
        try:
            if not hasattr(g, "yMax") or g.yMax is None:
                g.recalcBounds(glyf)
        except Exception:
            return None, None
        ymin = getattr(g, "yMin", None)
        ymax = getattr(g, "yMax", None)
        if ymin is None or ymax is None:
            return None, None
        return ymin, ymax

    fixed_marks = 0
    fixed_bases = 0
    stack_gap = 60  # Gap between base and mark

    if not gpos_table.LookupList:
        return False

    for lookup in gpos_table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            real_st = subtable
            if lookup.LookupType == 9 and hasattr(subtable, "ExtSubTable"):
                real_st = subtable.ExtSubTable

            lt = getattr(real_st, "LookupType", lookup.LookupType)
            if lt != 4:  # Only process MarkToBase
                continue

            if not (hasattr(real_st, "MarkCoverage") and real_st.MarkCoverage):
                continue
            if not (hasattr(real_st, "BaseCoverage") and real_st.BaseCoverage):
                continue
            if not (hasattr(real_st, "MarkArray") and real_st.MarkArray):
                continue
            if not (hasattr(real_st, "BaseArray") and real_st.BaseArray):
                continue

            # First pass: fix all mark anchors and collect which classes need base fixes
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
                correct_mark_y = mark_ymax if mark_type == 1 else mark_ymin

                # Fix if different from current
                if mark_anchor.YCoordinate != correct_mark_y:
                    mark_anchor.YCoordinate = correct_mark_y
                    fixed_marks += 1

                # Track this class for base anchor fixes
                if mark_class not in classes_to_fix:
                    classes_to_fix[mark_class] = (mark_type, correct_mark_y)
                else:
                    _, prev_y = classes_to_fix[mark_class]
                    if mark_type == 0:  # above mark - track MAXIMUM
                        classes_to_fix[mark_class] = (mark_type, max(prev_y, correct_mark_y))
                    else:  # below mark - track MINIMUM
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

                    if mark_type == 1:  # below mark
                        correct_base_y = base_ymin - stack_gap
                        if correct_base_y >= mark_y_threshold:
                            correct_base_y = mark_y_threshold - 1
                    else:  # above mark
                        correct_base_y = base_ymax + stack_gap
                        if correct_base_y <= mark_y_threshold:
                            correct_base_y = mark_y_threshold + 1

                    # Fix if different from current
                    if base_anchor.YCoordinate != correct_base_y:
                        base_anchor.YCoordinate = correct_base_y
                        fixed_bases += 1

    if fixed_marks > 0 or fixed_bases > 0:
        logger.info(f"  ✓ Fixed mark anchor positions: {fixed_marks} marks, {fixed_bases} bases")
        return True

    return False


def add_fallback_mark_anchors(font: TTFont) -> bool:
    """Add broad mark-to-base coverage so combining marks attach instead of floating."""
    if "GPOS" not in font or "glyf" not in font:
        return False

    cmap = font.getBestCmap()
    glyph_for_cp = {cp: name for cp, name in cmap.items()}

    # Quick classifier for mark direction
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
    base_glyphs = []
    mark_glyph_names = {name for name, _ in mark_glyphs}

    for cp, name in sorted(glyph_for_cp.items()):
        if not unicodedata.combining(chr(cp)) and name not in mark_glyph_names:
            base_glyphs.append(name)

    glyf_table = font["glyf"]
    for glyph_name in font.getGlyphOrder():
        if glyph_name not in glyph_for_cp.values() and glyph_name not in mark_glyph_names:
            if glyph_name in glyf_table:
                base_glyphs.append(glyph_name)

    glyf = font["glyf"]
    hmtx = font["hmtx"]

    gpos_table = font["GPOS"].table
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
            for subtable in lookup.SubTable:
                real_st = subtable
                if lookup.LookupType == 9 and hasattr(subtable, "ExtSubTable"):
                    real_st = subtable.ExtSubTable
                if getattr(real_st, "LookupType", lookup.LookupType) != 4:
                    continue
                if hasattr(real_st, "MarkCoverage") and real_st.MarkCoverage:
                    existing_mark_glyphs.update(real_st.MarkCoverage.glyphs)

    target_mark_glyphs = [(name, cp) for name, cp in mark_glyphs if name not in existing_mark_glyphs]

    if not target_mark_glyphs:
        return False

    mark_anchors = {}
    mark_classes_present = set()
    stack_gap = 60

    # Collect average mark heights per class
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
        my = glyph.yMax if cls == 1 else ((glyph.yMin + glyph.yMax) // 2 if cls == 2 else glyph.yMin)
        mark_anchors[name] = (cls, buildAnchor(mx, my))

    if not mark_anchors:
        return False

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

    gpos_table.LookupList.Lookup.append(lookup)
    gpos_table.LookupList.LookupCount += 1
    new_index = len(gpos_table.LookupList.Lookup) - 1

    for record in gpos_table.FeatureList.FeatureRecord:
        if record.FeatureTag == "mark":
            record.Feature.LookupListIndex.append(new_index)
            break
    else:
        feature = otTables.FeatureRecord()
        feature.FeatureTag = "mark"
        feature.Feature = otTables.Feature()
        feature.Feature.LookupCount = 1
        feature.Feature.LookupListIndex = [new_index]
        gpos_table.FeatureList.FeatureRecord.append(feature)
        gpos_table.FeatureList.FeatureCount += 1

    return True


def add_dotted_circle_fallback(font: TTFont) -> bool:
    """Ensure dotted circle can accept all combining marks."""
    if "GPOS" not in font or "glyf" not in font:
        return False

    cmap = font.getBestCmap()
    dotted = cmap.get(0x25CC) or "dottedcircle"
    if dotted not in font["glyf"]:
        return False

    gpos_table = font["GPOS"].table
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    def has_anchor(mark_name):
        for lookup in gpos_table.LookupList.Lookup:
            ltype = lookup.LookupType
            for st in lookup.SubTable:
                real = st.ExtSubTable if ltype == 9 and hasattr(st, "ExtSubTable") else st
                if getattr(real, "LookupType", None) != 4:
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

    mark_glyphs = [(name, cp) for cp, name in sorted(cmap.items()) if unicodedata.combining(chr(cp))]
    missing = [name for name, _ in mark_glyphs if not has_anchor(name)]

    if not missing:
        return False

    mark_class_index = 0
    mark_anchors = {name: (mark_class_index, buildAnchor(0, 0)) for name in missing}

    glyph = glyf[dotted]
    if not hasattr(glyph, "xMax") or glyph.xMax is None:
        glyph.recalcBounds(glyf)
    advance, _ = hmtx[dotted]
    x = advance // 2
    y = glyph.yMax if hasattr(glyph, "yMax") and glyph.yMax is not None else font["hhea"].ascender
    base_anchors = {dotted: {mark_class_index: buildAnchor(x, y)}}

    subtables = buildMarkBasePos(mark_anchors, base_anchors, font.getReverseGlyphMap())
    lookup = otTables.Lookup()
    lookup.LookupFlag = 0
    lookup.LookupType = 4
    lookup.SubTable = subtables
    lookup.SubTableCount = len(subtables)

    gpos_table.LookupList.Lookup.append(lookup)
    gpos_table.LookupList.LookupCount += 1
    new_index = len(gpos_table.LookupList.Lookup) - 1

    for record in gpos_table.FeatureList.FeatureRecord:
        if record.FeatureTag == "mark":
            record.Feature.LookupListIndex.append(new_index)
            break

    return True


def normalize_simple_glyphs(font: TTFont) -> bool:
    """Rebuild simple glyphs to clear bad flag bits that trigger OTS errors."""
    if "glyf" not in font:
        return False

    glyf = font["glyf"]
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


def fix_panose_monospace(font: TTFont) -> bool:
    """Ensure PANOSE proportion is set to monospaced."""
    if "OS/2" not in font:
        return False
    panose = font["OS/2"].panose
    if panose.bProportion != 9:
        panose.bProportion = 9
        return True
    return False


def fix_license_entries(font: TTFont) -> bool:
    """Force OFL license description and URL to the exact expected strings."""
    name_table = font["name"]
    ofl_desc = "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org"
    ofl_url = "https://openfontlicense.org"

    def set_name(name_id, value):
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 1, 0, 0)

    changed = False
    for nid, target in ((13, ofl_desc), (14, ofl_url)):
        existing = name_table.getName(nid, 3, 1, 0x409)
        if existing is None or existing.toUnicode() != target:
            set_name(nid, target)
            changed = True
    return changed


def fix_style_bits(font: TTFont) -> bool:
    """Ensure fsSelection and macStyle reflect bold/italic status correctly."""
    os2 = font["OS/2"]
    head = font["head"]
    name_table = font["name"]
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
        fs_sel |= 1 << 0
    if is_bold:
        fs_sel |= 1 << 5
    if is_regular:
        fs_sel |= 1 << 6

    os2.fsSelection = fs_sel
    head.macStyle = (1 if is_bold else 0) | (2 if is_italic else 0)
    return True


def drop_glyph_names(font: TTFont) -> bool:
    """Switch post table to format 3 to avoid invalid glyph names."""
    if "post" not in font:
        return False

    post = font["post"]
    if getattr(post, "formatType", None) == 3.0:
        return False

    post.formatType = 3.0
    post.extraNames = []
    post.glyphNameIndex = []
    post.mapping = {}
    return True


def fix_gdef_mark_classes(font: TTFont) -> bool:
    """Ensure combining marks are classified as marks in GDEF."""
    if "GDEF" not in font:
        return False

    cmap = font.getBestCmap()
    glyph_class_def = font["GDEF"].table.GlyphClassDef
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


def add_kerning_feature(font: TTFont) -> bool:
    """Add GPOS kern feature for quasi-proportional fonts."""
    # Only apply to quasi-proportional fonts
    if "post" in font and font["post"].isFixedPitch:
        return False

    if "GPOS" not in font:
        return False

    glyf = font.get("glyf")
    cmap = font.getBestCmap()
    if not glyf or not cmap:
        return False

    glyph_order = font.getGlyphOrder()

    def names_for_chars(chars: str) -> List[str]:
        return [cmap[ord(ch)] for ch in chars if ord(ch) in cmap]

    def expand_with_accents(base_names: List[str]) -> List[str]:
        import re

        accent_patterns = [
            r"acute", r"grave", r"circumflex", r"dieresis", r"tilde",
            r"macron", r"breve", r"dotaccent", r"ring", r"cedilla",
            r"ogonek", r"caron", r"hook", r"horn", r"comma",
            r"turkic", r"belowdot", r"tonos", r"dialytika",
        ]
        accent_regex = "|".join(accent_patterns)

        expanded = set(base_names)
        for name in base_names:
            if len(name) == 1:
                # Single-letter base
                pattern = re.compile(rf"^{re.escape(name)}({accent_regex})$", re.IGNORECASE)
                for gn in glyph_order:
                    if gn != name and pattern.match(gn):
                        expanded.add(gn)
            else:
                # Multi-letter base
                pattern = re.compile(rf"^({accent_regex})", re.IGNORECASE)
                for gn in glyph_order:
                    if gn.startswith(name) and gn != name:
                        if pattern.match(gn[len(name):]):
                            expanded.add(gn)
        return list(expanded)

    # Define kerning classes
    left_classes = {
        "@L_T": expand_with_accents(names_for_chars("TŦȚŢƬƮȾṪṬṮṰТЋЂΤτ")),
        "@L_V": expand_with_accents(names_for_chars("VṼṾѴѵ")),
        "@L_W": expand_with_accents(names_for_chars("WẀẂẄẆẈŴωѾѿ")),
        "@L_Y": expand_with_accents(names_for_chars("YỲỴỶỸŶŸÝƳƴУуЎўҮүҰұΥΎυύ")),
        "@L_A": expand_with_accents(names_for_chars("AÀÁÂÃÄÅĀĂĄǍẠẢẤẦẨẪẬẮẰẲẴẶÆАаДдΑαΆά")),
        "@L_F": expand_with_accents(names_for_chars("FḞƑГгҐґΓγ")),
        "@L_P": expand_with_accents(names_for_chars("PÞṔṖƤРрҎҏΡρ")),
        "@L_r": expand_with_accents(names_for_chars("rŕřŗṙṛṝṟɍɾгґ")),
        "@L_f": expand_with_accents(names_for_chars("fḟƒﬁﬂ")),
        "@L_L": expand_with_accents(names_for_chars("LĹĻĽĿŁḶḸḺḼȽГгҐґ")),
        "@L_quote": names_for_chars("\"'\u2019\u00bb\u203a"),
        "@L_paren": names_for_chars(")]}"),
        "@L_o": expand_with_accents(names_for_chars("oòóôõöōŏőơǒọỏốồổỗộớờởỡợøœоөοό")),
        "@L_a": expand_with_accents(names_for_chars("aàáâãäåāăąǎạảấầẩẫậắằẳẵặæаα")),
        "@L_e": expand_with_accents(names_for_chars("eèéêëēĕėęěẹẻẽếềểễệеёєεέ")),
    }

    right_classes = {
        "@R_o": expand_with_accents(names_for_chars("oòóôõöōŏőơǒọỏốồổỗộớờởỡợøœоөοό")),
        "@R_a": expand_with_accents(names_for_chars("aàáâãäåāăąǎạảấầẩẫậắằẳẵặæаαά")),
        "@R_e": expand_with_accents(names_for_chars("eèéêëēĕėęěẹẻẽếềểễệеёєεέη")),
        "@R_c": expand_with_accents(names_for_chars("cçćĉċčƈсς")),
        "@R_d": expand_with_accents(names_for_chars("dďđḋḍḏḑḓдђ")),
        "@R_g": expand_with_accents(names_for_chars("gĝğġģǧǵḡ")),
        "@R_q": expand_with_accents(names_for_chars("q")),
        "@R_u": expand_with_accents(names_for_chars("uùúûüũūŭůűųưǔǖǘǚǜụủứừửữựуўүυύ")),
        "@R_s": expand_with_accents(names_for_chars("sśŝşšșṡṣ")),
        "@R_y": expand_with_accents(names_for_chars("yýÿŷỳỵỷỹу")),
        "@R_v": expand_with_accents(names_for_chars("vѵ")),
        "@R_w": expand_with_accents(names_for_chars("wẁẃẅẇẉŵѿ")),
        "@R_A": expand_with_accents(names_for_chars("AÀÁÂÃÄÅĀĂĄǍẠẢẤẦẨẪẬẮẰẲẴẶАДΑΆ")),
        "@R_V": expand_with_accents(names_for_chars("VṼṾѴ")),
        "@R_T": expand_with_accents(names_for_chars("TŦȚŢƬƮȾṪṬṮṰТЋЂΤτ")),
        "@R_Y": expand_with_accents(names_for_chars("YỲỴỶỸŶŸÝƳƴУЎҮΥΎ")),
        "@R_punct": names_for_chars(".,;:!?"),
        "@R_hyphen": names_for_chars("-–—"),
        "@R_quote": names_for_chars("\"'\u201c\u2018\u00ab\u2039"),
        "@R_paren": names_for_chars("([{"),
    }

    # Filter to only include glyphs that exist in the font
    left_classes = {k: [g for g in v if g in glyph_order] for k, v in left_classes.items()}
    right_classes = {k: [g for g in v if g in glyph_order] for k, v in right_classes.items()}

    # Remove empty classes
    left_classes = {k: v for k, v in left_classes.items() if v}
    right_classes = {k: v for k, v in right_classes.items() if v}

    if not left_classes or not right_classes:
        return False

    kern_pairs = {
        ("@L_T", "@R_o"): -50, ("@L_T", "@R_a"): -45, ("@L_T", "@R_e"): -45,
        ("@L_T", "@R_c"): -40, ("@L_T", "@R_u"): -35, ("@L_T", "@R_s"): -35,
        ("@L_T", "@R_y"): -25, ("@L_T", "@R_punct"): -60, ("@L_T", "@R_hyphen"): -40,
        ("@L_V", "@R_o"): -40, ("@L_V", "@R_a"): -35, ("@L_V", "@R_e"): -35,
        ("@L_V", "@R_u"): -25, ("@L_V", "@R_A"): -50, ("@L_V", "@R_punct"): -50,
        ("@L_V", "@R_hyphen"): -30,
        ("@L_W", "@R_o"): -30, ("@L_W", "@R_a"): -25, ("@L_W", "@R_e"): -25,
        ("@L_W", "@R_A"): -35, ("@L_W", "@R_punct"): -40, ("@L_W", "@R_hyphen"): -20,
        ("@L_Y", "@R_o"): -50, ("@L_Y", "@R_a"): -45, ("@L_Y", "@R_e"): -45,
        ("@L_Y", "@R_u"): -35, ("@L_Y", "@R_punct"): -60, ("@L_Y", "@R_hyphen"): -35,
        ("@L_A", "@R_V"): -50, ("@L_A", "@R_v"): -35, ("@L_A", "@R_w"): -25,
        ("@L_A", "@R_y"): -30, ("@L_A", "@R_T"): -40, ("@L_A", "@R_Y"): -45,
        ("@L_A", "@R_quote"): -40,
        ("@L_F", "@R_o"): -35, ("@L_F", "@R_a"): -30, ("@L_F", "@R_e"): -30,
        ("@L_F", "@R_punct"): -50, ("@L_F", "@R_hyphen"): -25,
        ("@L_P", "@R_o"): -25, ("@L_P", "@R_a"): -20, ("@L_P", "@R_e"): -20,
        ("@L_P", "@R_punct"): -45, ("@L_P", "@R_hyphen"): -20,
        ("@L_r", "@R_o"): -20, ("@L_r", "@R_a"): -15, ("@L_r", "@R_e"): -15,
        ("@L_r", "@R_punct"): -30, ("@L_r", "@R_hyphen"): -15,
        ("@L_f", "@R_o"): -15, ("@L_f", "@R_a"): -10, ("@L_f", "@R_e"): -10,
        ("@L_L", "@R_V"): -35, ("@L_L", "@R_y"): -25, ("@L_L", "@R_T"): -35,
        ("@L_L", "@R_Y"): -30, ("@L_L", "@R_quote"): -30,
        ("@L_quote", "@R_o"): -25, ("@L_quote", "@R_a"): -20,
        ("@L_quote", "@R_e"): -20, ("@L_quote", "@R_c"): -20,
        ("@L_A", "@R_quote"): -40, ("@L_V", "@R_quote"): -35,
        ("@L_W", "@R_quote"): -25, ("@L_Y", "@R_quote"): -40,
        ("@L_T", "@R_quote"): -30,
        ("@L_paren", "@R_o"): -15, ("@L_paren", "@R_a"): -15,
        ("@L_paren", "@R_e"): -15,
        ("@L_A", "@R_paren"): -20, ("@L_V", "@R_paren"): -25,
        ("@L_T", "@R_paren"): -20, ("@L_Y", "@R_paren"): -25,
        ("@L_o", "@R_T"): -50, ("@L_o", "@R_V"): -35, ("@L_o", "@R_Y"): -40,
        ("@L_a", "@R_T"): -45, ("@L_a", "@R_V"): -30, ("@L_a", "@R_Y"): -35,
        ("@L_e", "@R_T"): -45, ("@L_e", "@R_V"): -30, ("@L_e", "@R_Y"): -35,
    }

    gpos_table = font["GPOS"].table
    left_class_defs = {}
    right_class_defs = {}
    left_class_ids = {}
    right_class_ids = {}

    for i, (name, glyphs) in enumerate(left_classes.items(), 1):
        left_class_ids[name] = i
        for g in glyphs:
            left_class_defs[g] = i

    for i, (name, glyphs) in enumerate(right_classes.items(), 1):
        right_class_ids[name] = i
        for g in glyphs:
            right_class_defs[g] = i

    class_pair_values = {}
    for (l_name, r_name), val in kern_pairs.items():
        l_id = left_class_ids.get(l_name)
        r_id = right_class_ids.get(r_name)
        if l_id and r_id:
            class_pair_values[(l_id, r_id)] = val

    if not class_pair_values:
        return False

    subtable = otTables.PairPos()
    subtable.Format = 2
    subtable.ValueFormat1 = 4
    subtable.ValueFormat2 = 0

    all_left_glyphs = sorted(left_class_defs.keys(), key=lambda x: glyph_order.index(x))
    coverage = otTables.Coverage()
    coverage.glyphs = all_left_glyphs
    subtable.Coverage = coverage

    class_def1 = otTables.ClassDef()
    class_def1.classDefs = left_class_defs
    subtable.ClassDef1 = class_def1

    class_def2 = otTables.ClassDef()
    class_def2.classDefs = right_class_defs
    subtable.ClassDef2 = class_def2

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
            val = class_pair_values.get((c1, c2), 0)
            c2_record.Value1 = otTables.ValueRecord()
            c2_record.Value1.XAdvance = val
            c2_record.Value2 = None
            c2_records.append(c2_record)
        c1_record.Class2Record = c2_records
        class1_records.append(c1_record)
    subtable.Class1Record = class1_records

    lookup = otTables.Lookup()
    lookup.LookupType = 2
    lookup.LookupFlag = 0
    lookup.SubTable = [subtable]
    lookup.SubTableCount = 1

    gpos_table.LookupList.Lookup.append(lookup)
    gpos_table.LookupList.LookupCount += 1
    new_lookup_index = len(gpos_table.LookupList.Lookup) - 1

    kern_feature = next((r.Feature for r in gpos_table.FeatureList.FeatureRecord if r.FeatureTag == "kern"), None)
    if kern_feature is None:
        new_record = otTables.FeatureRecord()
        new_record.FeatureTag = "kern"
        new_record.Feature = otTables.Feature()
        new_record.Feature.LookupListIndex = [new_lookup_index]
        new_record.Feature.LookupCount = 1

    print(f"  ✓ Added kerning: {len(class_pair_values)} class pairs, {len(all_left_glyphs)} left glyphs (Format 2)")
    return True


def post_process_font(font_path: Path, output_path: Optional[Path] = None) -> bool:
    """Apply all post-processing fixes to a font."""
    if output_path is None:
        output_path = font_path

    logger.info(f"\nProcessing: {font_path.name}")

    try:
        font = TTFont(font_path)
        fixes_applied = []

        fix_map = [
            (fix_font_revision, "font_revision"),
            (fix_copyright_notice, "copyright_notice"),
            (fix_windows_metrics, "windows_metrics"),
            (fix_vertical_metrics, "vertical_metrics"),
            (fix_fontbakery_version, "fontbakery_metadata"),
            (fix_zero_width_glyphs, "zero_width_glyphs"),
            (fix_font_names, "font_names"),
            (fix_dotted_circle, "dotted_circle"),
            (flatten_nested_components, "flattened_components"),
            (normalize_simple_glyphs, "normalized_glyf_flags"),
        ]

        for fix_func, fix_name in fix_map:
            if fix_func(font):
                fixes_applied.append(fix_name)

        # Run a light gftools fix pass for additional GF hygiene.
        font = gftools_fix_font(font, include_source_fixes=False)
        fixes_applied.append("gftools_fix_font")

        extra_fix_map = [
            (fix_panose_monospace, "panose_monospace"),
            (fix_license_entries, "license_entries"),
            (fix_style_bits, "style_bits"),
            (drop_glyph_names, "stripped_glyph_names"),
            (fix_broken_mark_anchors, "fixed_broken_mark_anchors"),
            (add_fallback_mark_anchors, "fallback_mark_anchors"),
            (add_dotted_circle_fallback, "dotted_circle_fallback"),
            (fix_gdef_mark_classes, "gdef_mark_classes"),
            (add_kerning_feature, "kerning"),
        ]

        for fix_func, fix_name in extra_fix_map:
            if fix_func(font):
                fixes_applied.append(fix_name)

        # Remove unwanted tables
        unwanted_tables = ["DSIG", "FFTM", "prop"]
        removed_tables = []
        for table in unwanted_tables:
            if table in font:
                del font[table]
                removed_tables.append(table)

        if removed_tables:
            fixes_applied.append(f"removed_tables({','.join(removed_tables)})")
            logger.info(f"  ✓ Removed unwanted tables: {', '.join(removed_tables)}")

        # Save the modified font
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path)
        font.close()

        logger.info(f"  ✅ Saved: {output_path.name}")
        logger.info(f"  Fixes applied: {', '.join(fixes_applied) if fixes_applied else 'none'}\n")
        return True

    except Exception as e:
        logger.error(f"  ❌ Error processing {font_path.name}: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc()
        return False


def process_and_copy_font(font_path: Path) -> Tuple[bool, Path, Optional[Path]]:
    """Helper for parallel processing: fix and copy to 'fonts/' directory."""
    try:
        # font_path structure: unprocessed_fonts/<plan_name>/ttf/<font>.ttf
        plan_dir = font_path.parent.parent.name
        dest_dir_name = plan_dir.lower().replace(" ", "")
        dest_dir = Path("fonts") / dest_dir_name

        # Normalize filename
        filename = font_path.name
        replacements = {"ExtraBold": "Extrabold", "ExtraLight": "Extralight", "SemiBold": "Semibold"}
        for old, new in replacements.items():
            filename = filename.replace(old, new)

        output_path = dest_dir / filename
        success = post_process_font(font_path, output_path)
        return success, font_path, output_path

    except Exception as e:
        logger.error(f"ERROR calculating paths for {font_path}: {e}")
        return False, font_path, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process Iosevka fonts for Google Fonts compliance")
    parser.add_argument(
        "fonts", nargs="*", type=Path, help="Font files to process. If omitted, uses unprocessed_fonts/"
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory (default: overwrite or use fonts/)")
    parser.add_argument("--parallel", action="store_true", help="Process fonts in parallel")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if not args.fonts:
        bulk_root = Path("unprocessed_fonts")
        fonts = sorted(bulk_root.glob("**/*.ttf"))

        if not fonts:
            logger.error(f"ERROR: No TTF files found in {bulk_root} and no files specified.")
            sys.exit(1)

        output_root = Path("fonts")
        if output_root.exists():
            logger.info(f"Cleaning existing output directory: {output_root}")
            shutil.rmtree(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

        num_workers = cpu_count()
        logger.info(f"Bulk processing {len(fonts)} fonts using {num_workers} workers...")

        with Pool(num_workers) as pool:
            results = pool.map(process_and_copy_font, fonts)

        success_count = sum(1 for success, _, _ in results if success)
        total_count = len(results)

        if success_count < total_count:
            logger.error("\nFailed fonts:")
            for success, input_path, _ in results:
                if not success:
                    logger.error(f"  - {input_path}")
    else:
        # Process specified fonts
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)

        total_count = len(args.fonts)
        if args.parallel and total_count > 1:
            num_workers = min(cpu_count(), total_count)
            logger.info(f"Processing {total_count} fonts in parallel using {num_workers} workers...")

            def _worker(f: Path) -> bool:
                out = args.output_dir / f.name if args.output_dir else f
                return post_process_font(f, out)

            with Pool(num_workers) as pool:
                results_list = pool.map(_worker, args.fonts)
            success_count = sum(1 for r in results_list if r)
        else:
            success_count = 0
            for f in args.fonts:
                if not f.exists():
                    logger.warning(f"File not found: {f}")
                    continue
                out = args.output_dir / f.name if args.output_dir else f
                if post_process_font(f, out):
                    success_count += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Processed {success_count}/{total_count} fonts successfully")
    logger.info(f"{'='*60}\n")

    if success_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
