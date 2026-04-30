"""
============================================================
  FORGE MASTER — 4×2 equipment-panel identification helper

  Shared between scan/jobs/player_equipment.py (Phase 5) and
  scan/jobs/opponent.py (Phase 6). The panel layout is the
  same for both: 8 tiles in a 4×2 grid, no titles, slot
  deduced from POSITION (index 0..7 → Helmet, Body, Gloves,
  Necklace, Ring, Weapon, Shoe, Belt).

  Pipeline (per tile):

      1. Crop the icon, border strip, and background patch
         using the per-tile pixel offsets supplied by the
         caller (scan/offsets/player.py).
      2. identify_age_from_color(bg_crop)        — STRAT A
         identify_rarity_from_color(border_crop)
      3. Load refs (age, slot) in mode="exact".
      4. match(crop, refs, ocr_name="") → top Candidate.
         Fall back to mode="all_ages" for THAT slot when
         the colour gap is ambiguous (cf. SCAN_REFACTOR.txt
         §3 STRAT A → STRAT B).
      5. extract_level (OCR strip below the icon) — copied
         from backend/scanner/panel.extract_level so the
         legacy regex behaviour is preserved.

  Returns: list of slot_dicts in slot_order, each dict ready
  to be merged into ``persistence.empty_equipment()``. The
  caller (player_equipment.py) is responsible for the
  ItemBalancingLibrary lookup that fills in hp_flat /
  damage_flat / __name__, plus the WeaponLibrary lookup for
  the slot index 5 (handled by scan.jobs._weapon_enrich).

  Public API:

      identify_panel(capture, layout, *, libs=None,
                     skip_per_slot_ocr=False) -> List[dict]
      extract_level(capture, icon_bbox)       -> int
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from ..colors import (
    HSV_AMBIGUITY_GAP,
    HSV_AMBIGUITY_THRESHOLD,
    identify_age_from_color_with_distance,
    identify_rarity_from_color,
)
from ..core import DEFAULT_THRESHOLD, autocrop_capture, match as core_match
from ..refs import load_references

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Per-slot Lv.NN OCR — direct port of
#  backend/scanner/panel.extract_level. The regex tolerates
#  RapidOCR's typical artefacts ("L v . 12" / "Lv  3").
# ────────────────────────────────────────────────────────────


_LV_RE = re.compile(r"L\s*v\.?\s*(\d{1,3})", re.IGNORECASE)


def _ocr_strip(capture: Image.Image,
               x0: int, y0: int, x1: int, y1: int) -> str:
    """OCR a single rectangle. Returns ``""`` if the OCR
    backend is unavailable or raises."""
    try:
        from backend.scanner import ocr as _ocr
    except Exception:  # pragma: no cover - defensive
        return ""
    if not _ocr.is_available():
        return ""
    try:
        return _ocr.ocr_image(capture.crop((x0, y0, x1, y1)))
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.jobs._panel: level-strip OCR failed")
        return ""


def extract_level(capture: Image.Image,
                  icon_bbox: Tuple[int, int, int, int]) -> int:
    """OCR a thin strip just below the icon to read ``Lv.NN``.

    Direct port of the legacy panel.extract_level — same
    geometry (height = 50 % of the icon, starting 20 % above
    the icon's bottom edge) so calibrated layouts keep
    working.
    """
    x0, y0, x1, y1 = icon_bbox
    h = max(1, y1 - y0)
    strip_y0 = min(capture.height, y1 - int(h * 0.20))
    strip_y1 = min(capture.height, y1 + int(h * 0.50))
    if strip_y1 <= strip_y0:
        return 0
    text = _ocr_strip(capture, x0, strip_y0, x1, strip_y1)
    m = _LV_RE.search(text or "")
    return int(m.group(1)) if m else 0


# ────────────────────────────────────────────────────────────
#  Per-tile identification
# ────────────────────────────────────────────────────────────


def _identify_one_tile(
    capture: Image.Image,
    *,
    slot: str,
    icon_bbox: Tuple[int, int, int, int],
    border_bbox: Tuple[int, int, int, int],
    bg_bbox: Tuple[int, int, int, int],
    threshold: float,
    skip_per_slot_ocr: bool,
) -> Dict[str, Any]:
    """Run STRAT A → STRAT B (slot-only) on a single tile.

    Returns a slot_dict with the canonical keys (``__age__``,
    ``__idx__``, ``__level__``, ``__rarity__``, ``__name__``)
    pre-filled. ``hp_flat`` / ``damage_flat`` / weapon-only
    fields are NOT filled here — the caller does that with
    its ItemBalancingLibrary / WeaponLibrary lookups.
    """
    icon_crop   = capture.crop(icon_bbox)
    border_crop = capture.crop(border_bbox)
    bg_crop     = capture.crop(bg_bbox)

    age_int, age_dist, age_gap = identify_age_from_color_with_distance(bg_crop)
    rarity = identify_rarity_from_color(border_crop)

    sprite = autocrop_capture(icon_crop)

    # STRAT A: load refs for the colour-detected age first.
    candidates = []
    use_strat_b = (age_dist > HSV_AMBIGUITY_THRESHOLD
                   or age_gap < HSV_AMBIGUITY_GAP)
    if not use_strat_b:
        try:
            refs_a = load_references("equipment", age=int(age_int),
                                     slot=slot, mode="exact")
        except Exception:  # pragma: no cover - defensive
            log.exception("scan.jobs._panel: load_references(exact) failed")
            refs_a = []
        if refs_a:
            candidates = core_match(sprite, refs_a, autocrop=False)
            if candidates and candidates[0].score < threshold:
                # Top-1 score below the per-job threshold — give
                # STRAT B a chance to find a better answer outside
                # the colour-detected age.
                use_strat_b = True

    if use_strat_b or not candidates:
        try:
            refs_b = load_references("equipment", slot=slot,
                                     mode="all_ages")
        except Exception:  # pragma: no cover - defensive
            log.exception("scan.jobs._panel: load_references(all_ages) failed")
            refs_b = []
        if refs_b:
            cand_b = core_match(sprite, refs_b, autocrop=False)
            if cand_b:
                # Keep STRAT B only if it beats STRAT A (or A had
                # nothing to offer).
                if not candidates or cand_b[0].score > candidates[0].score:
                    candidates = cand_b

    best = candidates[0] if candidates else None
    if best is None:
        return {
            "__age__":   int(age_int),
            "__idx__":   0,
            "__level__": 0,
            "__rarity__": rarity or "Common",
            "__name__":  "",
        }

    level = (1 if skip_per_slot_ocr
             else max(1, extract_level(capture, icon_bbox)))

    out: Dict[str, Any] = {
        "__age__":   int(best.age) if best.age is not None else int(age_int),
        "__idx__":   int(best.idx) if best.idx is not None else 0,
        "__level__": int(level),
        "__rarity__": rarity or "Common",
        "__name__":  best.payload.get("name") or best.name,
    }
    return out


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────


def identify_panel(
    capture: Image.Image,
    layout: Dict[str, Any],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    skip_per_slot_ocr: bool = False,
) -> List[Dict[str, Any]]:
    """Identify the 8 pieces visible in a 4×2 panel capture.

    Parameters
    ----------
    capture : PIL.Image.Image
        Full panel screenshot (the bbox of the equipment grid).
    layout : dict
        Output of ``scan.offsets.player.offsets_for_capture(W, H)``
        — three lists of 8 pixel rectangles (``equipment``,
        ``border``, ``bg``) plus ``slot_order``.
    threshold : float
        Per-tile minimum hybrid score before STRAT B kicks in
        (cf. SCAN_REFACTOR.txt §3 fallback critère c).
    skip_per_slot_ocr : bool
        Bypass the Lv.NN OCR (returns ``__level__=1`` for every
        slot). Useful for tests on synthetic captures.

    Returns
    -------
    list[dict]
        One slot_dict per tile, in ``layout["slot_order"]``
        order. Slots whose identification failed return a
        placeholder with ``__idx__=0`` so the list length is
        stable.
    """
    slot_order   = list(layout["slot_order"])
    eq_offsets   = layout["equipment"]
    border_offsets = layout["border"]
    bg_offsets   = layout["bg"]

    out: List[Dict[str, Any]] = []
    for i, slot in enumerate(slot_order):
        if i >= len(eq_offsets):
            break
        out.append(_identify_one_tile(
            capture,
            slot=slot,
            icon_bbox=eq_offsets[i],
            border_bbox=border_offsets[i],
            bg_bbox=bg_offsets[i],
            threshold=threshold,
            skip_per_slot_ocr=skip_per_slot_ocr,
        ))
    return out


__all__ = [
    "identify_panel",
    "extract_level",
]
