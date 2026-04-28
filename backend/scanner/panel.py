"""
============================================================
  FORGE MASTER -- Shared equipment-panel identification

  ``identify_equipment_panel`` runs the per-slot template
  matching + level OCR on a screenshot of an 8-slot equipment
  panel. Returns a list of ``IdentifiedItem``.

  Both pipelines call it:
    * backend.pipeline._build_profile()    (opponent)
    * backend.scanner.player_equipment            (player, P2)

  The helper does NOT load libraries or compute final stats --
  callers do that on their side. This keeps it pure and easy
  to test against synthetic captures.
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from .icon_matcher import identify_all
from .ocr_types import IdentifiedItem

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Per-slot level OCR (extracted from the enemy pipeline)
# ────────────────────────────────────────────────────────────
#
# Levels are rendered as ``Lv.NNN`` (or ``Lv NNN``) underneath
# each icon. We OCR a thin strip just below the icon to pick
# them up without bleeding into the global Forge level header.

_LV_RE = re.compile(r"L\s*v\.?\s*(\d{1,3})", re.IGNORECASE)


def _ocr_strip(capture: Image.Image,
               x0: int, y0: int, x1: int, y1: int) -> str:
    """Run OCR on a single rectangle of a capture. Empty string on
    error. Imported lazily so headless testing works without the
    OCR backend installed.
    """
    try:
        from . import ocr  # type: ignore
        if not ocr.is_available():
            return ""
        crop = capture.crop((x0, y0, x1, y1))
        return ocr.ocr_image(crop)
    except Exception:
        log.exception("level-strip OCR failed")
        return ""


def extract_level(capture: Image.Image,
                  icon_bbox: Tuple[int, int, int, int]) -> int:
    """OCR a strip BELOW the icon -- that's where ``Lv.NNN`` lives.

    The strip is sized as the same width as the icon, height equal
    to half the icon's height, starting flush with the icon's
    bottom (with a small overlap). Returns 0 on miss; callers
    typically clamp to a min of 1.
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
#  Public API
# ────────────────────────────────────────────────────────────


def identify_equipment_panel(
    capture: Image.Image,
    *,
    equipment_offsets: List[Tuple[int, int, int, int]],
    border_offsets:    List[Tuple[int, int, int, int]],
    bg_offsets:        List[Tuple[int, int, int, int]],
    slot_order:        List[str],
    skip_per_slot_ocr: bool = False,
) -> List[IdentifiedItem]:
    """Identify the 8 pieces visible in an equipment panel.

    Parameters
    ----------
    capture
        PIL.Image of the panel.
    equipment_offsets / border_offsets / bg_offsets
        Pixel rectangles per slot, all aligned with ``slot_order``.
        ``equipment_offsets[i]`` is the icon itself; ``border_offsets[i]``
        is a thin strip of the rarity-colored border (used for rarity
        inference from color); ``bg_offsets[i]`` is a small patch of the
        icon background (used for age inference from color).
    slot_order
        Slot names in the same order as the offsets, e.g.
        ``["Helmet", "Body", "Gloves", "Necklace", "Ring", "Weapon",
        "Shoe", "Belt"]``.
    skip_per_slot_ocr
        Disable Lv.NN OCR (returns ``level=1`` for every slot). Useful
        for tests on synthetic captures where the OCR backend is not
        available.

    Returns
    -------
    list of ``IdentifiedItem``
        One per slot, in the same order as ``slot_order``. Slots whose
        identification failed still appear with placeholder ``age=0``,
        ``idx=0``, ``rarity="Common"`` so the list length is stable.
    """
    identified: Dict[str, Any] = identify_all(
        capture,
        equipment_offsets=equipment_offsets,
        border_offsets=border_offsets,
        bg_offsets=bg_offsets,
        pet_offsets=[],
        mount_offset=None,
        skill_offsets=[],
        slot_order=list(slot_order),
    )

    items: List[IdentifiedItem] = []
    for i, entry in enumerate(identified["items"]):
        if i >= len(equipment_offsets):
            break
        level = (1 if skip_per_slot_ocr
                 else max(1, extract_level(capture, equipment_offsets[i])))
        items.append(IdentifiedItem(
            slot=entry["slot"],
            age=int(entry.get("age", 0)),
            idx=int(entry.get("idx", 0)),
            rarity=str(entry.get("rarity", "Common")),
            level=level,
        ))
    return items
