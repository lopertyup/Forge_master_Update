"""Compatibility shim for equipped skills stored in profile_store."""

from __future__ import annotations

import warnings
from typing import Dict, List, Tuple

from data.canonical import LEGACY_SKILL_SLOT_MAP, SKILL_SLOTS as CANONICAL_SKILL_SLOTS

from .profile_store import store
from .profile_store.codecs import normalise_skill_slot

SKILL_SLOTS = ("S1", "S2", "S3")
_CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_SKILL_SLOT_MAP.items()}


def _warn(name: str) -> None:
    warnings.warn(
        f"backend.persistence.skills.{name} is deprecated; use profile_store.store",
        DeprecationWarning,
        stacklevel=2,
    )


def empty_skill() -> Dict:
    return {
        "type": "",
        "name": "",
        "damage": 0.0,
        "hits": 0.0,
        "cooldown": 0.0,
        "buff_duration": 0.0,
        "buff_atk": 0.0,
        "buff_hp": 0.0,
        "passive_damage": 0.0,
        "passive_hp": 0.0,
    }


def _is_empty_skill(slot: Dict) -> bool:
    return not slot.get("__name__")


def load_skills() -> List[Tuple[str, Dict]]:
    _warn("load_skills")
    slots = load_skill_slots()
    return [(slot, slots[slot]) for slot in SKILL_SLOTS if not _is_empty_skill(slots[slot])]


def load_skill_slots() -> Dict[str, Dict]:
    _warn("load_skill_slots")
    profile = store.load_profile()
    out = {slot: empty_skill() for slot in SKILL_SLOTS}
    for canonical, data in (profile.get("skills") or {}).items():
        legacy = _CANONICAL_TO_LEGACY.get(canonical)
        if legacy:
            out[legacy] = _legacy_skill(data)
    return out


def save_skills(skills_by_slot: Dict[str, Dict]) -> None:
    _warn("save_skills")
    profile = store.load_profile()
    for raw_slot, value in (skills_by_slot or {}).items():
        slot = LEGACY_SKILL_SLOT_MAP.get(raw_slot, raw_slot)
        if slot in CANONICAL_SKILL_SLOTS:
            profile = store.set_skill_slot(profile, slot, value or {})
    store.save_profile(profile)


def _legacy_skill(data: Dict[str, object]) -> Dict:
    slot = normalise_skill_slot(data)
    out = empty_skill()
    out.update({
        "__name__": slot.get("__name__", ""),
        "__rarity__": slot.get("__rarity__", ""),
        "__level__": slot.get("__level__", 0),
        "name": slot.get("__name__", ""),
        "type": slot.get("type", ""),
        "passive_damage": float(slot.get("damage_flat", 0.0) or 0.0),
        "passive_hp": float(slot.get("hp_flat", 0.0) or 0.0),
    })
    for key in ("damage", "hits", "cooldown", "buff_duration", "buff_atk", "buff_hp"):
        if key in slot:
            out[key] = float(slot.get(key, 0.0) or 0.0)
    return out

