"""Compatibility shims for pets and mount stored in profile_store."""

from __future__ import annotations

import warnings
from typing import Dict

from data.canonical import LEGACY_PET_SLOT_MAP, MOUNT_SLOT, PET_SLOTS

from ._io import empty_companion
from .profile_store import store
from .profile_store.codecs import normalise_companion_slot

_CANONICAL_TO_LEGACY_PET = {value: key for key, value in LEGACY_PET_SLOT_MAP.items()}


def _warn(name: str) -> None:
    warnings.warn(
        f"backend.persistence.companions.{name} is deprecated; use profile_store.store",
        DeprecationWarning,
        stacklevel=2,
    )


def load_pets() -> Dict[str, Dict[str, float]]:
    _warn("load_pets")
    profile = store.load_profile()
    pets = {legacy: empty_companion() for legacy in _CANONICAL_TO_LEGACY_PET.values()}
    for slot, data in (profile.get("pets") or {}).items():
        legacy = _CANONICAL_TO_LEGACY_PET.get(slot)
        if legacy:
            pets[legacy] = _legacy_companion(data)
    return pets


def save_pets(pets: Dict[str, Dict[str, float]]) -> None:
    _warn("save_pets")
    profile = store.load_profile()
    for raw_slot, value in (pets or {}).items():
        slot = LEGACY_PET_SLOT_MAP.get(raw_slot, raw_slot)
        if slot in PET_SLOTS:
            profile = store.set_pet_slot(profile, slot, value or {})
    store.save_profile(profile)


def load_mount() -> Dict[str, float]:
    _warn("load_mount")
    profile = store.load_profile()
    return _legacy_companion((profile.get("mount") or {}).get(MOUNT_SLOT) or {})


def save_mount(mount: Dict[str, float]) -> None:
    _warn("save_mount")
    profile = store.set_mount(store.load_profile(), mount or {})
    store.save_profile(profile)


def _legacy_companion(data: Dict[str, object]) -> Dict[str, float]:
    out = dict(normalise_companion_slot(data))
    for key, value in (out.pop("substats", {}) or {}).items():
        out[key] = value
    return out

