"""
============================================================
  FORGE MASTER — Single-equipment-popup scan (Phase 5 rev.4)

  Path triggered when the user opens the detail popup of ONE
  equipment piece in-game (the small in-game screen showing
  the icon + ``[Quantum] Energy Helmet`` title + Lv.NN +
  substats) and clicks the « 📷 » button on the corresponding
  tile of the Build view.

  Why a separate job from player_equipment.py? The popup
  carries a textual title that gives the AGE deterministically
  (``[Quantum]`` → AGE_NAME_TO_INT["Quantum"] → 7) — much
  stronger signal than a colour heuristic on a noisy 18 %
  centre patch. The slot is supplied by the UI context
  (``force_slot=`` is mandatory). Single-tile scope means we
  can also reuse autocrop_capture aggressively without
  wrestling with grid offsets.

  STRAT (cf. SCAN_REFACTOR.txt §3 STRAT A → STRAT B):

      0. force_slot is REQUIRED (UI context always knows it).
         Returns status="scan_error" otherwise.
      1. parse_popup_metadata → tag (Age name) + name + level.
      2. If tag is a known age → STRAT A: load refs (age, slot)
         in mode="exact". If the score top-1 is below threshold,
         degrade to STRAT B (mode="all_ages").
         If tag is missing/unreadable → STRAT B straight away.
      3. identify_rarity_from_color on the popup border as a
         filet de sécurité.
      4. extract_popup_level via _lv (fallback when the title
         OCR did not return a Lv).
      5. Slot Weapon → enrich_weapon_slot adds windup / range
         / projectile_*.
      6. Returns ScanResult.matches=[Candidate], debug["slot_dict"]
         is a Dict[section_name, slot_dict] with ONE entry —
         same shape as player_equipment.scan() so the controller
         can reuse the same merge path.

  Public API:

      scan(capture, *, libs=None, debug_dir=None,
           threshold=DEFAULT_THRESHOLD,
           force_slot=<required>, force_age=None) -> ScanResult
============================================================
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from ..colors import (
    AGE_NAME_TO_INT,
    identify_rarity_from_color,
)
from ..core import (
    DEFAULT_THRESHOLD,
    autocrop_capture,
    is_cell_filled,
    match as core_match,
)
from ..refs import load_references
from ..types import Candidate, ScanResult

from . import _lv, _title
from ._weapon_enrich import enrich_weapon_slot

log = logging.getLogger(__name__)


# Slots accepted by force_slot. Mirrors backend.scanner.ocr_types.SLOT_ORDER.
_VALID_SLOTS = {"Helmet", "Body", "Gloves", "Necklace",
                "Ring", "Weapon", "Shoe", "Belt"}


def _border_crop(capture: Image.Image) -> Image.Image:
    """Sample a strip near the top of the popup for the rarity
    border colour. The popup frames the whole window with a
    rarity-coloured border; the top edge is the cleanest read
    (no Lv cartouche, no description text)."""
    w, h = capture.size
    margin_h = max(1, int(h * 0.06))
    return capture.crop((0, 0, w, margin_h)) if h > 2 * margin_h else capture


def _resolve_piece_stats(
    slot_dict: Dict[str, Any],
    *,
    slot: str,
    libs: Dict[str, Any],
) -> None:
    """ItemBalancingLibrary lookup (hp_flat, damage_flat, name).
    Mirrors the helper of the same name in player_equipment.py
    but takes ``libs`` directly so the equipment_popup job
    keeps its small footprint."""
    age = int(slot_dict.get("__age__", 0))
    idx = int(slot_dict.get("__idx__", 0))
    level = int(slot_dict.get("__level__", 0))
    rarity = slot_dict.get("__rarity__") or "Common"

    item_balancing_library = libs.get("item_balancing_library") or {}
    config = libs.get("item_balancing_config") or {}
    level_scaling_base = float(config.get("LevelScalingBase") or 1.01)

    try:
        from backend.scanner.ocr_types import SLOT_TO_JSON_TYPE
        from backend.calculator.item_keys import (
            item_key as _item_key,
            stat_type as _stat_type,
        )
    except Exception:  # pragma: no cover - defensive
        log.exception("equipment_popup: item_keys helpers unavailable")
        return

    json_type = SLOT_TO_JSON_TYPE.get(slot, slot)
    key = _item_key(age, json_type, idx)
    item_data = item_balancing_library.get(key)
    if not isinstance(item_data, dict):
        return

    name = item_data.get("Name") or item_data.get("DisplayName")
    if not name:
        name = f"{rarity} {slot} #{idx}"
    slot_dict["__name__"] = str(name)

    equip_stats = item_data.get("EquipmentStats") or []
    level_factor = math.pow(level_scaling_base,
                            max(0, level - 1)) if level else 1.0
    dmg = 0.0
    hp = 0.0
    for stat in equip_stats:
        stype = _stat_type(stat)
        try:
            value = float(stat.get("Value") or 0.0) * level_factor
        except (TypeError, ValueError):
            continue
        if stype == "Damage":
            dmg += value
        elif stype == "Health":
            hp += value
    slot_dict["damage_flat"] = dmg
    slot_dict["hp_flat"]     = hp


def scan(
    capture: Image.Image,
    *,
    libs:       Optional[Dict[str, Any]] = None,
    debug_dir:  Optional[Path]           = None,
    threshold:  float                    = DEFAULT_THRESHOLD,
    force_slot: Optional[str]            = None,
    force_age:  Optional[int]            = None,
) -> ScanResult:
    """Identify ONE equipment piece from a popup detail capture.

    ``force_slot`` is REQUIRED: the popup title carries the
    item NAME but not its slot type, and the same item name can
    repeat across slots (e.g. several distinct rings called
    "Energy Ring" at different ages). The Build view always
    passes the slot the user is updating. Returns
    ``status="scan_error"`` when ``force_slot`` is missing.

    ``force_age`` is accepted but normally ignored — the OCR
    balise is the canonical source. When the balise is illegible
    AND ``force_age`` is provided, we use it as a hint for
    STRAT A's age choice.
    """
    if capture is None:
        return ScanResult(matches=[], status="no_match",
                          debug={"reason": "capture is None"})
    if force_slot not in _VALID_SLOTS:
        return ScanResult(
            matches=[],
            status="scan_error",
            debug={"reason": f"force_slot is required, got {force_slot!r}"},
        )

    sprite = autocrop_capture(capture)
    if not is_cell_filled(sprite):
        return ScanResult(matches=[], status="no_match",
                          debug={"reason": "is_cell_filled=False"})

    # ---- OCR title → age tag + name + level
    meta = _title.parse_popup_metadata(
        capture, kind="companion", debug_zone="equipment_popup",
    )
    tag = meta.get("tag")  # e.g. "Quantum" / "Modern" / None
    name_ocr = meta.get("name") or ""
    level_ocr = meta.get("level")
    raw_text = meta.get("raw") or ""

    age_from_tag: Optional[int] = AGE_NAME_TO_INT.get(tag) if tag else None
    age_hint: Optional[int] = (
        age_from_tag
        if age_from_tag is not None
        else (force_age if isinstance(force_age, int) else None)
    )

    # ---- Lazy libs
    if libs is None:
        try:
            from backend.data.libraries import load_libs as _load
            libs = _load() or {}
        except Exception:  # pragma: no cover - defensive
            log.exception("equipment_popup: load_libs() failed")
            libs = {}

    # ---- STRAT A: refs for (age_hint, force_slot)
    candidates: List[Candidate] = []
    if age_hint is not None:
        try:
            refs_a = load_references("equipment", age=int(age_hint),
                                     slot=force_slot, mode="exact")
        except Exception:  # pragma: no cover - defensive
            log.exception("equipment_popup: load_references(exact) failed")
            refs_a = []
        if refs_a:
            candidates = core_match(sprite, refs_a, ocr_name=name_ocr,
                                    autocrop=False)

    # ---- STRAT B fallback: all ages for the same slot
    fallback_used = False
    if not candidates or candidates[0].score < threshold:
        try:
            refs_b = load_references("equipment", slot=force_slot,
                                     mode="all_ages")
        except Exception:  # pragma: no cover - defensive
            log.exception("equipment_popup: load_references(all_ages) failed")
            refs_b = []
        if refs_b:
            cand_b = core_match(sprite, refs_b, ocr_name=name_ocr,
                                autocrop=False)
            if cand_b and (not candidates or cand_b[0].score > candidates[0].score):
                candidates = cand_b
                fallback_used = True

    if not candidates:
        return ScanResult(
            matches=[],
            status="no_match",
            debug={"reason": "matcher returned no candidates",
                   "tag": tag, "raw_text": raw_text},
        )

    best = candidates[0]

    # ---- Rarity (filet de sécurité)
    rarity_color = identify_rarity_from_color(_border_crop(capture))

    # ---- Level (Lv.NN cartouche fallback)
    if level_ocr is None:
        try:
            level_ocr = _lv.extract_popup_level(
                capture, debug_zone="equipment_popup",
            )
        except Exception:  # pragma: no cover - defensive
            log.exception("equipment_popup: cartouche Lv extraction failed")

    # ---- Assemble slot_dict
    slot_dict: Dict[str, Any] = {
        "__age__":   int(best.age) if best.age is not None
                                    else (age_hint or 0),
        "__idx__":   int(best.idx) if best.idx is not None else 0,
        "__level__": int(level_ocr) if level_ocr else 0,
        "__rarity__": rarity_color or "Common",
        "__name__":  best.payload.get("name") or best.name,
    }
    _resolve_piece_stats(slot_dict, slot=force_slot, libs=libs)
    if force_slot == "Weapon":
        enrich_weapon_slot(slot_dict, libs=libs)

    # ---- Build the controller-shaped Dict[section, slot_dict]
    try:
        from backend.constants import EQUIPMENT_SLOTS, EQUIPMENT_SLOT_NAMES
        slot_to_section = dict(zip(EQUIPMENT_SLOT_NAMES, EQUIPMENT_SLOTS))
        section_dict: Dict[str, Any] = {
            slot_to_section[force_slot]: slot_dict,
        } if force_slot in slot_to_section else {}
    except Exception:  # pragma: no cover - defensive
        section_dict = {}

    enriched = Candidate(
        name=str(slot_dict["__name__"]),
        score=best.score,
        age=int(slot_dict["__age__"]),
        slot=force_slot,
        rarity=slot_dict["__rarity__"],
        idx=int(slot_dict["__idx__"]),
        payload=dict(slot_dict),
    )
    status = "ok" if best.score >= threshold else "low_confidence"

    return ScanResult(
        matches=[enriched],
        status=status,
        debug={
            "slot_dict":       section_dict,
            "force_slot":      force_slot,
            "tag":             tag,
            "age_from_tag":    age_from_tag,
            "rarity_color":    rarity_color,
            "fallback_used":   fallback_used,
            "raw_text":        raw_text,
            "ocr_name":        name_ocr,
            "level":           level_ocr,
            "top1_score":      best.score,
        },
    )


__all__ = ["scan"]
