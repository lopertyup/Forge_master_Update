"""
============================================================
  FORGE MASTER — Opponent recompute pipeline (orchestrator)

  Single entry-point used by the controller / simulator to
  turn an opponent screenshot into ready-to-inject combat
  stats. The actual work lives in the focused sub-modules:

      capture (PIL)
        → scanner.ocr.ocr_image(full_capture)            (text)
        → scanner.offsets.opponent.offsets_for_capture() (sub-zones)
        → scanner.panel.identify_equipment_panel()       (8 items)
        → scanner.icon_matcher.identify_all()            (pets / mount /
                                                            skills)
        → scanner.ocr_parser.parse_enemy_text()          (substats /
                                                            displayed totals)
        → calculator.combat.calculate_enemy_stats()      (final stats)

  This module is deliberately thin: every line of "how" lives in
  one of the called modules. Adding a new identification step
  goes there, not here.

  Public API:
      recompute_from_capture(capture, ocr_text=None)
            (EnemyComputedStats, EnemyIdentifiedProfile, raw_text)

      capture_and_recompute(bbox)
            same triple plus the captured image, for the UI.
============================================================
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from PIL import Image

from .calculator.combat import calculate_enemy_stats
from .data.libraries import load_libs
from .scanner.icon_matcher import identify_all
from .scanner.ocr_parser import parse_enemy_text
from .scanner.ocr_types import (
    EnemyComputedStats,
    EnemyIdentifiedProfile,
    IdentifiedMount,
    IdentifiedPet,
    IdentifiedSkill,
)
from .scanner.offsets.opponent import offsets_for_capture
from .scanner.panel import extract_level as _extract_level
from .scanner.panel import identify_equipment_panel

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Profile assembly
# ────────────────────────────────────────────────────────────


def _build_profile(
    capture: Image.Image,
    raw_text: str,
    *,
    skip_per_slot_ocr: bool = False,
) -> EnemyIdentifiedProfile:
    """Glue OCR text + visual identification into a single profile."""
    profile = parse_enemy_text(raw_text)

    W, H = capture.size
    offsets = offsets_for_capture(W, H)

    # Items — shared with the player-side scanner.
    profile.items = identify_equipment_panel(
        capture,
        equipment_offsets=offsets["equipment"],
        border_offsets=offsets["border"],
        bg_offsets=offsets["bg"],
        slot_order=list(offsets["slot_order"]),
        skip_per_slot_ocr=skip_per_slot_ocr,
    )

    # Pets / mount / skills: sub-zones of the same capture.
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

    mount_data = identified["mount"]
    if mount_data is not None and offsets["mount"]:
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["mount"][0]))
        profile.mount = IdentifiedMount(
            id=int(mount_data.get("id", 0)),
            rarity=str(mount_data.get("rarity", "Common")),
            level=max(1, level),
        )

    skills: list[IdentifiedSkill] = []
    for i, entry in enumerate(identified["skills"]):
        if i >= len(offsets["skills"]):
            break
        level = (0 if skip_per_slot_ocr
                 else _extract_level(capture, offsets["skills"][i]))
        skills.append(IdentifiedSkill(
            id=str(entry.get("name") or entry.get("id") or ""),
            rarity=str(entry.get("rarity") or "Common"),
            level=max(1, level),
        ))
    profile.skills = skills

    return profile


# ────────────────────────────────────────────────────────────
#  Public entry points
# ────────────────────────────────────────────────────────────


def recompute_from_capture(
    capture: Image.Image,
    ocr_text: Optional[str] = None,
    *,
    skip_per_slot_ocr: bool = False,
) -> Tuple[EnemyComputedStats, EnemyIdentifiedProfile, str]:
    """Run the full pipeline on an already-captured image."""
    if ocr_text is None:
        try:
            from .scanner import ocr  # type: ignore
            ocr_text = ocr.ocr_image(capture) if ocr.is_available() else ""
        except Exception:
            log.exception("recompute_from_capture: OCR pass failed")
            ocr_text = ""

    profile = _build_profile(capture, ocr_text or "",
                             skip_per_slot_ocr=skip_per_slot_ocr)
    stats = calculate_enemy_stats(profile, load_libs())
    return stats, profile, ocr_text or ""


def capture_and_recompute(bbox, *, skip_per_slot_ocr: bool = False):
    """Take a screen bbox → return (stats, profile, raw_text, image)."""
    from .scanner import ocr  # type: ignore
    img, text = ocr.capture_and_ocr(bbox)
    if img is None:
        return None
    stats, profile, raw_text = recompute_from_capture(
        img, text, skip_per_slot_ocr=skip_per_slot_ocr,
    )
    return stats, profile, raw_text, img
