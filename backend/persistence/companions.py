"""
Pets and mount — pets.txt and mount.txt I/O.

Both files share the companion stats schema (COMPANION_STATS_KEYS) and
identity fields (__name__, __rarity__, __level__). Pets has three slots
(PET1/PET2/PET3); the mount is a single section.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from ..constants import COMPANION_STATS_KEYS, MOUNT_FILE, PETS_FILE
from ._io import _ensure_parent_dir, empty_companion

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  PETS
# ──────────────────────────────────────────────────────────────

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
            elif key == "__level__":
                try:
                    pets[current][key] = int(val)
                except ValueError:
                    log.warning("pets.txt: invalid level for %s = %r", current, val)
            else:
                try:
                    pets[current][key] = float(val)
                except ValueError:
                    log.warning("pets.txt: invalid value for %s.%s = %r", current, key, val)
    return pets


def save_pets(pets: Dict[str, Dict[str, float]]) -> None:
    _ensure_parent_dir(PETS_FILE)
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
            if pet.get("__level__"):
                f.write(f"{'__level__':20s} = {int(pet['__level__'])}\n")
            for k in COMPANION_STATS_KEYS:
                f.write(f"{k:20s} = {pet.get(k, 0.0)}\n")
            f.write("\n")


# ──────────────────────────────────────────────────────────────
#  MOUNT
# ──────────────────────────────────────────────────────────────

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
            elif key == "__level__":
                try:
                    mount[key] = int(val)
                except ValueError:
                    log.warning("mount.txt: invalid level = %r", val)
            else:
                try:
                    mount[key] = float(val)
                except ValueError:
                    log.warning("mount.txt: invalid value for %s = %r", key, val)
    return mount


def save_mount(mount: Dict[str, float]) -> None:
    _ensure_parent_dir(MOUNT_FILE)
    with open(MOUNT_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active mount (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[MOUNT]\n")
        if mount.get("__name__"):
            f.write(f"{'__name__':20s} = {mount['__name__']}\n")
        if mount.get("__rarity__"):
            f.write(f"{'__rarity__':20s} = {mount['__rarity__']}\n")
        if mount.get("__level__"):
            f.write(f"{'__level__':20s} = {int(mount['__level__'])}\n")
        for k in COMPANION_STATS_KEYS:
            f.write(f"{k:20s} = {mount.get(k, 0.0)}\n")
