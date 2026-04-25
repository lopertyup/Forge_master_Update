"""
============================================================
  FORGE MASTER — Enemy recompute pipeline (Phase 3 glue)

  Single entry-point used by the controller / simulator to
  turn an opponent screenshot into ready-to-inject combat
  stats. It chains together everything Phases 1 and 2
  produced:

      capture_region(bbox)
        → ocr_image(full_capture)               (text)
        → offsets_for_capture(W, H)             (sub-zones)
        → ocr per sub-zone                      (per-slot levels)
        → identify_all(capture, offsets)        (item / pet / mount / skill ids)
        → calculate_enemy_stats(profile, libs)  (final HP/Dmg + substats)

  Public API:

      recompute_from_capture(capture, ocr_text=None)
          One pure call that takes a PIL.Image (already
          captured) and returns
          (EnemyComputedStats, EnemyIdentifiedProfile, raw_text).

      capture_and_recompute(bbox)
          Convenience wrapper that grabs the screen + runs
          the full pipeline. Returns the same triple, plus
          the captured image so the UI can display it.

  Both functions are tolerant: a missing label library, a
  failing OCR pass, an unmatched icon — none of these crash;
  the returned profile / stats simply contain holes that
  damage_accuracy / health_accuracy will surface to the UI.
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from PIL import Image

from .enemy_libraries import load_libs
from .enemy_icon_identifier import identify_all
from .enemy_icon_offsets import offsets_for_capture
from .enemy_ocr_parser import parse_enemy_text
from .enemy_ocr_types import (
    EnemyIdentifiedProfile,
    EnemyComputedStats,
    IdentifiedItem,
    IdentifiedMount,
    IdentifiedPet,
    IdentifiedSkill,
)
from .enemy_stat_calculator import calculate_enemy_stats

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
#  Per-slot level extraction
# ────────────────────────────────────────────────────────────
#
# Levels are rendered as "Lv.NNN" (or "Lv NNN") underneath each
# icon. We OCR a thin strip just below the icon to pick them up
# without confusing them with the global Forge level in the
# header.

_LV_RE = re.compile(r"L\s*v\.?\s*(\d{1,3})", re.IGNORECASE)


def _ocr_strip(capture: Image.Image,
               x0: int, y0: int, x1: int, y1: int) -> str:
    """Run OCR on a single rectangle of a capture. Empty string on
    error. Imported lazily so headless testing works without the
    OCR backend installed."""
    try:
        from . import ocr  # type: ignore
        if not ocr.is_available():
            return ""
        crop = capture.crop((x0, y0, x1, y1))
        return ocr.ocr_image(crop)
    except Exception:
        log.exception("level-strip OCR failed")
        return ""


def _extract_level(capture: Image.Image,
                   icon_bbox: Tuple[int, int, int, int]) -> int:
    """OCR a strip BELOW the icon — that's where Lv.NNN lives.

    The strip is sized as: same width as the icon, height equal to
    half the icon's height, starting flush with the icon's bottom.
    """
    x0, y0, x1, y1 = icon_bbox
    h = max(1, y1 - y0)
    # Pull the strip immediately under the icon, stopping at the
    # capture's height.
    strip_y0 = min(capture.height, y1 - int(h * 0.20))
    strip_y1 = min(capture.height, y1 + int(h * 0.50))
    if strip_y1 <= strip_y0:
        return 0
    text = _ocr_strip(capture, x0, strip_y0, x1, strip_y1)
    m = _LV_RE.search(text or "")
    return int(m.group(1)) if m else 0


# ────────────────────────────────────────────────────────────
#  Main entry points
# ────────────────────────────────────────────────────────────


def _build_profile(
    capture: Image.Image,
    raw_text: str,
    *,
    skip_per_slot_ocr: bool = False,
) -> EnemyIdentifiedProfile:
    """Glue OCR text + visual identification into a single profile.

    ``skip_per_slot_ocr`` is mainly for tests — when the capture is
    small or synthetic, per-strip OCR adds no value and is slow.
    """
    profile = parse_enemy_text(raw_text)

    W, H = capture.size
    offsets = offsets_for_capture(W, H)

    identified = identify_all(
        capture,
        equipment_offsets=offsets["equipment"],
        border_offsets=offsets["border"],
        bg_offsets=offsets["bg"],
        pet_offsets=offsets["pets"],
        mount_offset=offsets["mount"][0] if offsets["mount"] else None,
        skill_offsets=offsets["skills"],
        slot_order=list(offsets["slot_order"]),
    )

    # ── items ───────────────────────────────────────────────
    items: list[IdentifiedItem] = []
    for i, entry in enumerate(identified["items"]):
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["equipment"][i]))
        items.append(IdentifiedItem(
            slot=entry["slot"],
            age=entry["age"],
            idx=entry["idx"],
            rarity=entry["rarity"],
            level=max(1, level),
        ))
    profile.items = items

    # ── pets ────────────────────────────────────────────────
    pets: list[IdentifiedPet] = []
    for i, entry in enumerate(identified["pets"]):
        if i >= len(offsets["pets"]):
            break
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["pets"][i]))
        pets.append(IdentifiedPet(
            id=int(entry.get("id", 0)),
            rarity=str(entry.get("rarity", "Common")),
            level=max(1, level),
        ))
    profile.pets = pets

    # ── mount ───────────────────────────────────────────────
    mount_data = identified["mount"]
    if mount_data is not None and offsets["mount"]:
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["mount"][0]))
        profile.mount = IdentifiedMount(
            id=int(mount_data.get("id", 0)),
            rarity=str(mount_data.get("rarity", "Common")),
            level=max(1, level),
        )

    # ── skills ──────────────────────────────────────────────
    skills: list[IdentifiedSkill] = []
    for i, entry in enumerate(identified["skills"]):
        if i >= len(offsets["skills"]):
            break
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["skills"][i]))
        skills.append(IdentifiedSkill(
            id=str(entry.get("id", "")),
            rarity=str(entry.get("rarity") or "Common"),
            level=max(1, level),
        ))
    profile.skills = skills

    return profile


def recompute_from_capture(
    capture: Image.Image,
    ocr_text: Optional[str] = None,
    *,
    skip_per_slot_ocr: bool = False,
) -> Tuple[EnemyComputedStats, EnemyIdentifiedProfile, str]:
    """Run the full Phase 1 + 2 pipeline on an already-captured image.

    ``ocr_text`` is the result of the standard text OCR pass on the
    full capture. When omitted the function will run it itself
    (requires the OCR backend to be available).
    """
    if ocr_text is None:
        try:
            from . import ocr  # type: ignore
            if ocr.is_available():
                ocr_text = ocr.ocr_image(capture)
            else:
                ocr_text = ""
        except Exception:
            log.exception("recompute_from_capture: OCR pass failed")
            ocr_text = ""

    profile = _build_profile(capture, ocr_text or "",
                             skip_per_slot_ocr=skip_per_slot_ocr)
    stats = calculate_enemy_stats(profile, load_libs())
    return stats, profile, ocr_text or ""


def capture_and_recompute(
    bbox,
    *,
    skip_per_slot_ocr: bool = False,
):
    """Take a screen bbox → return (stats, profile, raw_text, image)."""
    from . import ocr  # type: ignore
    img, text = ocr.capture_and_ocr(bbox)
    if img is None:
        return None
    stats, profile, raw_text = recompute_from_capture(
        img, text, skip_per_slot_ocr=skip_per_slot_ocr,
    )
    return stats, profile, raw_text, img
