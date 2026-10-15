import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.package_release import SUBSETS, package


class PackageReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.fonts = root / "fonts"
        self.webfonts = root / "webfonts"
        self.output = root / "output"
        self.license = root / "OFL.txt"
        self.article = root / "ARTICLE.en_us.html"
        self.license.write_text("license")
        self.article.write_text("article")

        for family, name in (
            ("iosevkacharon", "IosevkaCharon-Regular"),
            ("iosevkacharonmono", "IosevkaCharonMono-Regular"),
        ):
            self.touch(self.fonts / family / f"{name}.ttf")
            for subset in SUBSETS:
                self.touch(self.webfonts / subset / family / f"{name}.woff2")

        self.static = "IosevkaCaleuche-Medium"
        self.variable = f"{self.static}[YTLC,opsz]"
        family = "iosevkacaleuche"
        self.touch(self.fonts / family / f"{self.static}.ttf")
        self.touch(self.fonts / family / "variable" / f"{self.variable}.ttf")
        for subset in SUBSETS:
            self.touch(self.webfonts / subset / family / f"{self.static}.woff2")
            self.touch(self.webfonts / subset / family / "variable" / f"{self.variable}.woff2")

    @staticmethod
    def touch(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"font")

    def test_archives_separate_families_and_include_caleuche_variable_webfonts(self):
        package(self.fonts, self.webfonts, self.output, self.license, self.article)
        with ZipFile(self.output / "iosevka-charon.zip") as archive:
            names = set(archive.namelist())
            self.assertIn("iosevkacharon/IosevkaCharon-Regular.ttf", names)
            self.assertIn("iosevkacharonmono/IosevkaCharonMono-Regular.ttf", names)
            self.assertIn("ARTICLE.en_us.html", names)
            self.assertFalse(any("caleuche" in name for name in names))
        with ZipFile(self.output / "iosevka-charon-webfonts.zip") as archive:
            names = set(archive.namelist())
            self.assertIn("latin/iosevkacharon/IosevkaCharon-Regular.woff2", names)
            self.assertFalse(any("caleuche" in name for name in names))
        with ZipFile(self.output / "iosevka-caleuche.zip") as archive:
            names = set(archive.namelist())
            self.assertIn(f"fonts/iosevkacaleuche/{self.static}.ttf", names)
            self.assertIn(f"fonts/iosevkacaleuche/variable/{self.variable}.ttf", names)
            for subset in SUBSETS:
                self.assertIn(f"webfonts/{subset}/iosevkacaleuche/{self.static}.woff2", names)
                self.assertIn(f"webfonts/{subset}/iosevkacaleuche/variable/{self.variable}.woff2", names)
            self.assertIn("OFL.txt", names)
            self.assertFalse(any("charon" in name for name in names))

    def test_missing_variable_fails_before_creating_archives(self):
        (self.fonts / "iosevkacaleuche" / "variable" / f"{self.variable}.ttf").unlink()
        with self.assertRaisesRegex(ValueError, "matching opsz/YTLC"):
            package(self.fonts, self.webfonts, self.output, self.license, self.article)
        self.assertFalse((self.output / "iosevka-caleuche.zip").exists())


if __name__ == "__main__":
    unittest.main()
