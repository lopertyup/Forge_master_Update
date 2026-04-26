"""
Player equipment -- equipment.txt I/O.

The player's equipped 8 pieces are persisted slot-by-slot, mirroring the
pets.txt / mount.txt pattern. Each section matches one of EQUIPMENT_SLOTS
(EQUIP_HELMET, EQUIP_BODY, ...). Empty slots remain present in the file
but with zero / empty values.

Schema (per section)::

    [EQUIP_HELMET]
    __name__    = Quantum Helmet
    __rarity__  = ultimate
    __age__     = 7
    __idx__     = 0
    __level__   = 87
    hp_flat     = 0.0
    damage_flat = 12345678.0
    attack_type = melee     # weapon-only; absent on other slots

The hp_flat / damage_flat values are CACHED level-scaled stats pulled
from ItemBalancingLibrary at scan time
(`base_value * 1.01^(level - 1)`). Re-scanning rewrites them. Editing
the file by hand is supported: a missing or zero value in a slot just
means "no contribution", and an unknown __name__ degrades gracefully.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from ..constants import (
    EQUIPMENT_FILE,
    EQUIPMENT_NUMERIC_KEYS,
    EQUIPMENT_SLOTS,
)
from ._io import _ensure_parent_dir

log = logging.getLogger(__name__)


def empty_equipment_slot() -> Dict[str, object]:
    """Zero-valued slot dict. Identity fields default to empty strings
    so a freshly-installed equipment.txt is human-readable.
    """
    return {
        "__name__":    "",
        "__rarity__":  "",
        "__age__":     0,
        "__idx__":     0,
        "__level__":   0,
        "hp_flat":     0.0,
        "damage_flat": 0.0,
        # attack_type is only meaningful on the Weapon slot but kept on
        # all slots (empty string when N/A) for round-trip simplicity.
        "attack_type": "",
    }


def empty_equipment() -> Dict[str, Dict[str, object]]:
    """Return a fresh, empty 8-slot equipment dict."""
    return {slot: empty_equipment_slot() for slot in EQUIPMENT_SLOTS}


def _coerce(key: str, val: str) -> object:
    """Cast a parsed key=value pair to its expected Python type."""
    if key in ("__name__", "__rarity__", "attack_type"):
        return val
    if key in ("__age__", "__idx__", "__level__"):
        try:
            return int(val)
        except ValueError:
            log.warning("equipment.txt: invalid int for %s = %r", key, val)
            return 0
    if key in EQUIPMENT_NUMERIC_KEYS:
        try:
            return float(val)
        except ValueError:
            log.warning("equipment.txt: invalid float for %s = %r", key, val)
            return 0.0
    # Unknown key -- preserve as string so a hand-added field is not
    # silently dropped.
    return val


def load_equipment() -> Dict[str, Dict[str, object]]:
    """Load equipment.txt. Missing file -> empty 8-slot dict."""
    equipment = empty_equipment()
    if not os.path.isfile(EQUIPMENT_FILE):
        return equipment

    with open(EQUIPMENT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current: Optional[str] = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            current = section if section in EQUIPMENT_SLOTS else None
            continue
        if current is None or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        equipment[current][key] = _coerce(key, val)
    return equipment


def save_equipment(equipment: Dict[str, Dict[str, object]]) -> None:
    """Persist the 8-slot equipment dict to equipment.txt."""
    _ensure_parent_dir(EQUIPMENT_FILE)
    with open(EQUIPMENT_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER -- Player equipment (8 slots, editable by hand)\n")
        f.write("# Each section caches the per-piece HP/Dmg derived from\n")
        f.write("# ItemBalancingLibrary at scan time. Re-scan to refresh.\n")
        f.write("# ============================================================\n\n")
        for slot in EQUIPMENT_SLOTS:
            entry = equipment.get(slot, empty_equipment_slot())
            f.write(f"[{slot}]\n")
            if entry.get("__name__"):
                f.write(f"{'__name__':12s} = {entry['__name__']}\n")
            if entry.get("__rarity__"):
                f.write(f"{'__rarity__':12s} = {entry['__rarity__']}\n")
            f.write(f"{'__age__':12s} = {int(entry.get('__age__', 0) or 0)}\n")
            f.write(f"{'__idx__':12s} = {int(entry.get('__idx__', 0) or 0)}\n")
            f.write(f"{'__level__':12s} = {int(entry.get('__level__', 0) or 0)}\n")
            f.write(f"{'hp_flat':12s} = {float(entry.get('hp_flat', 0.0) or 0.0)}\n")
            f.write(f"{'damage_flat':12s} = {float(entry.get('damage_flat', 0.0) or 0.0)}\n")
            atk_type = entry.get("attack_type") or ""
            if atk_type:
                f.write(f"{'attack_type':12s} = {atk_type}\n")
            f.write("\n")
