"""
Canonical names shared by data, scan, backend and UI.

This module is dependency-free so any layer can import it.
"""

from __future__ import annotations

import re
from typing import Dict, Optional


EQUIPMENT_SLOTS = (
    "Helmet",
    "Body",
    "Gloves",
    "Necklace",
    "Ring",
    "Weapon",
    "Shoe",
    "Belt",
)

SKILL_SLOTS = ("Skill_1", "Skill_2", "Skill_3")
PET_SLOTS = ("Pet_1", "Pet_2", "Pet_3")
MOUNT_SLOT = "Mount"

RARITIES = ("Common", "Rare", "Epic", "Legendary", "Ultimate", "Mythic")

AGES = (
    "Primitive",
    "Medieval",
    "Early-Modern",
    "Modern",
    "Space",
    "Interstellar",
    "Multiverse",
    "Quantum",
    "Underworld",
    "Divine",
)

AGE_INT_TO_NAME: Dict[int, str] = dict(enumerate(AGES))
AGE_NAME_TO_INT: Dict[str, int] = {
    "Primitive": 0,
    "Medieval": 1,
    "Earlymodern": 2,
    "Early-Modern": 2,
    "EarlyModern": 2,
    "Modern": 3,
    "Space": 4,
    "Interstellar": 5,
    "Multiverse": 6,
    "Quantum": 7,
    "Underworld": 8,
    "Divine": 9,
}

EQUIPMENT_SLOT_TO_ICON_FOLDER: Dict[str, str] = {
    "Helmet": "Headgear",
    "Body": "Armor",
    "Gloves": "Glove",
    "Necklace": "Neck",
    "Ring": "Ring",
    "Weapon": "Weapon",
    "Shoe": "Foot",
    "Belt": "Belt",
    "Headgear": "Headgear",
    "Armor": "Armor",
    "Armour": "Armor",
    "Glove": "Glove",
    "Neck": "Neck",
    "Shoes": "Foot",
    "Foot": "Foot",
}

SLOT_TO_JSON_TYPE: Dict[str, str] = {
    "Helmet": "Helmet",
    "Body": "Armour",
    "Gloves": "Gloves",
    "Necklace": "Necklace",
    "Ring": "Ring",
    "Weapon": "Weapon",
    "Shoe": "Shoes",
    "Belt": "Belt",
}

SLOT_TO_TYPE_ID: Dict[str, int] = {
    "Helmet": 0,
    "Body": 1,
    "Gloves": 2,
    "Necklace": 3,
    "Ring": 4,
    "Weapon": 5,
    "Shoe": 6,
    "Belt": 7,
}

SUBSTAT_KEYS = (
    "Crit Chance",
    "Crit Damage",
    "Block Chance",
    "Health Regen",
    "Lifesteal",
    "Double Chance",
    "Damage%",
    "Melee%",
    "Ranged%",
    "Attack Speed",
    "Skill Damage",
    "Skill Cooldown",
    "Health%",
)

SUBSTAT_ALIASES: Dict[str, str] = {
    "crit chance": "Crit Chance",
    "critical chance": "Crit Chance",
    "crit_chance": "Crit Chance",
    "crit damage": "Crit Damage",
    "critical damage": "Crit Damage",
    "crit_damage": "Crit Damage",
    "block chance": "Block Chance",
    "block_chance": "Block Chance",
    "health regen": "Health Regen",
    "health_regen": "Health Regen",
    "lifesteal": "Lifesteal",
    "life steal": "Lifesteal",
    "double chance": "Double Chance",
    "double_chance": "Double Chance",
    "damage": "Damage%",
    "damage%": "Damage%",
    "damage_pct": "Damage%",
    "melee": "Melee%",
    "melee%": "Melee%",
    "melee damage": "Melee%",
    "melee_pct": "Melee%",
    "ranged": "Ranged%",
    "ranged%": "Ranged%",
    "ranged damage": "Ranged%",
    "ranged_pct": "Ranged%",
    "attack speed": "Attack Speed",
    "attack_speed": "Attack Speed",
    "skill damage": "Skill Damage",
    "skill_damage": "Skill Damage",
    "skill cooldown": "Skill Cooldown",
    "skill_cooldown": "Skill Cooldown",
    "health": "Health%",
    "health%": "Health%",
    "health_pct": "Health%",
}

LEGACY_EQUIPMENT_SLOT_MAP: Dict[str, str] = {
    "EQUIP_HELMET": "Helmet",
    "EQUIP_BODY": "Body",
    "EQUIP_GLOVES": "Gloves",
    "EQUIP_NECKLACE": "Necklace",
    "EQUIP_RING": "Ring",
    "EQUIP_WEAPON": "Weapon",
    "EQUIP_SHOE": "Shoe",
    "EQUIP_BELT": "Belt",
}

LEGACY_PET_SLOT_MAP: Dict[str, str] = {
    "PET1": "Pet_1",
    "PET2": "Pet_2",
    "PET3": "Pet_3",
}

LEGACY_SKILL_SLOT_MAP: Dict[str, str] = {
    "S1": "Skill_1",
    "S2": "Skill_2",
    "S3": "Skill_3",
}


def _normalise_lookup(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_substat_key(label: str) -> Optional[str]:
    key = _normalise_lookup(label)
    if key in SUBSTAT_ALIASES:
        return SUBSTAT_ALIASES[key]
    compact = key.replace(" ", "")
    for alias, canonical in SUBSTAT_ALIASES.items():
        if compact == _normalise_lookup(alias).replace(" ", ""):
            return canonical
    return None


def canonical_rarity(value: str) -> Optional[str]:
    label = str(value or "").strip().title()
    return label if label in RARITIES else None


def canonical_age_int(value: str) -> Optional[int]:
    label = str(value or "").strip()
    if label in AGE_NAME_TO_INT:
        return AGE_NAME_TO_INT[label]
    compact = label.replace(" ", "").replace("_", "")
    for name, idx in AGE_NAME_TO_INT.items():
        if compact.lower() == name.replace(" ", "").replace("_", "").lower():
            return idx
    return None


def canonical_equipment_slot(value: str) -> Optional[str]:
    label = str(value or "").strip()
    if label in EQUIPMENT_SLOTS:
        return label
    return LEGACY_EQUIPMENT_SLOT_MAP.get(label.upper())


__all__ = [
    "EQUIPMENT_SLOTS",
    "SKILL_SLOTS",
    "PET_SLOTS",
    "MOUNT_SLOT",
    "RARITIES",
    "AGES",
    "AGE_INT_TO_NAME",
    "AGE_NAME_TO_INT",
    "EQUIPMENT_SLOT_TO_ICON_FOLDER",
    "SLOT_TO_JSON_TYPE",
    "SLOT_TO_TYPE_ID",
    "SUBSTAT_KEYS",
    "SUBSTAT_ALIASES",
    "LEGACY_EQUIPMENT_SLOT_MAP",
    "LEGACY_PET_SLOT_MAP",
    "LEGACY_SKILL_SLOT_MAP",
    "canonical_substat_key",
    "canonical_rarity",
    "canonical_age_int",
    "canonical_equipment_slot",
]
