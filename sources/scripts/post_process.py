#!/usr/bin/env python3
"""
Experimental post-processing script to make a TTF font Google Fonts compliant.

This script performs several common fixes aiming for GF compliance:
- Subsets the font (e.g., using GF_Latin_Core.nam).
- Reuses space glyph for U+00A0.
- Aligns head.fontRevision and nameID 5 (Version).
- Drops hinting.
- Sets OFL license nameIDs (13, 14).
- Fixes potentially invalid 'glyf' table flags.
- Adjusts OS/2 vertical metrics (usWinAscent, sTypoAscender).
- Adjusts hhea vertical metrics (ascent).
- Flattens composite glyphs.

WARNING: This is experimental. Use with caution and verify results.
"""

import os
import sys
import subprocess
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontbakery.constants import NameID

# Constants
# ----------------------------------------------------------------------------

# OFL license data
OFL_LICENSE_DESCRIPTION = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)
OFL_LICENSE_INFO_URL = "https://openfontlicense.org"

# Font version information
FONT_VERSION_STRING = "Version 32.5.0"  # Version string for nameID=5
FONT_REVISION_FLOAT = 32.5              # head.fontRevision (16.16 fixed-point float)

# Font metrics adjustments
ASCENT_VALUE = 985  # Value for usWinAscent, sTypoAscender, and hhea.ascent

class FlattenPen(BasePen):
    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours = []
        self.currentContour = []

    def moveTo(self, p0):
        if self.currentContour:
            self.contours.append(self.currentContour)
        self.currentContour = [p0]

    def lineTo(self, p1):
        self.currentContour.append(p1)

    def curveTo(self, p1, p2, p3):
        self.currentContour.append(p1)
        self.currentContour.append(p2)
        self.currentContour.append(p3)

    def closePath(self):
        if self.currentContour:
            self.contours.append(self.currentContour)
        self.currentContour = []

    def getContours(self):
        if self.currentContour:
            self.contours.append(self.currentContour)
        return self.contours

def flatten_glyphs(font):
    """Flatten composite glyphs into simple glyphs with coordinates."""
    glyph_set = font.getGlyphSet()

    # Iterate through all glyphs in the font
    for glyph_name in font['glyf'].keys():
        glyph = font['glyf'][glyph_name]

        # Skip if the glyph is simple (not a composite)
        if not glyph.isComposite():
            continue

        # Create a pen to collect the flattened coordinates
        flatten_pen = FlattenPen(glyph_set)
        transform_pen = TransformPen(flatten_pen, (1, 0, 0, 1, 0, 0))

        try:
            # First establish current point with a moveTo
            transform_pen.moveTo((0, 0))
            # Draw the composite glyph to the pen, which will flatten it
            glyph_set[glyph_name].draw(transform_pen)
        except Exception as e:
            print(f"Warning: Could not flatten glyph {glyph_name}: {str(e)}")
            continue

        # Get the flattened contours
        contours = flatten_pen.getContours()

        # Convert the glyph to a simple glyph
        glyph.components = []  # Remove components
        glyph.coordinates = []
        glyph.flags = []
        glyph.endPtsOfContours = []

        # Add the flattened contour data
        for contour in contours:
            start_pt = len(glyph.coordinates)
            for x, y in contour:
                glyph.coordinates.append((x, y))
                glyph.flags.append(1)  # Mark all points as on-curve
            glyph.endPtsOfContours.append(start_pt + len(contour) - 1)

    return font

def parse_nam_file(file_path):
    """Parse a .nam file and return list of codepoints."""
    codepoints = []

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):  # Ignore empty lines and comments
                try:
                    code_point = int(line.split()[0], 16)  # Get hex value before comment
                    codepoints.append(code_point)
                except ValueError:
                    print(f"Skipping invalid line: {line}")

    return codepoints

def set_license_description(ttFont, license_text):
    """Ensure NameID 13 (LICENSE DESCRIPTION) matches the provided text."""
    name_table = ttFont["name"]
    found_license = False
    for record in name_table.names:
        if record.nameID == NameID.LICENSE_DESCRIPTION:  # 13
            found_license = True
            if record.toUnicode() != license_text:
                record.string = license_text.encode(record.getEncoding())
    if not found_license:
        # Windows
        name_table.setName(license_text, NameID.LICENSE_DESCRIPTION, 3, 1, 0x409)
        # Mac
        name_table.setName(license_text, NameID.LICENSE_DESCRIPTION, 1, 0, 0)

def set_license_info_url(ttFont, license_url):
    """Ensure NameID 14 (LICENSE INFO URL) is set to the provided URL."""
    name_table = ttFont["name"]
    found_license_url = False
    for record in name_table.names:
        if record.nameID == NameID.LICENSE_INFO_URL:  # 14
            found_license_url = True
            if record.toUnicode() != license_url:
                record.string = license_url.encode(record.getEncoding())
    if not found_license_url:
        # Windows
        name_table.setName(license_url, NameID.LICENSE_INFO_URL, 3, 1, 0x409)
        # Mac
        name_table.setName(license_url, NameID.LICENSE_INFO_URL, 1, 0, 0)

def reuse_space_for_non_breaking_space(ttFont):
    """
    Reuse the same glyph for U+00A0 (no-break space) as U+0020 (space),
    if missing.
    """
    cmap_table = None
    for table in ttFont["cmap"].tables:
        if table.isUnicode():
            cmap_table = table.cmap
            break
    if not cmap_table:
        return  # No unicode cmap found

    space_glyph = cmap_table.get(0x0020)
    if not space_glyph:
        return  # No space glyph to reuse

    if 0x00A0 not in cmap_table:
        # Map U+00A0 to the same glyph as U+0020
        cmap_table[0x00A0] = space_glyph

def fix_font_version(ttFont, version_string, revision_float):
    """
    1) Sets 'head.fontRevision' to 'revision_float'.
    2) Updates nameID=5 (VERSION_STRING) to 'version_string' on major platforms.
    """
    # 1) head.fontRevision
    ttFont["head"].fontRevision = revision_float

    # 2) nameID=5
    name_table = ttFont["name"]
    for record in name_table.names:
        if record.nameID == NameID.VERSION_STRING:  # 5
            # Example final name ID 5 text is "Version 32.5.0"
            if record.toUnicode() != version_string:
                record.string = version_string.encode(record.getEncoding())

    # If you want to ensure both Windows and Mac entries exist:
    name_table.setName(version_string, NameID.VERSION_STRING, 3, 1, 0x409)  # Win
    name_table.setName(version_string, NameID.VERSION_STRING, 1, 0, 0)      # Mac

def subset_basic_latin_plus_nbsp(input_path, output_path):
    """
    1) Subset the font to Basic Latin (U+0020–U+007E) plus U+00A0.
    2) Reuse space glyph for U+00A0.
    3) Drop hinting to avoid OTS "Bad glyph flag" errors.
    4) Fix NameID 13, 14, and version mismatch.
    5) Fix invalid glyph flags in glyf table.
    6) Flatten composite glyphs.
    """

    # Get git repo root using git rev-parse
    repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
    nam_path = os.path.join(repo_root, "sources", "GF_Latin_Core.nam")

    # Parse codepoints from nam file
    codepoints = parse_nam_file(nam_path)

    # Set up subset options
    options = subset.Options()
    # If hinting data is causing OTS errors, remove it by setting hinting=False:
    options.hinting = False
    # Other subset options:
    options.desubroutinize = True
    options.notdef_outline = True
    options.recalc_bounds = True
    options.recalc_timestamp = True
    # This can help remove certain tables
    options.drop_tables = ["DSIG"]
    # We only keep the codepoints we care about
    options.unicodes = codepoints

    # Load font
    font = subset.load_font(input_path, options)

    # Subset
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)

    # 1) Fix version mismatch
    fix_font_version(font, FONT_VERSION_STRING, FONT_REVISION_FLOAT)

    # 2) Fix licensing name IDs
    set_license_description(font, OFL_LICENSE_DESCRIPTION)
    set_license_info_url(font, OFL_LICENSE_INFO_URL)

    # 3) Reuse space glyph for U+00A0
    reuse_space_for_non_breaking_space(font)

    # 4) Fix invalid glyph flags
    glyf_table = font["glyf"]
    for glyph_name in glyf_table.keys():
        glyph = glyf_table[glyph_name]
        # Check only simple glyphs (not composite)
        if not glyph.isComposite():
            # This call should still exist in older fontTools
            coords, endPts, flags = glyph.getCoordinates(glyf_table)

            # Clear bit 6 (0x40)
            new_flags = [flag & ~0x40 for flag in flags]

            # Manually re-assign the data back to the glyph
            glyph.coordinates = coords
            glyph.endPtsOfContours = endPts
            glyph.flags = new_flags

            # Optional: recalc bounding box
            glyph.recalcBounds(glyf_table)

    # 5) Fix OS/2 usWinAscent, sTypoAscender and hhea ascent values
    font["OS/2"].usWinAscent = ASCENT_VALUE
    font["OS/2"].sTypoAscender = ASCENT_VALUE
    font["hhea"].ascent = ASCENT_VALUE

    # 6) Flatten composite glyphs
    font = flatten_glyphs(font)

    # Save
    subset.save_font(font, output_path, options)
    print(f"Post-processed font saved to: {output_path}")

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.ttf> <output.ttf>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    subset_basic_latin_plus_nbsp(input_path, output_path)

if __name__ == "__main__":
    main()
