#!/usr/bin/env python3
"""Diagnostic script to compare original vs processed font anchors."""

from fontTools.ttLib import TTFont

# Check anchor in ORIGINAL font
orig = TTFont('general_use_fonts/iosevkacharonmono/IosevkaCharonMono-Regular.ttf')
cmap = orig.getBestCmap()
orig_gpos = orig['GPOS'].table

turned_v = cmap.get(0x028C)
double_grave = cmap.get(0x030F)

print('ORIGINAL font:')
for idx, lookup in enumerate(orig_gpos.LookupList.Lookup):
    for subtable in lookup.SubTable:
        real_st = subtable
        if lookup.LookupType == 9 and hasattr(subtable, 'ExtSubTable'):
            real_st = subtable.ExtSubTable
        if getattr(real_st, 'LookupType', lookup.LookupType) != 4:
            continue
        if not real_st.MarkCoverage or not real_st.BaseCoverage:
            continue
        if double_grave not in real_st.MarkCoverage.glyphs:
            continue
        if turned_v not in real_st.BaseCoverage.glyphs:
            continue
        m_idx = real_st.MarkCoverage.glyphs.index(double_grave)
        m_rec = real_st.MarkArray.MarkRecord[m_idx]
        b_idx = real_st.BaseCoverage.glyphs.index(turned_v)
        b_rec = real_st.BaseArray.BaseRecord[b_idx]
        base_anchor = b_rec.BaseAnchor[m_rec.Class]
        print(f'  Lookup {idx}: mark Y={m_rec.MarkAnchor.YCoordinate}, base Y={base_anchor.YCoordinate}')

# Check anchor in PROCESSED font
proc = TTFont('fonts/iosevkacharonmono/IosevkaCharonMono-Regular.ttf')
cmap = proc.getBestCmap()
proc_gpos = proc['GPOS'].table

turned_v = cmap.get(0x028C)
double_grave = cmap.get(0x030F)

print('\nPROCESSED font:')
for idx, lookup in enumerate(proc_gpos.LookupList.Lookup):
    for subtable in lookup.SubTable:
        real_st = subtable
        if lookup.LookupType == 9 and hasattr(subtable, 'ExtSubTable'):
            real_st = subtable.ExtSubTable
        if getattr(real_st, 'LookupType', lookup.LookupType) != 4:
            continue
        if not real_st.MarkCoverage or not real_st.BaseCoverage:
            continue
        if double_grave not in real_st.MarkCoverage.glyphs:
            continue
        if turned_v not in real_st.BaseCoverage.glyphs:
            continue
        m_idx = real_st.MarkCoverage.glyphs.index(double_grave)
        m_rec = real_st.MarkArray.MarkRecord[m_idx]
        b_idx = real_st.BaseCoverage.glyphs.index(turned_v)
        b_rec = real_st.BaseArray.BaseRecord[b_idx]
        base_anchor = b_rec.BaseAnchor[m_rec.Class]
        print(f'  Lookup {idx}: mark Y={m_rec.MarkAnchor.YCoordinate}, base Y={base_anchor.YCoordinate}')
