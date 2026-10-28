"""Exercise the generated font, including interpolation between Kerberos's masters."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.varLib.varStore import VarStoreInstancer

from scripts.caleuche_variable import KERBEROS, variable


def rectangle(left, bottom, right, top):
    pen = TTGlyphPen(None)
    pen.moveTo((left, bottom))
    pen.lineTo((left, top))
    pen.lineTo((right, top))
    pen.lineTo((right, bottom))
    pen.closePath()
    return pen.glyph()


def static_font(path, profile):
    x, cap = profile['x_height'], profile['cap_height']
    glyphs = {'.notdef': rectangle(0, 0, 200, 200),
              'x': rectangle(50, 0, 350, x), 'H': rectangle(50, 0, 350, cap),
              'h': rectangle(50, 0, 150, 741), 'p': rectangle(50, -233, 150, x),
              'acutecomb': rectangle(50, 20, 100, 60)}
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    builder.setupCharacterMap({ord(c): c for c in 'xHhp'} | {0x301: 'acutecomb'})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({g: (0 if g == 'acutecomb' else 443, 50) for g in glyphs})
    builder.setupHorizontalHeader(ascent=960, descent=-245)
    builder.setupNameTable({'familyName': 'Iosevka Caleuche', 'styleName': 'Regular',
                            'psName': path.stem, 'uniqueFontIdentifier': path.stem})
    style = path.stem.split('-', 1)[1]
    weight = next((w for name, w in [('Light', 300), ('Medium', 500), ('Bold', 700)] if style.startswith(name)), 400)
    builder.setupOS2(sxHeight=x, sCapHeight=cap, usWeightClass=weight,
                     fsSelection=1 if style.endswith('Italic') else 0)
    builder.setupPost(italicAngle=-14.3 if style.endswith('Italic') else 0)
    builder.setupMaxp()
    builder.font["head"].macStyle = 2 if style.endswith("Italic") else 0
    addOpenTypeFeaturesFromString(builder.font, f'''
        markClass acutecomb <anchor 75 20> @TOP;
        feature mark {{ pos base x <anchor 200 {x + 20}> mark @TOP; }} mark;
        feature kern {{ pos H x -20; }} kern;
    ''')
    builder.save(path)


class CaleucheVariableTest(unittest.TestCase):
    def test_profiles_through_generated_fonts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for style, profile in KERBEROS['profiles'].items():
                with self.subTest(style=style):
                    source = root / f'IosevkaCaleuche-{style}.ttf'
                    static_font(source, profile)
                    vf = TTFont(variable(source, root / 'variable'))
                    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in vf['fvar'].axes}
                    self.assertEqual(axes, {'opsz': (8, 14, 72), 'YTLC': (500, 500, 550)})
                    for opsz, ytlc, expected in self.samples(profile):
                        with self.subTest(opsz=opsz, YTLC=ytlc):
                            font = instantiateVariableFont(vf, {'opsz': opsz, 'YTLC': ytlc})
                            self.assertAlmostEqual(font['OS/2'].sxHeight, expected, delta=1)
                            self.assertAlmostEqual(font['glyf']['x'].yMax, expected, delta=1)
                            self.assertEqual(font['glyf']['H'].yMax, profile['cap_height'])
                            self.assertEqual(font['glyf']['h'].yMax, 741)
                            self.assertEqual(font['glyf']['p'].yMin, -233)
                            self.assertEqual(font['hmtx']['x'][0], 443)
                            self.assertEqual(font['hhea'].ascender - font['hhea'].descender, 1205)
                            self.assertAlmostEqual(font['OS/2'].yStrikeoutPosition, expected * 0.6, delta=1)
                            lookups = font['GPOS'].table.LookupList.Lookup
                            kern = next(l for l in lookups if l.LookupType == 2)
                            self.assertEqual(kern.SubTable[0].PairSet[0].PairValueRecord[0].Value1.XAdvance, -20)
                            mark = next(l for l in lookups if l.LookupType == 4)
                            anchor = mark.SubTable[0].BaseArray.BaseRecord[0].BaseAnchor[0]
                            self.assertAlmostEqual(anchor.YCoordinate, expected + 20, delta=1)

    @staticmethod
    def samples(profile):
        for opsz, heights in profile['targets'].items():
            yield int(opsz), 500, heights[0]
            yield int(opsz), 550, heights[1]
        # Interior points exercise both optical-size and lowercase-height interpolation.
        yield 16, 500, (profile['targets']['14'][0] * 2 + profile['targets']['20'][0]) / 3
        yield 12, 525, sum(profile['targets']['12']) / 2

    @unittest.skipUnless(Path('fonts/iosevkacaleuche/variable').is_dir(), 'requires built fonts')
    def test_built_family(self):
        root = Path('fonts/iosevkacaleuche')
        self.assertEqual(len(list((root / 'variable').glob('*.ttf'))), len(KERBEROS['profiles']))
        for style, profile in KERBEROS['profiles'].items():
            with self.subTest(style=style):
                static = TTFont(root / f'IosevkaCaleuche-{style}.ttf')
                vf = TTFont(root / 'variable' / f'IosevkaCaleuche-{style}[YTLC,opsz].ttf')
                self.assertEqual({g: m[0] for g, m in static['hmtx'].metrics.items()},
                                 {g: m[0] for g, m in vf['hmtx'].metrics.items()})
                self.assertEqual((vf['hhea'].ascender, vf['hhea'].descender), (960, -245))
                self.assertAlmostEqual(vf['post'].italicAngle, -14.3 if style.endswith('Italic') else 0, places=4)
                for location in ({'opsz': 8, 'YTLC': 550}, {'opsz': 72, 'YTLC': 500}):
                    glyphs = vf.getGlyphSet(location=location)
                    self.assertEqual({g: glyphs[g].width for g in vf.getGlyphOrder()},
                                     {g: m[0] for g, m in static['hmtx'].metrics.items()})
                cmap = vf.getBestCmap()
                base_set = static.getGlyphSet()
                def bounds(glyph_set, name):
                    pen = BoundsPen(glyph_set)
                    glyph_set[name].draw(pen)
                    return pen.bounds
                fixed = {c: bounds(base_set, cmap[ord(c)]) for c in 'Hhp'}
                for opsz, ytlc, expected in self.samples(profile):
                    location = {'opsz': opsz, 'YTLC': ytlc}
                    glyph_set = vf.getGlyphSet(location=location)
                    x = bounds(glyph_set, cmap[ord('x')])
                    self.assertAlmostEqual(x[3], expected, delta=1)
                    for c, index in [('H', 3), ('h', 3), ('p', 1)]:
                        self.assertAlmostEqual(bounds(glyph_set, cmap[ord(c)])[index], fixed[c][index], delta=1)
                    values = VarStoreInstancer(vf['MVAR'].table.VarStore, vf['fvar'].axes, vf.normalizeLocation(location))
                    deltas = {r.ValueTag: values[r.VarIdx] for r in vf['MVAR'].table.ValueRecord}
                    self.assertAlmostEqual(vf['OS/2'].sxHeight + deltas['xhgt'], expected, delta=1)

    def test_build_plan_matches_pinned_metrics(self):
        # Use Iosevka's actual expression evaluator: no second parser/interpolator in tests.
        subprocess.run(['node', '--input-type=module', '-e', """
            import fs from 'node:fs';
            import assert from 'node:assert/strict';
            import TOML from './sources/iosevka/node_modules/@iarna/toml/toml.js';
            import {applyMetricOverride} from './sources/iosevka/packages/param/src/metric-override.mjs';
            const plan = TOML.parse(fs.readFileSync('sources/private-build-plans.toml', 'utf8')).buildPlans.IosevkaCaleuche;
            const reference = JSON.parse(fs.readFileSync('sources/caleuche-kerberos.json', 'utf8'));
            for (const [weight, name] of [[300, 'Light'], [400, 'Regular'], [500, 'Medium'], [700, 'Bold']]) {
                for (const [slope, suffix] of [['Upright', ''], ['Italic', 'Italic']]) {
                    const style = name === 'Regular' && suffix ? 'Italic' : name + suffix;
                    const shape = {weight: plan.weights[name].shape, width: 443, slopeAngle: plan.slopes[slope].angle};
                    const metrics = {};
                    applyMetricOverride(metrics, plan.metricOverride, {shape});
                    assert.equal(metrics.xHeight, reference.profiles[style].x_height);
                    assert.equal(metrics.cap, reference.profiles[style].cap_height);
                    assert.equal(metrics.ascender, reference.ascender);
                    assert.equal(metrics.descender, reference.descender);
                    assert.equal(shape.slopeAngle, suffix ? reference.italic_angle : 0);
                }
            }
        """], check=True, cwd=Path(__file__).resolve().parents[1])

    def test_rejects_stale_statics(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'IosevkaCaleuche-Regular.ttf'
            static_font(source, {'x_height': 461, 'cap_height': 703})
            with self.assertRaisesRegex(ValueError, 'rebuild statics'):
                variable(source, Path(tmp) / 'variable')


if __name__ == '__main__':
    unittest.main()
