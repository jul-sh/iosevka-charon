#!/usr/bin/env python3
"""
Auto-kerning integration using HalfKern (behdad/halfkern).

Wraps HalfKern's SDF-envelope overlap algorithm to compute kern values for
all relevant glyph pairs in a compiled TTF, then injects the results as a
GPOS PairPos Format 2 (class-based) kern feature.

HalfKern is vendored at scripts/halfkern/ as a git submodule.
"""

import logging
import sys
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure the vendored halfkern is importable, and that the native libraries
# (freetype, cairo) are locatable even inside a Nix shell on macOS where
# DYLD_* env vars are stripped by SIP.
# ---------------------------------------------------------------------------

_HALFKERN_DIR = str(Path(__file__).resolve().parent / "halfkern")
if _HALFKERN_DIR not in sys.path:
    sys.path.insert(0, _HALFKERN_DIR)


def _resolve_nix_lib(name: str) -> Optional[str]:
    """Find the full path to a shared library via NIX_LDFLAGS."""
    import glob
    import os
    import platform

    ext = ".dylib" if platform.system() == "Darwin" else ".so"
    nix_ldflags = os.environ.get("NIX_LDFLAGS", "")
    for token in nix_ldflags.split():
        if token.startswith("-L"):
            d = token[2:]
            for candidate in glob.glob(os.path.join(d, f"lib{name}*{ext}")):
                if os.path.isfile(candidate):
                    return candidate
    return None


def _patch_cairoft_for_nix() -> None:
    """Monkey-patch halfkern's cairoft module so it can find libs in Nix.

    cairoft.py calls ``ct.CDLL("libfreetype.dylib")`` which fails on macOS
    inside Nix because SIP strips DYLD_* variables.  We patch ``ct.CDLL`` to
    resolve bare library names via NIX_LDFLAGS before the real dlopen.
    """
    import ctypes as ct
    import os

    if not os.environ.get("NIX_LDFLAGS"):
        return  # Not in a Nix shell, nothing to patch

    _real_CDLL = ct.CDLL

    # Cache of resolved paths so we only search once per name
    _resolved: Dict[str, str] = {}

    class _NixCDLL(_real_CDLL):  # type: ignore[misc]
        def __init__(self, name, *args, **kwargs):
            # If it's a bare library name (no path separator), try to resolve
            if name and os.sep not in name:
                if name not in _resolved:
                    # Strip version suffixes to get the base lib name
                    # "libfreetype.dylib" -> "freetype"
                    base = name
                    for prefix in ("lib",):
                        if base.startswith(prefix):
                            base = base[len(prefix):]
                    for suffix in (".dylib", ".so", ".so.6", ".so.2"):
                        if base.endswith(suffix):
                            base = base[: -len(suffix)]
                    resolved = _resolve_nix_lib(base)
                    _resolved[name] = resolved if resolved else name
                name = _resolved[name]
            super().__init__(name, *args, **kwargs)

    ct.CDLL = _NixCDLL  # type: ignore[misc]


_patch_cairoft_for_nix()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class AutoKernConfig:
    """Tunables for the auto-kerning algorithm."""

    envelope: str = "sdf"  # "sdf" (default, best) or "gaussian"
    reduce: str = "max"  # "max" (tighter, optically even) or "sum" (averaged)
    half_negative: bool = False  # use full computed kerns (not halved)
    min_kern_units: int = -250  # clamp: most negative kern allowed (font units)
    max_kern_units: int = 100  # clamp: most positive kern allowed (font units)
    threshold_units: int = 5  # drop kerns smaller than this (font units)
    quantize_step: int = 2  # round kerns to multiples of this (font units)
    class_tolerance: int = 10  # max deviation for class merging (font units)
    negative_only: bool = False  # only emit tightening (negative) kerns
    half_positive: bool = True  # halve positive (loosening) kerns for conservative widening


# ---------------------------------------------------------------------------
# Unicode helpers – which glyphs are kerning candidates?
# ---------------------------------------------------------------------------

_KERN_RANGES: List[Tuple[int, int]] = [
    (0x0020, 0x007E),  # Basic Latin (space through tilde)
    (0x00A0, 0x00FF),  # Latin-1 Supplement (À-ÿ, common accented)
    (0x0100, 0x017F),  # Latin Extended-A (Ā-ſ)
    (0x0180, 0x024F),  # Latin Extended-B (ƀ-ɏ)
    (0x2010, 0x2015),  # Dashes (hyphen, en-dash, em-dash)
    (0x2018, 0x201F),  # Quotation marks
    (0x2026, 0x2026),  # Ellipsis
    (0x2039, 0x203A),  # Single angle quotes
    (0x20AC, 0x20AC),  # Euro sign
]


def _is_kern_candidate(cp: int) -> bool:
    if unicodedata.combining(chr(cp)):
        return False
    cat = unicodedata.category(chr(cp))
    if cat.startswith("C"):
        return False
    return any(lo <= cp <= hi for lo, hi in _KERN_RANGES)


def _candidate_codepoints(cmap: dict) -> List[int]:
    return sorted(cp for cp in cmap if _is_kern_candidate(cp))


# ---------------------------------------------------------------------------
# HalfKern wrapper
# ---------------------------------------------------------------------------


def _compute_all_kerns(
    font_path: str,
    candidates: List[int],
    cmap: dict,
    upem: int,
    config: AutoKernConfig,
) -> Dict[Tuple[str, str], int]:
    """Use HalfKern to compute kern values for all candidate pairs.

    Sets up HalfKern's globals, calibrates, then iterates all pairs.
    Returns {(left_glyph_name, right_glyph_name): kern_in_font_units}.
    """
    import builtins

    import cairoft as halfkern_cairoft
    import kern_pair as hk

    # --- Set up HalfKern globals ---
    hk.FONT_FACE = halfkern_cairoft.create_cairo_font_face_for_file(font_path, 0)
    hk.HB_FONT = hk.create_hb_font(font_path)

    reduce_fn = getattr(builtins, config.reduce)
    envelope = config.envelope
    px_to_units = upem / hk.FONT_SIZE

    # --- Calibrate ---
    min_s, max_s = hk.find_s(reduce=reduce_fn, envelope=envelope)
    logger.info(f"  Auto-kerning: calibrated overlap [{min_s:.0f}, {max_s:.0f}]")

    # --- Rasterize + blur all candidate glyphs ---
    # Clear the cache from any previous font
    hk.create_blurred_surface_for_text_cached.cache_clear()

    glyph_cache: Dict[int, object] = {}
    for cp in candidates:
        ch = chr(cp)
        gs = hk.create_blurred_surface_for_text_cached(ch, envelope=envelope)
        if gs is not None:
            glyph_cache[cp] = gs

    logger.info(f"  Auto-kerning: rasterized {len(glyph_cache)} glyphs")

    # --- Compute kerns for all pairs ---
    kern_cps = sorted(glyph_cache.keys())
    raw_kerns: Dict[Tuple[str, str], int] = {}
    pairs_evaluated = 0

    for left_cp in kern_cps:
        left_gs = glyph_cache[left_cp]
        for right_cp in kern_cps:
            right_gs = glyph_cache[right_cp]
            pairs_evaluated += 1

            kern_px, _overlap = hk.kern_pair(
                left_gs,
                right_gs,
                min_s,
                max_s,
                reduce=reduce_fn,
                envelope=envelope,
                blurred=True,
                half=config.half_negative,
            )

            if kern_px is None or kern_px == 0:
                continue

            # Only tightening (negative) kerns if configured
            if config.negative_only and kern_px > 0:
                continue

            # Halve positive (loosening) kerns for conservative widening
            if config.half_positive and kern_px > 0:
                kern_px = kern_px / 2.0

            # Convert pixels to font units
            kern_units = round(kern_px * px_to_units)

            # Clamp
            kern_units = max(kern_units, config.min_kern_units)
            kern_units = min(kern_units, config.max_kern_units)

            # Threshold
            if abs(kern_units) < config.threshold_units:
                continue

            left_name = cmap[left_cp]
            right_name = cmap[right_cp]
            raw_kerns[(left_name, right_name)] = kern_units

    logger.info(
        f"  Auto-kerning: evaluated {pairs_evaluated} pairs, "
        f"{len(raw_kerns)} non-zero kerns"
    )

    return raw_kerns


# ---------------------------------------------------------------------------
# Class-based clustering
# ---------------------------------------------------------------------------


def _cluster_kerns(
    pair_kerns: Dict[Tuple[str, str], int],
    quantize: int,
    class_tolerance: int,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[Tuple[int, int], int]]:
    """Cluster raw glyph-pair kerns into left/right classes + class pair values.

    Returns (left_class_defs, right_class_defs, class_pair_values).
    """
    # Quantize
    quantized = {
        pair: round(val / quantize) * quantize
        for pair, val in pair_kerns.items()
        if round(val / quantize) * quantize != 0
    }

    if not quantized:
        return {}, {}, {}

    left_glyphs = sorted({l for l, _ in quantized})
    right_glyphs = sorted({r for _, r in quantized})

    # Build kern profile for each left glyph (its kern against every right glyph)
    left_profiles: Dict[str, Dict[str, int]] = defaultdict(dict)
    right_profiles: Dict[str, Dict[str, int]] = defaultdict(dict)

    for (l, r), v in quantized.items():
        left_profiles[l][r] = v
        right_profiles[r][l] = v

    def _profile_key(profile: Dict[str, int], tol: int) -> tuple:
        items = sorted(profile.items())
        return tuple(
            (k, round(v / max(tol, 1)) * max(tol, 1)) for k, v in items
        )

    # Cluster left glyphs
    left_class_map: Dict[tuple, int] = {}
    left_class_defs: Dict[str, int] = {}
    next_id = 1
    for glyph in left_glyphs:
        key = _profile_key(left_profiles[glyph], class_tolerance)
        if key not in left_class_map:
            left_class_map[key] = next_id
            next_id += 1
        left_class_defs[glyph] = left_class_map[key]

    # Cluster right glyphs
    right_class_map: Dict[tuple, int] = {}
    right_class_defs: Dict[str, int] = {}
    next_id = 1
    for glyph in right_glyphs:
        key = _profile_key(right_profiles[glyph], class_tolerance)
        if key not in right_class_map:
            right_class_map[key] = next_id
            next_id += 1
        right_class_defs[glyph] = right_class_map[key]

    # Average kerns within each class pair
    class_pair_accum: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for (l, r), v in quantized.items():
        lc = left_class_defs[l]
        rc = right_class_defs[r]
        class_pair_accum[(lc, rc)].append(v)

    class_pair_values = {}
    for key, vals in class_pair_accum.items():
        avg = round(sum(vals) / len(vals) / quantize) * quantize
        if avg != 0:
            class_pair_values[key] = avg

    return left_class_defs, right_class_defs, class_pair_values


# ---------------------------------------------------------------------------
# GPOS injection
# ---------------------------------------------------------------------------


def _inject_kern_lookup(
    font: TTFont,
    left_class_defs: Dict[str, int],
    right_class_defs: Dict[str, int],
    class_pair_values: Dict[Tuple[int, int], int],
) -> bool:
    """Build a GPOS PairPos Format 2 lookup and append it to the font."""
    if "GPOS" not in font:
        return False

    glyph_order = font.getGlyphOrder()
    glyph_set = set(glyph_order)

    left_class_defs = {g: c for g, c in left_class_defs.items() if g in glyph_set}
    right_class_defs = {g: c for g, c in right_class_defs.items() if g in glyph_set}

    if not left_class_defs or not class_pair_values:
        return False

    gpos_table = font["GPOS"].table

    subtable = otTables.PairPos()
    subtable.Format = 2
    subtable.ValueFormat1 = 4  # XAdvance only
    subtable.ValueFormat2 = 0

    all_left = sorted(left_class_defs.keys(), key=lambda x: glyph_order.index(x))
    coverage = otTables.Coverage()
    coverage.glyphs = all_left
    subtable.Coverage = coverage

    class_def1 = otTables.ClassDef()
    class_def1.classDefs = left_class_defs
    subtable.ClassDef1 = class_def1

    class_def2 = otTables.ClassDef()
    class_def2.classDefs = right_class_defs
    subtable.ClassDef2 = class_def2

    num_class1 = max(left_class_defs.values(), default=0) + 1
    num_class2 = max(right_class_defs.values(), default=0) + 1
    subtable.ClassCount1 = num_class1
    subtable.ClassCount2 = num_class2

    class1_records = []
    for c1 in range(num_class1):
        c1_record = otTables.Class1Record()
        c2_records = []
        for c2 in range(num_class2):
            c2_record = otTables.Class2Record()
            val = class_pair_values.get((c1, c2), 0)
            c2_record.Value1 = otTables.ValueRecord()
            c2_record.Value1.XAdvance = val
            c2_record.Value2 = None
            c2_records.append(c2_record)
        c1_record.Class2Record = c2_records
        class1_records.append(c1_record)
    subtable.Class1Record = class1_records

    lookup = otTables.Lookup()
    lookup.LookupType = 2
    lookup.LookupFlag = 0
    lookup.SubTable = [subtable]
    lookup.SubTableCount = 1

    gpos_table.LookupList.Lookup.append(lookup)
    gpos_table.LookupList.LookupCount += 1
    new_idx = len(gpos_table.LookupList.Lookup) - 1

    # Add to existing kern feature or create one
    kern_feature = None
    for rec in gpos_table.FeatureList.FeatureRecord:
        if rec.FeatureTag == "kern":
            kern_feature = rec.Feature
            break

    if kern_feature is not None:
        kern_feature.LookupListIndex.append(new_idx)
        kern_feature.LookupCount = len(kern_feature.LookupListIndex)
    else:
        new_rec = otTables.FeatureRecord()
        new_rec.FeatureTag = "kern"
        new_rec.Feature = otTables.Feature()
        new_rec.Feature.LookupListIndex = [new_idx]
        new_rec.Feature.LookupCount = 1
        gpos_table.FeatureList.FeatureRecord.append(new_rec)
        gpos_table.FeatureList.FeatureCount = len(
            gpos_table.FeatureList.FeatureRecord
        )

        # Register the new kern feature in every script/language so
        # HarfBuzz (and other shapers) can discover it.
        kern_feat_idx = len(gpos_table.FeatureList.FeatureRecord) - 1
        for script_rec in gpos_table.ScriptList.ScriptRecord:
            script = script_rec.Script
            if script.DefaultLangSys is not None:
                script.DefaultLangSys.FeatureIndex.append(kern_feat_idx)
            for lang_rec in (script.LangSysRecord or []):
                lang_rec.LangSys.FeatureIndex.append(kern_feat_idx)

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add_auto_kerning(font: TTFont, config: Optional[AutoKernConfig] = None) -> bool:
    """Compute and inject auto-kerning for a quasi-proportional font.

    Drop-in replacement for the old hand-tuned ``add_kerning_feature``.
    Follows the fix_fonts.py convention: takes a TTFont, returns bool.
    """
    if config is None:
        config = AutoKernConfig()

    # Only apply to quasi-proportional (non-fixed-pitch) fonts
    if "post" in font and font["post"].isFixedPitch:
        return False

    if "GPOS" not in font:
        return False

    cmap = font.getBestCmap()
    if not cmap:
        return False

    upem = font["head"].unitsPerEm
    candidates = _candidate_codepoints(cmap)
    if len(candidates) < 3:
        return False

    logger.info(f"  Auto-kerning: {len(candidates)} candidate codepoints")

    # Save the in-memory (already post-processed) font to a temp file
    # so that HalfKern's Cairo/FreeType rasterizer sees the actual glyphs
    with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as tmp:
        tmp_path = tmp.name
        font.save(tmp_path)

    try:
        raw_kerns = _compute_all_kerns(
            tmp_path, candidates, cmap, upem, config
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not raw_kerns:
        return False

    # Cluster into classes
    left_defs, right_defs, class_pairs = _cluster_kerns(
        raw_kerns, config.quantize_step, config.class_tolerance
    )

    if not class_pairs:
        return False

    num_left = len(set(left_defs.values()))
    num_right = len(set(right_defs.values()))
    logger.info(
        f"  Auto-kerning: {num_left} left classes, "
        f"{num_right} right classes, "
        f"{len(class_pairs)} class pairs"
    )

    success = _inject_kern_lookup(font, left_defs, right_defs, class_pairs)
    if success:
        logger.info(
            f"  ✓ Auto-kerning: injected {len(class_pairs)} class kern pairs "
            f"({len(left_defs)} left glyphs, {len(right_defs)} right glyphs)"
        )
    return success
