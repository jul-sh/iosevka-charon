#!/usr/bin/env python3
from fontTools.ttLib import TTFont
import sys

f = TTFont(sys.argv[1])
nt = f['name']
print(f'Checking {sys.argv[1]}:')
print(f'Weight class: {f["OS/2"].usWeightClass}')
for name_id in [1, 2, 4, 6, 16, 17]:
    name = nt.getName(name_id, 3, 1, 0x409)
    if name:
        print(f'  NameID {name_id}: {name.toUnicode()}')
    else:
        print(f'  NameID {name_id}: MISSING')
