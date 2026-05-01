"""Schema helpers for the canonical player profile store."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict

from data.canonical import EQUIPMENT_SLOTS, MOUNT_SLOT, PET_SLOTS, SKILL_SLOTS, SUBSTAT_KEYS

SCHEMA_VERSION = 2


def empty_substats() -> Dict[str, float]:
    return {key: 0.0 for key in SUBSTAT_KEYS}


def empty_equipment_slot() -> Dict[str, object]:
    return {
        "__name__": "",
        "__level__": 0,
        "__age__": 0,
        "__rarity__": "",
        "__idx__": 0,
        "hp_flat": 0.0,
        "damage_flat": 0.0,
        "substats": {},
        "attack_type": "",
        "weapon_attack_range": 0.0,
        "weapon_windup": 0.0,
        "weapon_recovery": 0.0,
        "projectile_speed": 0.0,
        "projectile_travel_time": 0.0,
    }


def empty_skill_slot() -> Dict[str, object]:
    return {
        "__name__": "",
        "__level__": 0,
        "__rarity__": "",
        "hp_flat": 0.0,
        "damage_flat": 0.0,
        "type": "",
        "substats": {},
    }


def empty_companion_slot() -> Dict[str, object]:
    return {
        "__name__": "",
        "__level__": 0,
        "__rarity__": "",
        "hp_flat": 0.0,
        "damage_flat": 0.0,
        "substats": {},
    }


def empty_profile() -> Dict[str, object]:
    return {
        "equipment": {slot: empty_equipment_slot() for slot in EQUIPMENT_SLOTS},
        "skills": {slot: empty_skill_slot() for slot in SKILL_SLOTS},
        "pets": {slot: empty_companion_slot() for slot in PET_SLOTS},
        "mount": {MOUNT_SLOT: empty_companion_slot()},
        "substats_total": empty_substats(),
        "base_profile": {},
    }


def clone_empty_profile() -> Dict[str, object]:
    return deepcopy(empty_profile())

