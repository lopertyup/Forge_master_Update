"""Centralized persistence API for the canonical player profile."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Dict

from data.canonical import EQUIPMENT_SLOTS, MOUNT_SLOT, PET_SLOTS, SKILL_SLOTS, SUBSTAT_KEYS

from .._io import _ensure_parent_dir
from . import codecs
from .schema import empty_profile as _empty_profile

STORE_DIR = Path(__file__).resolve().parent
PROFILE_PATH = STORE_DIR / "profile.txt"


def empty_profile() -> Dict:
    return _empty_profile()


def load_profile() -> Dict:
    if not PROFILE_PATH.is_file():
        from backend.persistence._migrate_profile import migrate_legacy_profile_once

        migrate_legacy_profile_once()
    if not PROFILE_PATH.is_file():
        profile = empty_profile()
        save_profile(profile)
        return profile
    return codecs.loads_profile(PROFILE_PATH.read_text(encoding="utf-8"))


def save_profile(profile: Dict) -> None:
    profile = codecs.normalise_profile(profile)
    profile["substats_total"] = compute_substats_total(profile)
    _ensure_parent_dir(os.fspath(PROFILE_PATH))
    PROFILE_PATH.write_text(codecs.dumps_profile(profile), encoding="utf-8")


def compute_substats_total(profile: Dict) -> Dict[str, float]:
    total = {key: 0.0 for key in SUBSTAT_KEYS}
    for section in ("equipment", "pets"):
        for entry in (profile.get(section) or {}).values():
            _add_substats(total, entry)
    for entry in (profile.get("mount") or {}).values():
        _add_substats(total, entry)
    return total


def set_equipment_slot(profile: Dict, slot: str, value: Dict) -> Dict:
    if slot not in EQUIPMENT_SLOTS:
        raise KeyError(f"unknown equipment slot: {slot!r}")
    out = deepcopy(profile)
    out.setdefault("equipment", {})[slot] = codecs.normalise_equipment_slot(value)
    out["substats_total"] = compute_substats_total(out)
    return out


def set_pet_slot(profile: Dict, slot: str, value: Dict) -> Dict:
    if slot not in PET_SLOTS:
        raise KeyError(f"unknown pet slot: {slot!r}")
    out = deepcopy(profile)
    out.setdefault("pets", {})[slot] = codecs.normalise_companion_slot(value)
    out["substats_total"] = compute_substats_total(out)
    return out


def set_mount(profile: Dict, value: Dict) -> Dict:
    out = deepcopy(profile)
    out.setdefault("mount", {})[MOUNT_SLOT] = codecs.normalise_companion_slot(value)
    out["substats_total"] = compute_substats_total(out)
    return out


def set_skill_slot(profile: Dict, slot: str, value: Dict) -> Dict:
    if slot not in SKILL_SLOTS:
        raise KeyError(f"unknown skill slot: {slot!r}")
    out = deepcopy(profile)
    out.setdefault("skills", {})[slot] = codecs.normalise_skill_slot(value)
    out["substats_total"] = compute_substats_total(out)
    return out


def _add_substats(total: Dict[str, float], entry: Dict) -> None:
    for key, value in (entry.get("substats") or {}).items():
        total[key] = total.get(key, 0.0) + float(value or 0.0)

