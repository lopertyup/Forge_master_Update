"""
============================================================
  FORGE MASTER — Persistence (file read / write)
  Read and write profile.txt, pets.txt, mount.txt, skills.txt.
============================================================
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from .constants import (
    COMPANION_STATS_KEYS,
    MOUNT_FILE,
    MOUNT_LIBRARY_FILE,
    PETS_FILE,
    PETS_LIBRARY_FILE,
    PROFILE_FILE,
    SKILLS_FILE,
    STATS_KEYS,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  PROFILE + ACTIVE SKILLS
# ════════════════════════════════════════════════════════════

def save_profile(player: Dict, skills: Optional[List[Tuple[str, Dict]]] = None) -> None:
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Player profile (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[PLAYER]\n")
        for k in STATS_KEYS:
            f.write(f"{k:20s} = {player.get(k, 0.0)}\n")
        f.write(f"{'attack_type':20s} = {player.get('attack_type', 'melee')}\n")
        codes = ",".join(c for c, _ in (skills or []))
        f.write(f"{'skills':20s} = {codes}\n\n")


def _read_section(lines: List[str], start: int) -> Optional[Dict]:
    """
    Read a key=value section until the next [...] header or end of file.
    `start` must point to the first line AFTER the [SECTION] header.
    """
    stats: Dict = {}
    for line in lines[start:]:
        line = line.strip()
        if line.startswith("["):
            break
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if key == "attack_type":
            stats[key] = val
        elif key == "skills":
            # Handled separately by load_profile (not a numeric stat).
            continue
        else:
            try:
                stats[key] = float(val)
            except ValueError:
                log.warning("profile.txt: invalid value for %s = %r", key, val)
    return stats if stats else None


def load_profile() -> Tuple[Optional[Dict], List[Tuple[str, Dict]]]:
    if not os.path.isfile(PROFILE_FILE):
        return None, []

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    profile: Optional[Dict] = None
    skills_codes = ""
    for i, line in enumerate(lines):
        if line.strip() == "[PLAYER]":
            profile = _read_section(lines, i + 1)
        elif "skills" in line and "=" in line:
            skills_codes = line.split("=", 1)[1].strip()

    if profile is None:
        return None, []

    all_skills = load_skills()
    skills: List[Tuple[str, Dict]] = []
    if skills_codes:
        for code in skills_codes.split(","):
            code = code.strip()
            if code and code in all_skills:
                skills.append((code, all_skills[code]))
    return profile, skills


# ════════════════════════════════════════════════════════════
#  SKILLS (catalog)
# ════════════════════════════════════════════════════════════

def load_skills() -> Dict[str, Dict]:
    if not os.path.isfile(SKILLS_FILE):
        return {}

    skills: Dict[str, Dict] = {}
    current_code: Optional[str] = None
    current: Dict = {}

    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_code:
                    skills[current_code] = current
                current_code = line[1:-1].lower()
                current = {}
            elif "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                try:
                    current[key] = float(val)
                except ValueError:
                    current[key] = val
        if current_code:
            skills[current_code] = current
    return skills


# ════════════════════════════════════════════════════════════
#  PETS
# ════════════════════════════════════════════════════════════

def empty_companion() -> Dict[str, float]:
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


# Back-compat aliases
pet_vide   = empty_companion
mount_vide = empty_companion


def load_pets() -> Dict[str, Dict[str, float]]:
    pets = {name: empty_companion() for name in ("PET1", "PET2", "PET3")}
    if not os.path.isfile(PETS_FILE):
        return pets

    with open(PETS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current: Optional[str] = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line in ("[PET1]", "[PET2]", "[PET3]"):
            current = line[1:-1]
        elif current and "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__"):
                pets[current][key] = val
            else:
                try:
                    pets[current][key] = float(val)
                except ValueError:
                    log.warning("pets.txt: invalid value for %s.%s = %r", current, key, val)
    return pets


def save_pets(pets: Dict[str, Dict[str, float]]) -> None:
    with open(PETS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active pets (editable by hand)\n")
        f.write("# ============================================================\n\n")
        for name in ("PET1", "PET2", "PET3"):
            pet = pets.get(name, empty_companion())
            f.write(f"[{name}]\n")
            # Identity (name/rarity) at the top of the section if set
            if pet.get("__name__"):
                f.write(f"{'__name__':20s} = {pet['__name__']}\n")
            if pet.get("__rarity__"):
                f.write(f"{'__rarity__':20s} = {pet['__rarity__']}\n")
            for k in COMPANION_STATS_KEYS:
                f.write(f"{k:20s} = {pet.get(k, 0.0)}\n")
            f.write("\n")


# ════════════════════════════════════════════════════════════
#  MOUNT
# ════════════════════════════════════════════════════════════

def load_mount() -> Dict[str, float]:
    mount = empty_companion()
    if not os.path.isfile(MOUNT_FILE):
        return mount

    with open(MOUNT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__"):
                mount[key] = val
            else:
                try:
                    mount[key] = float(val)
                except ValueError:
                    log.warning("mount.txt: invalid value for %s = %r", key, val)
    return mount


def save_mount(mount: Dict[str, float]) -> None:
    with open(MOUNT_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active mount (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[MOUNT]\n")
        if mount.get("__name__"):
            f.write(f"{'__name__':20s} = {mount['__name__']}\n")
        if mount.get("__rarity__"):
            f.write(f"{'__rarity__':20s} = {mount['__rarity__']}\n")
        for k in COMPANION_STATS_KEYS:
            f.write(f"{k:20s} = {mount.get(k, 0.0)}\n")


# ════════════════════════════════════════════════════════════
#  LIBRARIES (pets + mount at level 1)
# ════════════════════════════════════════════════════════════
#
#  Identical format for both files:
#
#      # comment
#      [Treant]
#      rarity      = ultimate
#      hp_flat     = 10200000.0
#      damage_flat = 427000.0
#
#      [Phoenix]
#      rarity      = legendary
#      hp_flat     = 8500000.0
#      damage_flat = 380000.0
#
#  The index key (e.g. "Treant") is case-sensitive on disk
#  but compared case-insensitively by the controller.
# ════════════════════════════════════════════════════════════

_LIBRARY_KEYS = ("rarity", "hp_flat", "damage_flat")


def _load_library(path: str) -> Dict[str, Dict]:
    if not os.path.isfile(path):
        return {}

    library: Dict[str, Dict] = {}
    current_name: Optional[str] = None
    current: Dict = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    library[current_name] = current
                current_name = line[1:-1].strip()
                current = {"rarity": "common", "hp_flat": 0.0, "damage_flat": 0.0}
            elif current_name and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key == "rarity":
                    current[key] = val.lower()
                elif key in ("hp_flat", "damage_flat"):
                    try:
                        current[key] = float(val)
                    except ValueError:
                        log.warning("%s: invalid value for [%s].%s = %r",
                                    path, current_name, key, val)
        if current_name:
            library[current_name] = current
    return library


def _save_library(path: str, library: Dict[str, Dict], title: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write(f"# FORGE MASTER — {title}\n")
        f.write("# Reference stats at level 1, indexed by name.\n")
        f.write("# ============================================================\n\n")
        for name in sorted(library.keys(), key=str.lower):
            entry = library[name]
            f.write(f"[{name}]\n")
            f.write(f"{'rarity':12s} = {entry.get('rarity', 'common')}\n")
            f.write(f"{'hp_flat':12s} = {entry.get('hp_flat', 0.0)}\n")
            f.write(f"{'damage_flat':12s} = {entry.get('damage_flat', 0.0)}\n\n")


def load_pets_library() -> Dict[str, Dict]:
    return _load_library(PETS_LIBRARY_FILE)


def save_pets_library(library: Dict[str, Dict]) -> None:
    _save_library(PETS_LIBRARY_FILE, library, "Pets library (level 1)")


def load_mount_library() -> Dict[str, Dict]:
    return _load_library(MOUNT_LIBRARY_FILE)


def save_mount_library(library: Dict[str, Dict]) -> None:
    _save_library(MOUNT_LIBRARY_FILE, library, "Mounts library (level 1)")
