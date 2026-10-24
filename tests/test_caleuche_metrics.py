"""Family post-processing must match the pinned reference without changing Charon."""
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fix_fonts import FAMILIES, fix_italic_angle, fix_line_decorations, fix_vertical_metrics
from test_caleuche_variable import static_font
from scripts.caleuche_variable import KERBEROS


class CaleucheMetricsTest(unittest.TestCase):
    def test_postprocess_all_styles(self):
        with tempfile.TemporaryDirectory() as tmp:
            for style, profile in KERBEROS['profiles'].items():
                with self.subTest(style=style):
                    path = Path(tmp) / f'IosevkaCaleuche-{style}.ttf'
                    static_font(path, profile)
                    f = TTFont(path)
                    spec = FAMILIES['IosevkaCaleuche']
                    fix_vertical_metrics(f, spec)
                    fix_line_decorations(f, spec)
                    # Reproduce the whole-degree rounding in upstream's post table.
                    f['post'].italicAngle = -14 if style.endswith('Italic') else 0
                    fix_italic_angle(f, spec)
                    self.assertEqual((f['hhea'].ascender, f['hhea'].descender, f['hhea'].lineGap), (960, -245, 0))
                    self.assertEqual((f['OS/2'].sTypoAscender, f['OS/2'].sTypoDescender), (960, -245))
                    self.assertEqual((f['post'].underlinePosition, f['post'].underlineThickness), (-120, 75))
                    self.assertEqual(f['OS/2'].yStrikeoutPosition, round(profile['x_height'] * 0.6))
                    self.assertEqual(f['post'].italicAngle, -14.3 if style.endswith('Italic') else 0)

    def test_charon_keeps_its_metrics_and_angle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'IosevkaCaleuche-Italic.ttf'
            static_font(path, KERBEROS['profiles']['Italic'])
            for family in ('IosevkaCharon', 'IosevkaCharonMono'):
                f = TTFont(path)
                spec = FAMILIES[family]
                before = f['post'].italicAngle
                fix_vertical_metrics(f, spec)
                fix_italic_angle(f, spec)
                self.assertEqual((f['hhea'].ascender, f['hhea'].descender), (1015, -265))
                self.assertEqual(f['post'].italicAngle, before)


if __name__ == '__main__':
    unittest.main()
