#!/usr/bin/env python3
from fontTools.ttLib import TTFont
import sys

f = TTFont(sys.argv[1])
print(f'Checking glyphs in {sys.argv[1]}:')
glyf = f['glyf']
hmtx = f['hmtx']
cmap = f.getBestCmap()

for gid in range(3756, 3763):
    name = f.getGlyphName(gid)
    width, lsb = hmtx[name]
    cp = [k for k, v in cmap.items() if v == name]
    print(f'  gid{gid}: {name}, width={width}, cp={hex(cp[0]) if cp else "None"}')
