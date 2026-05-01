"""
============================================================
  FORGE MASTER — HSV colour heuristics for scan/

  Two questions every panel/popup scan needs answered before
  loading the right reference set:

      "What AGE does this tile belong to?"      → identify_age_from_color
      "What RARITY does this tile show?"         → identify_rarity_from_color

  Both work the same way:

    1. Average the RGB of the patch (alpha < 64 ignored so
       transparent corners do not drag the mean toward black).
    2. Convert to HSV.
    3. Pick the entry of the calibration table closest in
       circular-hue distance.

  These functions are FALLBACKS in the unified scan pipeline.
  When a popup carries a textual ``[<Quantum>]`` / ``[<Rare>]``
  tag the OCR layer is the deterministic source — colour is
  only consulted on panels (4×2 opponent / player_equipment)
  or when the OCR balise is illegible.

  ⚠ Vocabulary trap: ``hsv_distance`` here returns a DISTANCE
  (0 = perfect, ↑ = worse). The hybrid matcher score in
  ``scan.core`` returns a SCORE in [0, 1] where 1 = best.
  These two metrics have INVERSE scales — never compare them
  with the same threshold. Cf. PLAN_REFACTO_SCAN.txt.

  Constants (re-exported for jobs that need them):

      RARITY_COLORS_HSV  — calibration table for borders
      AGE_COLORS_HSV     — calibration table for backgrounds
      RARITY_NAMES       — ordered tuple of canonical rarities
      AGE_INT_TO_NAME    — pretty-print table (kept for parity
                            with the old calibration tooling)

  Tunable thresholds used by the strategy switcher in jobs:

      HSV_AMBIGUITY_THRESHOLD — distance above which colour
                                 alone is unreliable; the job
                                 falls back to STRAT B
                                 (all-ages traversal).
============================================================
"""

from __future__ import annotations

import colorsys
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Calibration tables
# ────────────────────────────────────────────────────────────
#
# The canonical source of truth for these HSV calibrations is
# ``data/colors.json``. The dicts below are EMBEDDED
# FALLBACKS used only if the JSON file is missing, malformed,
# or unreadable — the project still boots in that degraded
# state, with a warning. Edit the JSON FIRST; keep the
# fallback in sync so a fresh checkout works without the JSON.
#
# Numbers are in HSV space, all in [0, 1]. Hue is circular:
# circular distance is min(|h1-h2|, 1 - |h1-h2|).

# Border colour → rarity. (h, s, v) tuples in [0, 1].
RARITY_COLORS_HSV: Dict[str, Tuple[float, float, float]] = {
    "Common":    (0.00, 0.00, 0.88),
    "Rare":      (0.56, 0.89, 1.00),
    "Epic":      (0.36, 0.89, 1.00),
    "Legendary": (0.17, 0.89, 1.00),
    "Ultimate":  (0.00, 0.89, 1.00),
    "Mythic":    (0.77, 0.89, 1.00),
}

# Background colour → Age index. Comments use the canonical
# in-game age names (see AGE_INT_TO_NAME below). The HSV
# triples currently coincide with rarity colours at matching
# positions because the in-game age progression uses the same
# colour ramp as the rarity tier — this is intentional and
# documented in data/colors.json (_comment_convergence).
AGE_COLORS_HSV: Dict[int, Tuple[float, float, float]] = {
    0: (0.00, 0.00, 0.88),   # Primitive    — gris
    1: (0.56, 0.89, 1.00),   # Medieval     — bleu
    2: (0.36, 0.89, 1.00),   # Early-Modern — vert
    3: (0.17, 0.89, 1.00),   # Modern       — jaune
    4: (0.00, 0.89, 1.00),   # Space        — rouge
    5: (0.77, 0.89, 1.00),   # Interstellar — violet
    6: (0.47, 0.82, 1.00),   # Multiverse   — turquoise
    7: (0.68, 0.89, 1.00),   # Quantum      — bleu profond
    8: (1.00, 0.57, 0.35),   # Underworld   — brun rouge
    9: (0.06, 1.00, 1.00),   # Divine       — orange
}


# Canonical rarity ordering — matches the in-game Rarity enum
# and is what AutoPet/Mount/Skill mapping JSON files store as
# the "Rarity" field. Useful for UI sort and for the [<X>]
# popup-tag parser.
RARITY_NAMES: Tuple[str, ...] = (
    "Common",
    "Rare",
    "Epic",
    "Legendary",
    "Ultimate",
    "Mythic",
)


# Pretty-printer — the wiki-grid scanner used a slightly
# different "EarlyModern" → "Earlymodern" spelling. Kept for
# parity with strings persisted in older debug dumps.
AGE_INT_TO_NAME: Dict[int, str] = {
    0: "Primitive",
    1: "Medieval",
    2: "Earlymodern",
    3: "Modern",
    4: "Space",
    5: "Interstellar",
    6: "Multiverse",
    7: "Quantum",
    8: "Underworld",
    9: "Divine",
}


# Reverse lookup used by jobs that read ``[<Quantum>]`` from
# popup titles. Both spellings ("Earlymodern" and "Early-Modern"
# accepted; folder uses the dash, OCR usually loses it).
AGE_NAME_TO_INT: Dict[str, int] = {
    "Primitive":      0,
    "Medieval":       1,
    "Earlymodern":    2,
    "Early-Modern":   2,
    "EarlyModern":    2,
    "Modern":         3,
    "Space":          4,
    "Interstellar":   5,
    "Multiverse":     6,
    "Quantum":        7,
    "Underworld":     8,
    "Divine":         9,
}


# ────────────────────────────────────────────────────────────
#  Strategy thresholds
# ────────────────────────────────────────────────────────────
#
# Cf. PLAN_REFACTO_SCAN.txt — STRAT A (per-tile colour-driven
# load) vs STRAT B (all-ages traversal). The job switches
# between them autonomously based on these values. Like the
# colour tables above, these defaults are overridden by
# data/colors.json at import time when the file is
# present.

# Squared HSV distance above which the colour heuristic is
# considered too uncertain to trust. Default tuned on the
# reference captures shipped with the chantier; a typical
# "good" match comes back at < 0.04, so 0.08 leaves comfortable
# headroom.
HSV_AMBIGUITY_THRESHOLD: float = 0.08

# Smallest acceptable gap between top-1 and top-2 colour
# candidates. Below this, the two colours look interchangeable
# and the job should fall back to STRAT B.
HSV_AMBIGUITY_GAP: float = 0.02


# ────────────────────────────────────────────────────────────
#  JSON calibration loader
# ────────────────────────────────────────────────────────────
#
# We ship the calibration values both as Python literals
# (above) AND as ``data/colors.json``. The JSON wins when
# present; the Python literals are the safety net so an
# accidental removal of ``data/colors.json`` does not crash the
# matcher — it just degrades to the snapshot baked into the
# code.

_COLORS_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "colors.json"


def _coerce_triple(value: Any) -> Optional[Tuple[float, float, float]]:
    """Validate and convert a 3-element list to an HSV tuple.

    Returns None on any structural mismatch; the caller treats
    None as "skip this entry, log a warning, keep the
    in-Python fallback".
    """
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        out = (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
    if not all(0.0 <= c <= 1.0 for c in out):
        return None
    return out


def _load_colors_json(path: Path) -> Optional[Dict[str, Any]]:
    """Read and parse the JSON. Returns None on any I/O or
    parse error — the caller falls back to the embedded
    defaults and logs a warning."""
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        log.exception("scan.colors: cannot parse %s", path)
        return None


def _apply_calibration(payload: Dict[str, Any]) -> None:
    """Mutate the module-level dicts and threshold constants
    in place from a parsed JSON payload. Silently ignores
    unknown keys so future fields (e.g. opponent panel
    sub-bbox tweaks) can ship without breaking older code."""
    global HSV_AMBIGUITY_THRESHOLD, HSV_AMBIGUITY_GAP

    rarity = payload.get("rarity_colors_hsv") or {}
    if isinstance(rarity, dict):
        for name, triple in rarity.items():
            if not isinstance(name, str):
                continue
            t = _coerce_triple(triple)
            if t is None:
                log.warning("scan.colors: bad rarity HSV %r=%r", name, triple)
                continue
            RARITY_COLORS_HSV[name] = t

    ages = payload.get("age_colors_hsv") or {}
    if isinstance(ages, dict):
        for key, triple in ages.items():
            try:
                age_int = int(key)
            except (TypeError, ValueError):
                log.warning("scan.colors: bad age key %r in age_colors_hsv", key)
                continue
            t = _coerce_triple(triple)
            if t is None:
                log.warning("scan.colors: bad age HSV %r=%r", key, triple)
                continue
            AGE_COLORS_HSV[age_int] = t

    th = payload.get("thresholds") or {}
    if isinstance(th, dict):
        ambig = th.get("hsv_ambiguity_threshold")
        if isinstance(ambig, (int, float)):
            HSV_AMBIGUITY_THRESHOLD = float(ambig)
        gap = th.get("hsv_ambiguity_gap")
        if isinstance(gap, (int, float)):
            HSV_AMBIGUITY_GAP = float(gap)


# Apply the JSON overrides at import time. Failure is non
# fatal: the embedded fallback values above keep the matcher
# functional with a single warning in the log.
_calibration_payload = _load_colors_json(_COLORS_JSON_PATH)
if _calibration_payload is not None:
    _apply_calibration(_calibration_payload)
else:
    log.info(
        "scan.colors: %s missing — using embedded fallback HSV calibration",
        _COLORS_JSON_PATH,
    )


def reload_calibration(path: Optional[Path] = None) -> bool:
    """Re-read the calibration JSON and re-apply it.

    Useful from tests or from a future "Recalibrate colours"
    UI button. Returns True when an override was applied,
    False when the file was missing or unreadable (in which
    case the previously-loaded values keep their last state).
    """
    target = path or _COLORS_JSON_PATH
    payload = _load_colors_json(target)
    if payload is None:
        return False
    _apply_calibration(payload)
    return True


# ────────────────────────────────────────────────────────────
#  Distance / dominant colour
# ────────────────────────────────────────────────────────────


def hsv_distance(h1: float, s1: float, v1: float,
                 h2: float, s2: float, v2: float) -> float:
    """Squared HSV distance with circular hue.

    The factor of two on the hue component up-weights it
    relative to saturation/value — empirically this gives the
    best discrimination on opponent-panel borders where two
    rarities can have very close S/V but obvious hue offsets.

    Returns a squared-distance in roughly [0, ~6]. 0 means a
    perfect colour match; the threshold constants in this
    module are calibrated against this scale.
    """
    dh = min(abs(h1 - h2), 1.0 - abs(h1 - h2))
    return (dh * 2.0) ** 2 + (s1 - s2) ** 2 + (v1 - v2) ** 2


def dominant_color_hsv(img: Image.Image) -> Tuple[float, float, float]:
    """Coarse mean-RGB downscale → HSV.

    Pixels with alpha < 64 are ignored so transparent corners
    do not drag the mean toward black. Returns ``(h, s, v)`` in
    [0, 1]. When the patch is fully transparent the function
    returns ``(0, 0, 0)`` — callers should treat that as a
    sentinel and not match against it.
    """
    small = img.convert("RGBA").resize((8, 8))
    arr = np.asarray(small, dtype=np.float32)
    rgb = arr[..., :3] / 255.0
    a = arr[..., 3]
    mask = a >= 64
    if not mask.any():
        return (0.0, 0.0, 0.0)
    avg = rgb[mask].mean(axis=0)
    return colorsys.rgb_to_hsv(float(avg[0]), float(avg[1]), float(avg[2]))


# ────────────────────────────────────────────────────────────
#  Public identifiers
# ────────────────────────────────────────────────────────────


def identify_rarity_from_color(border_crop: Optional[Image.Image]) -> str:
    """Best-rarity guess from a border crop.

    Returns ``"Common"`` on a None / empty input — matches the
    legacy behaviour and keeps downstream calculators happy
    (Common rarity = neutral multipliers).
    """
    if border_crop is None:
        return "Common"
    h, s, v = dominant_color_hsv(border_crop)
    return min(
        RARITY_COLORS_HSV,
        key=lambda r: hsv_distance(h, s, v, *RARITY_COLORS_HSV[r]),
    )


def identify_rarity_from_color_with_distance(
    border_crop: Optional[Image.Image],
) -> Tuple[str, float, float]:
    """Same as ``identify_rarity_from_color`` but also returns
    the top-1 distance and the gap to top-2.

    Useful for the STRAT A → STRAT B switcher: a job can call
    this once, cache the distances and gap, and decide whether
    to trust the colour result without re-running the loop.

    Returns ``(rarity_name, top1_distance, top1_top2_gap)``.
    When the image is None the function returns
    ``("Common", float("inf"), 0.0)``.
    """
    if border_crop is None:
        return ("Common", float("inf"), 0.0)
    h, s, v = dominant_color_hsv(border_crop)
    distances = sorted(
        ((rarity, hsv_distance(h, s, v, *RARITY_COLORS_HSV[rarity]))
         for rarity in RARITY_COLORS_HSV),
        key=lambda t: t[1],
    )
    top1_name, top1_d = distances[0]
    top2_d = distances[1][1] if len(distances) > 1 else float("inf")
    return (top1_name, float(top1_d), float(top2_d - top1_d))


def identify_age_from_color(bg_crop: Optional[Image.Image]) -> int:
    """Best-age guess from a background crop. Returns 0
    (Primitive) on a None / empty input."""
    if bg_crop is None:
        return 0
    h, s, v = dominant_color_hsv(bg_crop)
    return min(
        AGE_COLORS_HSV,
        key=lambda a: hsv_distance(h, s, v, *AGE_COLORS_HSV[a]),
    )


def identify_age_from_color_with_distance(
    bg_crop: Optional[Image.Image],
) -> Tuple[int, float, float]:
    """Distance-aware variant of ``identify_age_from_color``.

    Returns ``(age_int, top1_distance, top1_top2_gap)``. See
    ``identify_rarity_from_color_with_distance`` for usage.
    """
    if bg_crop is None:
        return (0, float("inf"), 0.0)
    h, s, v = dominant_color_hsv(bg_crop)
    distances = sorted(
        ((age, hsv_distance(h, s, v, *AGE_COLORS_HSV[age]))
         for age in AGE_COLORS_HSV),
        key=lambda t: t[1],
    )
    top1_age, top1_d = distances[0]
    top2_d = distances[1][1] if len(distances) > 1 else float("inf")
    return (int(top1_age), float(top1_d), float(top2_d - top1_d))


def is_color_ambiguous(top1_distance: float, top1_top2_gap: float) -> bool:
    """STRAT A → STRAT B trigger.

    Returns True when the colour heuristic should NOT be
    trusted — either the top-1 distance is too large
    (``> HSV_AMBIGUITY_THRESHOLD``) or the gap to the runner-up
    is too small (``< HSV_AMBIGUITY_GAP``).

    Calling code uses this to decide whether to load
    ``mode="exact"`` references or fall back to
    ``mode="all_ages"``.
    """
    return (top1_distance > HSV_AMBIGUITY_THRESHOLD
            or top1_top2_gap < HSV_AMBIGUITY_GAP)


__all__ = [
    "RARITY_COLORS_HSV",
    "AGE_COLORS_HSV",
    "RARITY_NAMES",
    "AGE_INT_TO_NAME",
    "AGE_NAME_TO_INT",
    "HSV_AMBIGUITY_THRESHOLD",
    "HSV_AMBIGUITY_GAP",
    "hsv_distance",
    "dominant_color_hsv",
    "identify_rarity_from_color",
    "identify_rarity_from_color_with_distance",
    "identify_age_from_color",
    "identify_age_from_color_with_distance",
    "is_color_ambiguous",
    "reload_calibration",
]
