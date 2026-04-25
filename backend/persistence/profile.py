"""
Player profile — profile.txt I/O.

NOTE: equipped skills are NOT stored inline in profile.txt anymore.
They live in their own file (skills.txt, 3 slots) — same pattern as
pets.txt and mount.txt. Old profiles with a `skills =` line are
silently tolerated (the line is ignored).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from ..constants import PROFILE_FILE, STATS_KEYS
from ._io import _ensure_parent_dir
from .skills import load_skills

log = logging.getLogger(__name__)


def save_profile(player: Dict, skills: Optional[List[Tuple[str, Dict]]] = None) -> None:
    """
    `skills` is accepted for back-compat but no longer written: equipped
    skills are persisted by save_skills() into skills.txt.
    """
    _ensure_parent_dir(PROFILE_FILE)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Player profile (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[PLAYER]\n")
        for k in STATS_KEYS:
            f.write(f"{k:20s} = {player.get(k, 0.0)}\n")
        f.write(f"{'attack_type':20s} = {player.get('attack_type', 'melee')}\n\n")


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
            # Legacy field — silently ignored. Equipped skills now live
            # in skills.txt and are loaded by load_skills().
            continue
        else:
            try:
                stats[key] = float(val)
            except ValueError:
                log.warning("profile.txt: invalid value for %s = %r", key, val)
    return stats if stats else None


def load_profile() -> Tuple[Optional[Dict], List[Tuple[str, Dict]]]:
    """
    Returns (profile, equipped_skills).
    `equipped_skills` is loaded from skills.txt (the new 3-slot format).
    """
    if not os.path.isfile(PROFILE_FILE):
        return None, []

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    profile: Optional[Dict] = None
    for i, line in enumerate(lines):
        if line.strip() == "[PLAYER]":
            profile = _read_section(lines, i + 1)
            break

    if profile is None:
        return None, []

    return profile, load_skills()
