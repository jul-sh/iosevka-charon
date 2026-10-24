#!/usr/bin/env python3
"""Iosevka Caleuche with Kerberos's x-height behaviour: an optical-size axis that raises the
x-height below 20 pt, and the lowercase height axis (YTLC 500-550), as variable fonts.

Kerberos (the serif Caleuche pairs with) grows its x-height at small sizes and offers a taller
x-height on its YTLC axis. Iosevka builds made at different x-heights do not interpolate (its
curve conversion and overlap removal give some glyphs different points), so the taller shape is
derived from each built static instead, the way Kerberos derives its own: the lowercase stretches
in the x-height zone while ascenders, capitals and descenders stay; accents and dots ride along
with the top of their letter (over an ascender they stay, the dot of i and j rises a little less);
colon, hyphen and the like move with the x-height; mark attachment points on the lowercase follow.
Every corner of the design space is then the drawn static plus a share of that change, so the
variable font matches Kerberos at every size:

    Regular roman (per 1000 em)   8 pt   14 pt   20 pt and up
    YTLC 500                 515    485     461 (the drawn static)
    YTLC 550                 525    507     507

Kerberos 1.4.2's zones and optical-size targets are pinned in sources/caleuche-kerberos.json,
including each weight/style's own heights and its 12 pt optical-size master.
One variable font per static (weights are drawn separately and do not interpolate), unhinted:
fonts/iosevkacaleuche/variable/IosevkaCaleuche-<Style>[YTLC,opsz].ttf

    python3 scripts/caleuche_variable.py [STATIC.ttf ...] [--out DIR]
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import sys
import tempfile
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, InstanceDescriptor, SourceDescriptor
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.varLib import build as build_variable

# Pinned Kerberos metrics keep the build reproducible without another checkout/network access.
KERBEROS = json.loads((Path(__file__).resolve().parents[1] / "sources/caleuche-kerberos.json").read_text())
ASCENDER = KERBEROS["ascender"]
OPSZ = (8, 14, 72)
YTLC = (500, 500, 550)
OPSZ_NAMES = (8, 9, 10, 11, 12, 14, 16, 17, 18, 20, 24, 28, 36, 48, 60, 72)   # STAT, as in Kerberos
WEIGHTS = {300: "Light", 400: "Regular", 500: "Medium", 700: "Bold"}
DOT_SHARE = 0.6        # the dots of i and j rise by less, so they do not climb past the ascenders
GAP_POWER = 3.0        # the larger an empty stretch of outline, the more of the stretch it takes
MAX_SQUEEZE = 0.7      # never compress an outline faster than this
STEM_SQUEEZE = 0.92    # a straight stem can shorten almost all the way
EMPTY_SQUEEZE = 0.9    # empty space above a short ascender (t) closes first
STEM_SLOPE = 0.2       # a straight edge this close to vertical is a stem
STEM_RUN = 0.4         # ... if the ink across it is no wider than this share of the x-height
PUNCTUATION = {":", ";", "-", "\u00ad", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u00b7",
               "\u2022", "\u00ab", "\u00bb", "\u2039", "\u203a", "\u0387", "\u037e"}
DOTTED = {"i", "j", "\u0456", "\u0458", "\u012f", "\u0133"}


# ------------------------------------------------------------------------------------------------
# which glyphs follow

def _dotted(ch: str) -> bool:
    """i and j, and their styled forms (the mathematical 𝑖, ⅈ)"""
    if ch in DOTTED:
        return True
    parts = unicodedata.decomposition(ch).split()
    return len(parts) == 2 and parts[0] == "<font>" and chr(int(parts[1], 16)) in DOTTED


def roles(font: TTFont) -> tuple[dict, set, set, set]:
    """(glyph -> char, stretched glyphs, punctuation glyphs, dotted glyphs)"""
    glyf = font["glyf"]
    x_height = font["OS/2"].sxHeight
    cmap = font.getBestCmap()
    char_of = {}
    for cp, name in cmap.items():
        char_of.setdefault(name, chr(cp))
    lower = {g for g, ch in char_of.items() if unicodedata.category(ch) == "Ll"}
    upper = {g for g, ch in char_of.items() if unicodedata.category(ch) in ("Lu", "Lt")}
    changed = True
    while changed:
        changed = False
        # alternates and ligatures of lowercase letters (GSUB closure)
        if "GSUB" in font:
            for lookup in font["GSUB"].table.LookupList.Lookup:
                for st in lookup.SubTable:
                    st = st.ExtSubTable if lookup.LookupType == 7 else st
                    kind = st.LookupType if lookup.LookupType == 7 else lookup.LookupType
                    pairs = []
                    if kind == 1:
                        pairs = [([a], [b]) for a, b in st.mapping.items()]
                    elif kind == 3:
                        pairs = [([a], bs) for a, bs in st.alternates.items()]
                    elif kind == 4:
                        pairs = [([first] + lig.Component, [lig.LigGlyph])
                                 for first, ligs in st.ligatures.items() for lig in ligs]
                    for ins, outs in pairs:
                        if all(g in lower for g in ins):
                            for g in outs:
                                if g not in lower and g not in upper:
                                    lower.add(g)
                                    changed = True
        # the unencoded bodies lowercase composites are built on (the d of ď, used in place)
        # stretch with them
        for name in list(lower):
            g = glyf[name]
            if not g.isComposite():
                continue
            for comp in g.components:
                c = comp.glyphName
                if c in lower or c in char_of or comp.y or hasattr(comp, "transform"):
                    continue
                b = bounds_of(c, glyf)
                if b and b[1] <= x_height + 10 and b[3] >= x_height - 10:
                    lower.add(c)
                    changed = True
    punct = {g for g, ch in char_of.items() if ch in PUNCTUATION}
    dotted = {g for g, ch in char_of.items() if _dotted(ch)}
    return char_of, lower, punct, dotted


# ------------------------------------------------------------------------------------------------
# the vertical move (a trimmed copy of Kerberos's scripts/xheight_axis.py)

class Edges:
    def __init__(self, contours):
        self.pieces, self.ys = [], []
        for pts in contours:                      # [(x, y, on)]
            self.ys += [p[1] for p in pts]
            n = len(pts)
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                self.pieces.append((a[0], a[1], b[0], b[1], STEM_SLOPE if a[2] and b[2] else -1.0))
        self.top = max(self.ys) if self.ys else None
        self._columns = None

    @staticmethod
    def _runs(hits):
        runs, winding, start = [], 0, None
        for pos, sign in sorted(hits):
            before, winding = winding, winding + sign
            if before == 0 and winding:
                start = pos
            elif before and not winding:
                runs.append((start, pos))
        return runs

    def columns(self, samples=24):
        if self._columns is None:
            xs = [p[0] for p in self.pieces] + [p[2] for p in self.pieces]
            lo, hi = min(xs), max(xs)
            self._columns = []
            for s in range(samples):
                x = lo + (hi - lo) * (s + 0.5) / samples
                hits = [(y0 + (x - x0) * (y1 - y0) / (x1 - x0), 1 if x1 > x0 else -1)
                        for x0, y0, x1, y1, _ in self.pieces if (x0 <= x < x1) or (x1 <= x < x0)]
                self._columns.append(self._runs(hits))
        return self._columns

    def kind(self, y, x_height):
        hits, stems = [], True
        for x0, y0, x1, y1, tolerance in self.pieces:
            if (y0 <= y < y1) or (y1 <= y < y0):
                slope = (x1 - x0) / (y1 - y0)
                hits.append((x0 + (y - y0) * slope, 1 if y1 > y0 else -1))
                stems = stems and abs(slope) <= tolerance
        if not hits:
            return "empty"
        if any(a < y < b and b - a < 0.35 * x_height for runs in self.columns() for a, b in runs):
            return "stroke"
        if stems and all(b - a <= STEM_RUN * x_height for a, b in self._runs(hits)):
            return "stem"
        return "other"


class Move:
    def __init__(self, x_height, ascender, d, edges=None):
        self.x, self.d = x_height, d
        self.b0, self.t0, self.p1 = 0.2 * x_height, 0.8 * x_height, 1.15 * x_height
        self.z0 = ascender - 0.116 * 741
        if edges is not None and edges.top is not None and edges.top < ascender - 50:
            self.z0 = ascender
        ys = sorted(set(round(y, 2) for y in edges.ys)) if edges is not None else []
        self.rise = self._spread(ys, self.b0, self.t0)
        self.fall = self._squeeze(ys, edges)

    @staticmethod
    def _spread(ys, lo, hi):
        cuts = [lo] + [y for y in ys if lo < y < hi] + [hi]
        weights = [(b - a) ** GAP_POWER for a, b in zip(cuts, cuts[1:])]
        s = sum(weights) or 1.0
        out, acc = [(lo, 0.0)], 0.0
        for c, w in zip(cuts[1:], weights):
            acc += w / s
            out.append((c, min(acc, 1.0)))
        return out

    def _squeeze(self, ys, edges):
        lo, hi = self.p1, self.z0
        cuts = [lo] + [y for y in ys if lo < y < hi] + [hi]
        if hi <= lo or len(cuts) == 2 or edges is None:
            return [(lo, 0.0), (max(hi, lo + 1), 1.0)]
        gaps = [b - a for a, b in zip(cuts, cuts[1:])]
        kinds = [edges.kind((a + b) / 2, self.x) for a, b in zip(cuts, cuts[1:])]
        rates = {"empty": EMPTY_SQUEEZE, "stem": STEM_SQUEEZE}
        cap = [rates.get(k, MAX_SQUEEZE) * g for k, g in zip(kinds, gaps)]
        take, left = [0.0] * len(gaps), float(self.d)
        for k in ("empty", "stem", "other", "stroke"):
            idx = [i for i in range(len(gaps)) if kinds[i] == k and cap[i] > 0]
            room = sum(cap[i] for i in idx)
            if not idx or left <= 1e-9:
                continue
            part = min(left, room)
            for i in idx:
                take[i] += part * cap[i] / room
            left -= part
        if left > 1e-9:
            for i, g in enumerate(gaps):
                take[i] += left * g / sum(gaps)
        out, acc = [(lo, 0.0)], 0.0
        for c, t in zip(cuts[1:], take):
            acc += t / self.d
            out.append((c, min(acc, 1.0)))
        return out

    @staticmethod
    def _interp(points, y):
        ys = [p[0] for p in points]
        i = bisect.bisect_right(ys, y)
        if i <= 0:
            return points[0][1]
        if i >= len(points):
            return points[-1][1]
        (y0, s0), (y1, s1) = points[i - 1], points[i]
        return s0 + (s1 - s0) * (y - y0) / (y1 - y0) if y1 > y0 else s1

    def delta(self, y):
        if y <= self.b0:
            return 0.0
        if y < self.t0:
            return self.d * self._interp(self.rise, y)
        if y <= self.p1:
            return float(self.d)
        if y < self.z0:
            return self.d * (1.0 - self._interp(self.fall, y))
        return 0.0

    def body(self, y):
        if y <= self.b0:
            return 0.0
        if y < self.t0:
            return self.d * (y - self.b0) / (self.t0 - self.b0)
        return float(self.d)


class Lifted:
    """mark attachment on a lowercase letter: over its top (where accents sit) it rises as far as
    the top does, as the accents of precomposed letters do; on the letter it follows the outline"""

    def __init__(self, move, lift: float, top: float):
        self.move, self.lift, self.top = move, lift, top

    def delta(self, y):
        return self.lift if y >= self.top else self.move.delta(y)


def clustered(points, deltas, radius=14.0, max_extent=40.0):
    n = len(points)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(n), key=lambda i: points[i][0])
    for a, i in enumerate(order):
        for j in order[a + 1:]:
            if points[j][0] - points[i][0] > radius:
                break
            if (points[j][0] - points[i][0]) ** 2 + (points[j][1] - points[i][1]) ** 2 < radius * radius:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = list(deltas)
    for members in groups.values():
        if len(members) > 1 and max(points[i][1] for i in members) - min(points[i][1] for i in members) <= max_extent:
            mean = sum(deltas[i] for i in members) / len(members)
            for i in members:
                out[i] = mean
    return out


def floating(contours, x_height) -> set:
    """contours of the marks drawn into a letter (the dot of 𝑖): clear of its body, over the
    x-height. Contours whose boxes overlap belong together (a dot and its counter)."""
    boxes = [(min(p[0] for p in c), min(p[1] for p in c), max(p[0] for p in c), max(p[1] for p in c))
             for c in contours]
    parent = list(range(len(boxes)))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(boxes)):
        groups.setdefault(find(i), []).append(i)
    out = {i for members in groups.values() if min(boxes[i][1] for i in members) >= x_height + 10
           for i in members}
    return out if len(out) < len(boxes) else set()


# ------------------------------------------------------------------------------------------------
# the taller shape of one static

def contours_of(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append([(coords[i][0], coords[i][1], bool(flags[i] & 1)) for i in range(start, end + 1)])
        start = end + 1
    return out


def bounds_of(name, glyf):
    g = glyf[name]
    if g.isComposite() or g.numberOfContours > 0:
        g.recalcBounds(glyf)
        return (g.xMin, g.yMin, g.xMax, g.yMax) if hasattr(g, "yMin") else None
    return None


def derive(font: TTFont, full: int) -> dict:
    """{"shift": {glyph: [(dx, dy) per point, or per component]}, "moves": {glyph: delta(y)} for
    its anchors}, at the full change (the static x-height -> full)"""
    glyf = font["glyf"]
    x_height = font["OS/2"].sxHeight
    slant = math.tan(math.radians(-font["post"].italicAngle))
    sl = lambda dy: (round(dy * slant), round(dy))
    d = full - x_height
    char_of, lower, punct, dotted = roles(font)
    generic = Move(x_height, ASCENDER, d)
    moves, shift, tops = {}, {}, {}
    for name in font.getGlyphOrder():
        g = glyf[name]
        if name in lower and not g.isComposite() and g.numberOfContours > 0:
            cs = contours_of(g, glyf)
            marks = floating(cs, x_height)
            body = [c for i, c in enumerate(cs) if i not in marks]
            mv = Move(x_height, ASCENDER, d, Edges(body))
            pts = [(x, y) for c in cs for x, y, _ in c]
            ds = clustered(pts, [mv.delta(y) for _, y in pts])
            # how far the top of the letter rises: marks drawn into it ride along by as much
            owner = [i for i, c in enumerate(cs) for _ in c]
            top = max(y for (_, y), i in zip(pts, owner) if i not in marks)
            at_top = [dy for (_, y), i, dy in zip(pts, owner, ds) if i not in marks and y >= top - 1]
            tops[name] = sum(at_top) / len(at_top)
            lift = tops[name] * (DOT_SHARE if name in dotted else 1.0)
            ds = [lift if i in marks else dy for i, dy in zip(owner, ds)]
            shift[name] = [sl(v) for v in ds]
            moves[name] = Lifted(mv, tops[name], top)
        elif name in punct and not g.isComposite() and g.numberOfContours > 0:
            out = []
            for c in contours_of(g, glyf):
                ys = [y for _, y, _ in c]
                out += [sl(generic.body((min(ys) + max(ys)) / 2))] * len(c)
            shift[name] = out

    def tallest(name):
        """(top, name) of the tallest lowercase part of a composite: the letter its accents sit on"""
        best = None
        for comp in glyf[name].components:
            b = bounds_of(comp.glyphName, glyf) if comp.glyphName in lower else None
            if b and (best is None or b[3] + comp.y > best[0]):
                best = (b[3] + comp.y, comp.glyphName)
        return best

    def top_lift(name):
        """how far the top of a lowercase letter rises (nothing over an ascender, all of it at the
        x-height): for a composite, that of its tallest lowercase part"""
        if name not in tops:
            tops[name] = 0.0
            if glyf[name].isComposite():
                part = tallest(name)
                tops[name] = top_lift(part[1]) if part else 0.0
        return tops[name]

    # composites: lowercase ones lift their accents with the top of the letter and move a dot or
    # bar on it with the letter (the parts they are built on stretch by themselves); punctuation
    # built of parts moves each part with the x-height
    for name in font.getGlyphOrder():
        g = glyf[name]
        if not g.isComposite():
            continue
        if name in lower:
            lift = top_lift(name)
            share = DOT_SHARE if name in dotted else 1.0
            part = tallest(name)
            on = moves.get(part[1], generic) if part else generic
            out = []
            for comp in g.components:
                b = bounds_of(comp.glyphName, glyf)
                if comp.glyphName in lower or not b:
                    out.append((0, 0))
                elif b[1] + comp.y >= x_height + 10:          # an accent over the letter
                    out.append(sl(lift * share))
                else:                                         # the dot of ŀ; a cedilla stays
                    out.append(sl(on.delta((b[1] + b[3]) / 2 + comp.y)))
            shift[name] = out
            moves[name] = Lifted(on, lift, part[0] if part else x_height + 10)
        elif name in punct:
            out = []
            for comp in g.components:
                b = bounds_of(comp.glyphName, glyf)
                out.append(sl(generic.body(((b[1] + b[3]) / 2) + comp.y)) if b else (0, 0))
            shift[name] = out
    return {"shift": shift, "moves": moves, "slant": slant}


def _x_min(glyf, name):
    g = glyf[name]
    if g.isComposite() or g.numberOfContours > 0:
        g.recalcBounds(glyf)
        return g.xMin
    return None


def dehint(font: TTFont) -> None:
    """unhinted, smooth at every size, as Kerberos's variable fonts are"""
    for tag in ("fpgm", "prep", "cvt ", "cvar", "hdmx", "LTSH", "VDMX", "DSIG"):
        if tag in font:
            del font[tag]
    glyf = font["glyf"]
    for name in font.getGlyphOrder():
        g = glyf[name]
        if hasattr(g, "program"):
            g.program = ttProgram.Program()
            g.program.fromBytecode(b"")
    maxp = font["maxp"]
    maxp.maxZones, maxp.maxTwilightPoints, maxp.maxStorage = 1, 0, 0
    maxp.maxFunctionDefs = maxp.maxInstructionDefs = maxp.maxStackElements = maxp.maxSizeOfInstructions = 0
    gasp = newTable("gasp")
    gasp.version, gasp.gaspRange = 1, {0xFFFF: 0x000F}
    font["gasp"] = gasp


def pair_lookups(font: TTFont) -> list:
    """indices of the kerning lookups (the same in every master: no need to merge them)"""
    out = []
    if "GPOS" in font:
        for i, lookup in enumerate(font["GPOS"].table.LookupList.Lookup):
            kind = lookup.LookupType
            if kind == 9 and lookup.SubTable:
                kind = lookup.SubTable[0].ExtensionLookupType
            if kind == 2:
                out.append(i)
    return out


def base_of(path: Path, pairs: list, out: Path) -> Path:
    """the static as every master starts from it: unhinted, its kerning lookups left empty"""
    f = TTFont(path)
    for i in pairs:
        lookup = f["GPOS"].table.LookupList.Lookup[i]
        lookup.SubTable, lookup.SubTableCount = [], 0
    dehint(f)
    f.save(out)
    return out


def master(base: Path, change: dict, share: float, target: int) -> TTFont:
    """the static (as base_of() leaves it) plus `share` of the taller shape"""
    f = TTFont(base)
    glyf, hmtx = f["glyf"], f["hmtx"]
    order = f.getGlyphOrder()
    before = {name: _x_min(glyf, name) for name in order}
    for name, ds in change["shift"].items():
        g = glyf[name]
        if g.isComposite():
            for comp, (dx, dy) in zip(g.components, ds):
                comp.x += round(share * dx)
                comp.y += round(share * dy)
        else:
            coords, _, _ = g.getCoordinates(glyf)
            for i, (dx, dy) in enumerate(ds):
                x, y = coords[i]
                coords[i] = (x + round(share * dx), y + round(share * dy))
            g.coordinates = coords
    # the origin stays put: side bearings follow the outlines (an italic shifts them sideways)
    for name in order:
        x = _x_min(glyf, name)
        if x is not None and before[name] is not None and x != before[name]:
            advance, lsb = hmtx[name]
            hmtx[name] = (advance, lsb + x - before[name])
    # mark attachment points on the lowercase follow the letter
    if "GPOS" in f:
        for lookup in f["GPOS"].table.LookupList.Lookup:
            for st in lookup.SubTable:
                st = st.ExtSubTable if lookup.LookupType == 9 else st
                kind = st.LookupType if lookup.LookupType == 9 else lookup.LookupType
                if kind == 4:
                    for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                        mv = change["moves"].get(name)
                        if mv is None:
                            continue
                        for anchor in rec.BaseAnchor:
                            if anchor is not None:
                                dy = share * mv.delta(anchor.YCoordinate)
                                anchor.XCoordinate += round(dy * change["slant"])
                                anchor.YCoordinate += round(dy)
    f["OS/2"].sxHeight = target
    f["OS/2"].yStrikeoutPosition = round(KERBEROS["strikeout"]["position_ratio"] * target)
    return f


def variable(path: Path, out_dir: Path) -> Path:
    font = TTFont(path)
    profile = KERBEROS["profiles"][path.stem.split("-", 1)[1]]
    drawn = profile["x_height"]
    if (font["OS/2"].sxHeight, font["OS/2"].sCapHeight) != (drawn, profile["cap_height"]):
        raise ValueError(f"{path.name}: rebuild statics with the Kerberos {KERBEROS['version']} build plan")
    targets = {(int(opsz), ytlc): target
               for opsz, heights in profile["targets"].items()
               for ytlc, target in zip((500, 550), heights)}
    full = max(targets.values())
    change = derive(font, full)
    change["pairs"] = pair_lookups(font)
    names = font["name"]
    italic = bool(font["OS/2"].fsSelection & 1)
    doc = DesignSpaceDocument()
    for tag, name, (lo, default, hi) in (("opsz", "Optical Size", OPSZ), ("YTLC", "Lowercase Height", YTLC)):
        ax = AxisDescriptor()
        ax.tag, ax.name, ax.minimum, ax.default, ax.maximum = tag, name, lo, default, hi
        doc.addAxis(ax)
    default = {"Optical Size": OPSZ[1], "Lowercase Height": YTLC[1]}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{path.stem}[YTLC,opsz].ttf"
    with tempfile.TemporaryDirectory(prefix="caleuche-vf-") as tmp:
        base = base_of(path, change["pairs"], Path(tmp) / "base.ttf")
        for (opsz, ytlc), target in targets.items():
            share = (target - drawn) / (full - drawn)
            p = Path(tmp) / f"m-{opsz}-{ytlc}.ttf"
            master(base, change, share, target).save(p)
            src = SourceDescriptor()
            src.path, src.location = str(p), {"Optical Size": opsz, "Lowercase Height": ytlc}
            doc.addSource(src)
        inst = InstanceDescriptor()
        inst.familyName = names.getDebugName(16) or names.getDebugName(1)
        inst.styleName = names.getDebugName(17) or names.getDebugName(2)
        inst.postScriptFontName = names.getDebugName(6)
        inst.location = dict(default)
        doc.addInstance(inst)
        vf, _, _ = build_variable(doc)
        # the kerning does not vary: it goes back in as drawn, unmerged (merging its million
        # class pairs ten times over would take minutes and gigabytes for nothing)
        for i in change["pairs"]:
            kern = font["GPOS"].table.LookupList.Lookup[i]
            lookup = vf["GPOS"].table.LookupList.Lookup[i]
            lookup.SubTable, lookup.SubTableCount = kern.SubTable, len(kern.SubTable)
        for axis in vf["fvar"].axes:
            if axis.axisTag == "YTLC":
                axis.flags |= 0x1                    # a parametric axis: hidden from menus
        weight = font["OS/2"].usWeightClass
        own = {"value": weight, "name": WEIGHTS.get(weight, str(weight))}   # the file's own weight
        if weight == 400:
            own["linkedValue"] = 700
        buildStatTable(vf, [
            {"tag": "opsz", "name": "Optical Size", "values": [{"value": v, "name": f"{v}pt"} for v in OPSZ_NAMES]},
            {"tag": "wght", "name": "Weight", "values": [own]},
            {"tag": "YTLC", "name": "Lowercase Height", "values": [{"value": 500, "name": "Normal", "flags": 0x2}]},
            {"tag": "ital", "name": "Italic", "values": [
                {"value": 1, "name": "Italic"} if italic else
                {"value": 0, "name": "Roman", "flags": 0x2, "linkedValue": 1}]},
        ])
        vf.save(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fonts", nargs="*", type=Path)
    parser.add_argument("--out", type=Path, default=Path("fonts/iosevkacaleuche/variable"))
    args = parser.parse_args()
    fonts = args.fonts or sorted(Path("fonts/iosevkacaleuche").glob("*.ttf"))
    if not fonts:
        print("no Iosevka Caleuche statics found", file=sys.stderr)
        return 1
    # each build holds ten masters in memory: a few at a time
    with ProcessPoolExecutor(max_workers=max(1, min(len(fonts), os.cpu_count() or 1, 4))) as pool:
        for out in pool.map(variable, fonts, [args.out] * len(fonts)):
            print("built", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
