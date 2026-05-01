"""One-shot migration from legacy split player files to profile schema v2."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from backend.constants import EQUIPMENT_FILE, MOUNT_FILE, PETS_FILE, PROFILE_FILE, SKILLS_FILE
from data.canonical import (
    LEGACY_EQUIPMENT_SLOT_MAP,
    LEGACY_PET_SLOT_MAP,
    LEGACY_SKILL_SLOT_MAP,
    MOUNT_SLOT,
)

from .profile_store import codecs
from .profile_store.schema import empty_profile

log = logging.getLogger(__name__)

LEGACY_FILES = (
    Path(PROFILE_FILE),
    Path(EQUIPMENT_FILE),
    Path(PETS_FILE),
    Path(MOUNT_FILE),
    Path(SKILLS_FILE),
)


def migrate_legacy_profile_once() -> bool:
    from .profile_store.store import PROFILE_PATH, save_profile

    if PROFILE_PATH.is_file() and codecs.has_schema_v2(PROFILE_PATH.read_text(encoding="utf-8")):
        return False

    profile = empty_profile()
    _merge_base_profile(profile, Path(PROFILE_FILE))
    _merge_equipment(profile, Path(EQUIPMENT_FILE))
    _merge_pets(profile, Path(PETS_FILE))
    _merge_mount(profile, Path(MOUNT_FILE))
    _merge_skills(profile, Path(SKILLS_FILE))

    if not any(path.is_file() for path in LEGACY_FILES):
        return False

    save_profile(profile)
    for path in LEGACY_FILES:
        if path.is_file():
            _backup_legacy(path)
    log.info("migrated legacy player persistence to %s", PROFILE_PATH)
    return True


def _merge_base_profile(profile: Dict, path: Path) -> None:
    for section, values in _read_sections(path).items():
        if section != "PLAYER":
            continue
        for key, value in values.items():
            profile["base_profile"][key] = value if key == "attack_type" else _float(value)


def _merge_equipment(profile: Dict, path: Path) -> None:
    for section, values in _read_sections(path).items():
        slot = LEGACY_EQUIPMENT_SLOT_MAP.get(section, section)
        if slot in profile["equipment"]:
            profile["equipment"][slot] = codecs.normalise_equipment_slot(values)


def _merge_pets(profile: Dict, path: Path) -> None:
    for section, values in _read_sections(path).items():
        slot = LEGACY_PET_SLOT_MAP.get(section, section)
        if slot in profile["pets"]:
            profile["pets"][slot] = codecs.normalise_companion_slot(values)


def _merge_mount(profile: Dict, path: Path) -> None:
    sections = _read_sections(path)
    values = sections.get("MOUNT") or sections.get(MOUNT_SLOT)
    if values is not None:
        profile["mount"][MOUNT_SLOT] = codecs.normalise_companion_slot(values)


def _merge_skills(profile: Dict, path: Path) -> None:
    for section, values in _read_sections(path).items():
        slot = LEGACY_SKILL_SLOT_MAP.get(section, section)
        if slot in profile["skills"]:
            profile["skills"][slot] = codecs.normalise_skill_slot(values)


def _read_sections(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.is_file():
        return {}
    sections: Dict[str, Dict[str, object]] = {}
    current: Optional[str] = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current and "=" in line:
            key, value = [part.strip() for part in line.split("=", 1)]
            sections[current][key] = _coerce(value)
    return sections


def _coerce(value: str) -> object:
    try:
        as_float = float(value)
    except ValueError:
        return value
    if as_float.is_integer():
        return int(as_float)
    return as_float


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _backup_legacy(path: Path) -> None:
    target = path.with_name(path.name + ".legacy.bak")
    if not target.exists():
        path.rename(target)
        return
    index = 1
    while True:
        candidate = path.with_name(f"{path.name}.legacy.{index}.bak")
        if not candidate.exists():
            path.rename(candidate)
            return
        index += 1

