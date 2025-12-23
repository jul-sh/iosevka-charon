"""
Repository-local Python site customization.

We patch FontTools script metadata so FontBakery's glyphset language checks
do not crash on newer gflanguages entries that reference the non-standard
\"Berf\" script (Beria Erfe). The value is intentionally mapped to itself so
glyphsets that rely on standard scripts will simply skip it.
"""

try:
    from fontTools.unicodedata import Scripts

    # Ensure unknown script code from gflanguages does not raise KeyError in glyphsets
    Scripts.NAMES.setdefault("Berf", "Berf")
except ImportError:
    # fontTools not available yet (e.g., during nix shell initialization)
    pass
