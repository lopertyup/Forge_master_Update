"""
Level-1 reference libraries — pets_library.txt, mount_library.txt,
skills_library.txt.

Pets and mount libraries share a tiny 3-field schema (rarity, hp_flat,
damage_flat) handled by `_load_library` / `_save_library`. The skills
library has its own richer schema with SKILL_NUMERIC_KEYS + rarity + type.

The index key (e.g. "Treant") is case-sensitive on disk but compared
case-insensitively by the controller.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from ..constants import (
    MOUNT_LIBRARY_FILE,
    PETS_LIBRARY_FILE,
    SKILL_NUMERIC_KEYS,
    SKILLS_LIBRARY_FILE,
)
from ._io import _ensure_parent_dir

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  PETS + MOUNT libraries (shared 3-field schema)
# ──────────────────────────────────────────────────────────────

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
    _ensure_parent_dir(path)
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


# ──────────────────────────────────────────────────────────────
#  SKILLS library — richer schema
# ──────────────────────────────────────────────────────────────

_SKILL_LIB_STRING_KEYS = ("rarity", "type")


def load_skills_library() -> Dict[str, Dict]:
    """Load skills_library.txt — Lv.1 reference for each known skill."""
    if not os.path.isfile(SKILLS_LIBRARY_FILE):
        return {}

    library: Dict[str, Dict] = {}
    current_name: Optional[str] = None
    current: Dict = {}

    def _empty_entry() -> Dict:
        entry = {k: 0.0 for k in SKILL_NUMERIC_KEYS}
        entry["rarity"] = "common"
        entry["type"]   = "damage"
        return entry

    with open(SKILLS_LIBRARY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    library[current_name] = current
                current_name = line[1:-1].strip()
                current = _empty_entry()
            elif current_name and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key in _SKILL_LIB_STRING_KEYS:
                    current[key] = val.lower()
                elif key in SKILL_NUMERIC_KEYS:
                    try:
                        current[key] = float(val)
                    except ValueError:
                        log.warning("skills_library.txt: invalid value for [%s].%s = %r",
                                    current_name, key, val)
        if current_name:
            library[current_name] = current
    return library


def save_skills_library(library: Dict[str, Dict]) -> None:
    """Persist skills_library.txt, sorted alphabetically (case-insensitive)."""
    _ensure_parent_dir(SKILLS_LIBRARY_FILE)
    with open(SKILLS_LIBRARY_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Skills library (level 1)\n")
        f.write("# Reference stats at level 1, indexed by name.\n")
        f.write("# ============================================================\n\n")
        for name in sorted(library.keys(), key=str.lower):
            entry = library[name]
            f.write(f"[{name}]\n")
            f.write(f"{'rarity':14s} = {entry.get('rarity', 'common')}\n")
            f.write(f"{'type':14s} = {entry.get('type', 'damage')}\n")
            for k in SKILL_NUMERIC_KEYS:
                f.write(f"{k:14s} = {entry.get(k, 0.0)}\n")
            f.write("\n")
