"""Compatibility shim for player equipment stored in profile_store."""

from __future__ import annotations

import warnings
from typing import Dict

from data.canonical import EQUIPMENT_SLOTS as CANONICAL_EQUIPMENT_SLOTS, LEGACY_EQUIPMENT_SLOT_MAP

from .profile_store import store
from .profile_store.codecs import normalise_equipment_slot
from .profile_store.schema import empty_equipment_slot as _canonical_empty_slot

_CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_EQUIPMENT_SLOT_MAP.items()}


def _warn(name: str) -> None:
    warnings.warn(
        f"backend.persistence.equipment.{name} is deprecated; use profile_store.store",
        DeprecationWarning,
        stacklevel=2,
    )


def empty_equipment_slot() -> Dict[str, object]:
    slot = _canonical_empty_slot()
    slot.pop("substats", None)
    return slot


def empty_equipment() -> Dict[str, Dict[str, object]]:
    return {
        _CANONICAL_TO_LEGACY[slot]: empty_equipment_slot()
        for slot in CANONICAL_EQUIPMENT_SLOTS
    }


def load_equipment() -> Dict[str, Dict[str, object]]:
    _warn("load_equipment")
    profile = store.load_profile()
    return {
        _CANONICAL_TO_LEGACY[slot]: _legacy_slot(data)
        for slot, data in (profile.get("equipment") or {}).items()
        if slot in _CANONICAL_TO_LEGACY
    }


def save_equipment(equipment: Dict[str, Dict[str, object]]) -> None:
    _warn("save_equipment")
    profile = store.load_profile()
    for raw_slot, value in (equipment or {}).items():
        slot = LEGACY_EQUIPMENT_SLOT_MAP.get(raw_slot, raw_slot)
        if slot in CANONICAL_EQUIPMENT_SLOTS:
            profile = store.set_equipment_slot(profile, slot, value or {})
    store.save_profile(profile)


def _legacy_slot(data: Dict[str, object]) -> Dict[str, object]:
    out = dict(normalise_equipment_slot(data))
    for key, value in (out.pop("substats", {}) or {}).items():
        out[key] = value
    return out

