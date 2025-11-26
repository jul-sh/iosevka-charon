# Analysis: Fixing Nested Components Upstream in Iosevka

## Root Cause

The nested components issue originates in `/sources/iosevka/packages/font-glyphs/src/common/derivatives.ptl` at lines 218-237.

The `derive-composites` function creates composite glyphs by referencing other glyphs:

```ptl
define [derive-composites dstGid dstUnicode srcGid] : begin
    # ... creates component references without checking if source is composite
    include [refer-glyph srcs.(rid)] asBase alsoMetrics
```

**Problem**: When `srcs.(rid)` is itself a composite glyph, this creates a nested component reference.

## Affected Glyphs (165 total)

- **Greek polytonic** (majority): Greek letters with multiple diacritical marks
- **Roman numerals**: ii, iii, iv, vi, vii, viii, ix, xi, xii
- **Latin with diacritics**: iogonek, various combinations
- **Digraphs**: ij, DZ variants
- **Special characters**: quotedblright, etc.

## Upstream Fix Options

### Option 1: Modify Iosevka Core ⚠️ HIGH RISK
**Approach**: Patch `derive-composites` to detect and expand nested component references.

**Implementation**:
```ptl
# Add check before including component:
if ([query-glyph srcs.(rid)].isComposite)
    then: # expand the nested components
    else: include [refer-glyph srcs.(rid)] asBase alsoMetrics
```

**Risks**:
- Could break 200+ glyph definitions across the codebase
- Requires testing all font variants
- May affect font file size significantly
- Changes core font generation logic

**Complexity**: VERY HIGH

### Option 2: Post-Processing (Current Approach) ✅ MODERATE RISK
**Approach**: Use `fix_fonts.py` to flatten nested components after build.

**Status**: Implementation exists but causes OTS glyph flag errors

**Pros**:
- Isolated change, doesn't affect Iosevka source
- Can be disabled if issues arise
- Easier to debug

**Cons**:
- Currently introduces OTS corruption
- Requires careful glyph structure handling

**Complexity**: HIGH

### Option 3: Report to Iosevka Upstream 📝 LONG-TERM
**Approach**: File an issue with Iosevka project requesting built-in support.

**Timeline**: Months

##Recommendation

**Short-term**: Fix the post-processing OTS error (Option 2)
**Long-term**: File upstream issue (Option 3)

The nested components are a design decision in Iosevka for file size optimization. Fixing it properly requires upstream Iosevka changes or very careful post-processing.
