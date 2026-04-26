"""
============================================================
  FORGE MASTER -- Player equipment-panel scanner

  Take a screenshot of the player's "Equipement" panel and
  return the 8-slot dict ready to drop into equipment.txt
  via persistence.save_equipment().

  Pipeline:
    1. Load the equipment-panel offsets (per-user override or
       the default 4x2 grid).
    2. Run the shared identify_equipment_panel() helper to get
       8 IdentifiedItem records (slot + age + idx + rarity +
       level).
    3. For each record, look up ItemBalancingLibrary entry,
       apply level scaling (1.01^(level-1)) to extract the
       per-piece base hp_flat / damage_flat. Pull the weapon's
       attack_type from WeaponLibrary on the Weapon slot.
    4. Build an 8-slot dict with the same shape as
       persistence.empty_equipment().

  No fight math here -- just the ground-truth derivation.
  Substats stay in profile.txt (aggregated by the game).
============================================================
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional

from PIL import Image

from .constants import EQUIPMENT_SLOTS, EQUIPMENT_SLOT_NAMES
from .enemy_libraries import load_libs
from .enemy_ocr_types import SLOT_TO_JSON_TYPE
from .enemy_stat_calculator import _item_key, _stat_type
from .equipment_pipeline import identify_equipment_panel
from .persistence import empty_equipment, empty_equipment_slot
from . import player_equipment_offsets as offsets_mod

log = logging.getLogger(__name__)


_SLOT_TO_SECTION = dict(zip(EQUIPMENT_SLOT_NAMES, EQUIPMENT_SLOTS))


# ────────────────────────────────────────────────────────────
#  Per-piece library lookup
# ────────────────────────────────────────────────────────────


def _resolve_piece_stats(
    age: int,
    slot: str,
    idx: int,
    level: int,
    rarity: str,
    item_balancing_library: Dict,
    weapon_library: Dict,
    level_scaling_base: float,
) -> Dict[str, object]:
    """Return a saved-equipment-slot dict for one identified piece.

    Falls back to an empty slot when the library lookup fails
    (unknown {age, type, idx} combo). Logs the miss but never
    raises: a hand-edited equipment.txt entry can fix the miss
    later.
    """
    slot_dict = empty_equipment_slot()
    slot_dict["__age__"]    = int(age)
    slot_dict["__idx__"]    = int(idx)
    slot_dict["__level__"]  = int(level) if level else 0
    slot_dict["__rarity__"] = rarity or ""

    json_type = SLOT_TO_JSON_TYPE.get(slot, slot)
    key = _item_key(int(age), json_type, int(idx))
    item_data = item_balancing_library.get(key)
    if not isinstance(item_data, dict):
        log.debug("player scanner: item not found %s", key)
        return slot_dict

    # Display name -- ItemBalancingLibrary often stores a
    # ``Name`` or ``DisplayName`` field; if absent, fall back
    # to ``"<Rarity> <Type> #<Idx>"`` so the UI shows something
    # readable instead of a blank cell.
    name = item_data.get("Name") or item_data.get("DisplayName")
    if not name:
        name = f"{rarity or 'Common'} {slot} #{idx}"
    slot_dict["__name__"] = str(name)

    # Cached level-scaled main stats
    equip_stats = item_data.get("EquipmentStats") or []
    level_factor = math.pow(level_scaling_base,
                            max(0, int(level) - 1)) if level else 1.0
    dmg = 0.0
    hp  = 0.0
    for stat in equip_stats:
        stype = _stat_type(stat)
        value = float(stat.get("Value") or 0.0) * level_factor
        if stype == "Damage":
            dmg += value
        elif stype == "Health":
            hp += value
    slot_dict["damage_flat"] = dmg
    slot_dict["hp_flat"]     = hp

    # Weapon-only: pull attack_type from WeaponLibrary so the
    # downstream simulator knows whether the weapon is melee or
    # ranged.
    if slot == "Weapon":
        w_key = _item_key(int(age), "Weapon", int(idx))
        w_data = weapon_library.get(w_key)
        if isinstance(w_data, dict):
            attack_range = float(w_data.get("AttackRange") or 0.0)
            slot_dict["attack_type"] = "ranged" if attack_range >= 1.0 else "melee"

    return slot_dict


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────


def scan_player_equipment_image(
    capture: Image.Image,
    libs: Optional[Dict] = None,
    *,
    skip_per_slot_ocr: bool = False,
) -> Optional[Dict[str, Dict[str, object]]]:
    """Identify the player's 8 pieces from one panel screenshot.

    Returns an 8-slot dict (keys = EQUIPMENT_SLOTS) ready to be
    passed to persistence.save_equipment(), or ``None`` if the
    capture is unusable.

    ``skip_per_slot_ocr`` mirrors the enemy pipeline flag: when
    True the scanner returns level=1 for every slot. Useful for
    tests on synthetic captures without an OCR backend.
    """
    if capture is None:
        return None

    libs = libs or load_libs()
    item_balancing_library = libs.get("item_balancing_library") or {}
    weapon_library         = libs.get("weapon_library") or {}
    config                 = libs.get("item_balancing_config") or {}
    level_scaling_base     = float(
        config.get("LevelScalingBase") or 1.01)

    W, H = capture.size
    layout = offsets_mod.offsets_for_capture(W, H)

    items = identify_equipment_panel(
        capture,
        equipment_offsets=layout["equipment"],
        border_offsets=layout["border"],
        bg_offsets=layout["bg"],
        slot_order=list(layout["slot_order"]),
        skip_per_slot_ocr=skip_per_slot_ocr,
    )

    out = empty_equipment()
    for piece in items:
        section = _SLOT_TO_SECTION.get(piece.slot)
        if section is None:
            log.warning("player scanner: unknown slot name %r", piece.slot)
            continue
        out[section] = _resolve_piece_stats(
            age=piece.age,
            slot=piece.slot,
            idx=piece.idx,
            level=piece.level,
            rarity=piece.rarity,
            item_balancing_library=item_balancing_library,
            weapon_library=weapon_library,
            level_scaling_base=level_scaling_base,
        )
    return out
