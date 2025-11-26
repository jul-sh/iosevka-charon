# Walkthrough: Upstream Fixes for Fontbakery Validation

I successfully implemented upstream fixes directly in the Iosevka submodule to resolve fontbakery validation issues, complementing the post-processing fixes that were already in place.

## Changes Made

### 1. Fixed Zero-Width Base Characters ✅
**Problem**: Characters `uni055F`, `uniEF01`, and `uniEF02` had zero advance width, failing the `base_has_width` check.

**Files Modified**:

#### [`marks/composite.ptl`](file:///usr/local/google/home/julsh/git/iosevka-charon/sources/iosevka/packages/font-glyphs/src/marks/composite.ptl)
- **Line 53**: Changed `uniEF01` (psiliPerispomeni) from `set-width 0` to `set-width [query-glyph 'markBaseSpace'].advanceWidth`
- **Line 83**: Changed `uniEF02` (dasiaPerispomeni) from `set-width 0` to `set-width [query-glyph 'markBaseSpace'].advanceWidth`

#### [`marks/above.ptl`](file:///usr/local/google/home/julsh/git/iosevka-charon/sources/iosevka/packages/font-glyphs/src/marks/above.ptl)
- **Line 1409**: Changed `uni055F` (Armenian abbreviation mark) from `set-width 0` to `set-width Width`

---

### 2. Added Mark Anchors to Dotted Circle 🔧
**Problem**: Dotted circle (U+25CC) existed but marks could not attach to it.

**File Modified**: [`symbol/geometric/dotted.ptl`](file:///usr/local/google/home/julsh/git/iosevka-charon/sources/iosevka/packages/font-glyphs/src/symbol/geometric/dotted.ptl)
- **Lines 67-69**: Added mark anchors to the dotted circle glyph:
  - `set-base-anchor 'above' Geom.MidX Geom.Top`
  - `set-base-anchor 'below' Geom.MidX Geom.Bot`
  - `set-base-anchor 'overlay' Geom.MidX Geom.MidY`

> [!NOTE]
> This partially addresses the `dotted_circle` failure. Some marks (uni1AC1-uni1AC4) still cannot attach, which may require additional anchor types.

---

## Results

### Before Upstream Fixes
```
IosevkaCharon-Regular.ttf: base_has_width: FAIL [zero-width-bases]
IosevkaCharon-Regular.ttf: fontbakery_version: FAIL [outdated-fontbakery]
IosevkaCharon-Regular.ttf: nested_components: FAIL [found-nested-components]
IosevkaCharon-Regular.ttf: googlefonts/glyphsets/shape_languages: ERROR [failed-check]
IosevkaCharon-Regular.ttf: dotted_circle: FAIL [unattached-dotted-circle-marks]

ERROR: 1 FATAL: 0 FAIL: 4 WARN: 23 INFO: 6 SKIP: 107 PASS: 94
```

### After Upstream Fixes
```
IosevkaCharon-Regular.ttf: fontbakery_version: FAIL [outdated-fontbakery]
IosevkaCharon-Regular.ttf: nested_components: FAIL [found-nested-components]
IosevkaCharon-Regular.ttf: googlefonts/glyphsets/shape_languages: ERROR [failed-check]
IosevkaCharon-Regular.ttf: dotted_circle: FAIL [unattached-dotted-circle-marks]

ERROR: 1 FATAL: 0 FAIL: 3 WARN: 23 INFO: 6 SKIP: 107 PASS: 95
```

**Improvement**: **1 additional FAIL resolved** (`base_has_width` now PASSES ✅)

---

## Remaining Issues

### 1. `fontbakery_version` ⚠️
**Status**: Environment issue - outdated fontbakery (0.13.2 vs 1.1.0)
**Fix**: Upgrade fontbakery: `pip install -U fontbakery`

### 2. `nested_components` ⚠️
**Status**: Deep structural issue requiring complex refactoring
**Recommendation**: Address in a future update or accept as a known limitation

### 3. `dotted_circle` ⚠️
**Status**: Partially fixed - glyph now has basic anchors
**Issue**: Specific marks (uni1AC1-uni1AC4) still cannot attach
**Recommendation**: Investigate required anchor types for these specific combining marks

### 4. `googlefonts/glyphsets/shape_languages` ❌
**Status**: ERROR (not FAIL) - needs investigation
**Recommendation**: Run with verbose logging to understand the error

---

## Summary

Combined with the post-processing fixes from [`fix_fonts.py`](file:///usr/local/google/home/julsh/git/iosevka-charon/sources/scripts/fix_fonts.py), we have successfully resolved **6 out of 9** original FAIL issues:

✅ **Fixed** (6):
- Font Revision
- Windows Metrics
- Vertical Metrics (Hhea/Typo)
- Font Names
- Unwanted Tables
- **Zero-Width Base Characters** (upstream fix)

⚠️ **Remaining** (3):
- Fontbakery Version (environment)
- Nested Components (complex)
- Dotted Circle (partial fix)

The font is now in significantly better shape for Google Fonts compliance!
