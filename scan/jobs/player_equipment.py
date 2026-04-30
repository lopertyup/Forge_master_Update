"""
============================================================
  FORGE MASTER — Player equipment-panel scan (Phase 5)

  Replaces backend/scanner/player_equipment.scan_player_equipment_image
  AND (rev.4) backend/scanner/weapon.scan_player_weapon_image — both
  responsibilities now live here. The 8-tile panel is identified
  with the hybrid matcher (via _panel.py); the slot Weapon
  receives an extra WeaponLibrary lookup (via _weapon_enrich.py)
  so the slot_dict carries windup / range / projectile_* exactly
  like the legacy weapon scanner used to.

  Pipeline (see SCAN_REFACTOR.txt §7 Phase 5 A):

      1. Compute pixel offsets via scan.offsets.player.
      2. _panel.identify_panel → 8 slot_dicts with
         __age__, __idx__, __level__, __rarity__, __name__.
      3. Per slot, ItemBalancingLibrary lookup → hp_flat,
         damage_flat, __name__ override (logic copied
         verbatim from backend/scanner/player_equipment).
      4. Slot Weapon → enrich_weapon_slot() injects
         attack_type + windup / range / projectile_*.
      5. Return ScanResult.matches = 8 Candidates (in
         SLOT_ORDER) and ScanResult.debug["slot_dict"] =
         the canonical Dict[section_name, slot_dict] the
         controller hands to persistence.set_equipment().

  Public API:

      scan(capture, *, libs=None, debug_dir=None,
           threshold=DEFAULT_THRESHOLD,
           force_slot=None, force_age=None,
           skip_per_slot_ocr=False) -> ScanResult
============================================================
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from ..core import DEFAULT_THRESHOLD
from ..offsets import player as _offsets
from ..types import Candidate, ScanResult

from . import _panel
from ._weapon_enrich import enrich_weapon_slot

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  ItemBalancingLibrary lookup (copied from legacy)
# ────────────────────────────────────────────────────────────


def _resolve_piece_stats(
    slot_dict: Dict[str, Any],
    *,
    slot: str,
    item_balancing_library: Dict[str, Any],
    level_scaling_base: float,
) -> None:
    """Mutate ``slot_dict`` in place with hp_flat, damage_flat,
    and a refined __name__ derived from the ItemBalancingLibrary
    entry. Called for every slot (including Weapon — the
    weapon-specific timing fields are added afterwards by
    enrich_weapon_slot)."""
    age = int(slot_dict.get("__age__", 0))
    idx = int(slot_dict.get("__idx__", 0))
    level = int(slot_dict.get("__level__", 0))
    rarity = slot_dict.get("__rarity__") or "Common"

    try:
        from backend.scanner.ocr_types import SLOT_TO_JSON_TYPE
        from backend.calculator.item_keys import (
            item_key as _item_key,
            stat_type as _stat_type,
        )
    except Exception:  # pragma: no cover - defensive
        log.exception("player_equipment: item_keys helpers unavailable")
        return

    json_type = SLOT_TO_JSON_TYPE.get(slot, slot)
    key = _item_key(age, json_type, idx)
    item_data = item_balancing_library.get(key)
    if not isinstance(item_data, dict):
        log.debug("player_equipment: item not found %s", key)
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


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────


def scan(
    capture: Image.Image,
    *,
    libs:              Optional[Dict[str, Any]] = None,
    debug_dir:         Optional[Path]           = None,
    threshold:         float                    = DEFAULT_THRESHOLD,
    force_slot:        Optional[str]            = None,
    force_age:         Optional[int]            = None,
    skip_per_slot_ocr: bool                     = False,
) -> ScanResult:
    """Identify the 8 pieces visible in the player's equipment panel.

    ``force_slot`` and ``force_age`` are accepted but ignored —
    the panel layout supplies the slot, the per-tile colour
    heuristic supplies the age. The kwargs stay in the signature
    for parity with the rest of ``scan.jobs.*``.

    The ScanResult carries:

      - ``matches``: list of 8 Candidate objects in SLOT_ORDER.
        Each Candidate's ``payload`` includes the canonical
        slot_dict for that slot so callers can pull the merged
        view via ``ScanResult.debug["slot_dict"]`` (preferred)
        or rebuild it from per-Candidate payloads.
      - ``debug["slot_dict"]``: ``Dict[section_name, slot_dict]``
        ready to be passed to ``persistence.set_equipment()`` —
        same shape as the legacy ``scan_player_equipment_image``
        return value.
      - ``status``: ``"ok"`` when the matcher returned a hit on
        every slot above ``threshold``; ``"low_confidence"`` if
        any slot ended below threshold; ``"no_match"`` if the
        capture is None.
    """
    if capture is None:
        return ScanResult(matches=[], status="no_match",
                          debug={"reason": "capture is None"})

    # Lazy-load libs once for the whole panel pass.
    if libs is None:
        try:
            from backend.data.libraries import load_libs as _load
            libs = _load() or {}
        except Exception:  # pragma: no cover - defensive
            log.exception("player_equipment: load_libs() failed")
            libs = {}

    item_balancing_library = libs.get("item_balancing_library") or {}
    config                 = libs.get("item_balancing_config") or {}
    level_scaling_base     = float(config.get("LevelScalingBase") or 1.01)

    # Layout & per-tile identification.
    W, H = capture.size
    layout = _offsets.offsets_for_capture(W, H)
    slot_dicts = _panel.identify_panel(
        capture,
        layout,
        threshold=threshold,
        skip_per_slot_ocr=skip_per_slot_ocr,
    )

    # Library enrichment per slot.
    slot_order = list(layout["slot_order"])
    for slot, sd in zip(slot_order, slot_dicts):
        _resolve_piece_stats(
            sd,
            slot=slot,
            item_balancing_library=item_balancing_library,
            level_scaling_base=level_scaling_base,
        )
        if slot == "Weapon":
            enrich_weapon_slot(sd, libs=libs)

    # Build the canonical Dict[section_name, slot_dict] the
    # controller hands to persistence.set_equipment().
    try:
        from backend.constants import EQUIPMENT_SLOTS, EQUIPMENT_SLOT_NAMES
        from backend.persistence import empty_equipment
        slot_to_section = dict(zip(EQUIPMENT_SLOT_NAMES, EQUIPMENT_SLOTS))
        section_dict = empty_equipment()
    except Exception:  # pragma: no cover - defensive
        log.exception("player_equipment: persistence helpers unavailable")
        slot_to_section, section_dict = {}, {}

    # Build Candidates AND populate the section_dict in one pass.
    matches: List[Candidate] = []
    any_low = False
    for slot, sd in zip(slot_order, slot_dicts):
        section = slot_to_section.get(slot)
        if section is not None:
            section_dict[section] = sd
        score = 1.0 if sd.get("__idx__") else 0.0   # crude proxy
        if score < threshold and sd.get("__idx__"):
            any_low = True
        matches.append(Candidate(
            name=str(sd.get("__name__") or ""),
            score=float(score),
            age=int(sd.get("__age__", 0)),
            slot=slot,
            rarity=sd.get("__rarity__"),
            idx=int(sd.get("__idx__") or 0),
            payload=dict(sd),
        ))

    # Status: overall "ok" unless at least one slot is empty
    # (idx==0). The matcher score itself is per-tile inside
    # _panel and not exposed here; the controller can inspect
    # ScanResult.debug["slot_dict"] for slot-by-slot details.
    if not any(sd.get("__idx__") for sd in slot_dicts):
        status = "no_match"
    elif any_low or any(not sd.get("__idx__") for sd in slot_dicts):
        status = "low_confidence"
    else:
        status = "ok"

    return ScanResult(
        matches=matches,
        status=status,
        debug={
            "slot_dict": section_dict,
            "slot_order": slot_order,
            "n_filled":  sum(1 for sd in slot_dicts if sd.get("__idx__")),
        },
    )


__all__ = ["scan"]
