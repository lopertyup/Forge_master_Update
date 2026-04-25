"""
Equipped skills — skills.txt I/O (3 slots: S1, S2, S3).

skills.txt holds the CURRENT-LEVEL stats of the equipped skills, in the
same spirit as pets.txt and mount.txt.

Lv.1 reference values for swap simulations live in skills_library.txt
(see libraries.py).

Returned format (back-compat with the simulator):
    [(slot_label, data_dict), ...]
where data_dict has the keys expected by SkillInstance:
    name, type, damage, hits, cooldown,
    buff_duration, buff_atk, buff_hp,
    passive_damage, passive_hp,
    __name__, __rarity__, __level__
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from ..constants import SKILL_NUMERIC_KEYS, SKILLS_FILE
from ._io import _ensure_parent_dir

log = logging.getLogger(__name__)

SKILL_SLOTS = ("S1", "S2", "S3")


def empty_skill() -> Dict:
    """Build an empty skill slot (all-zero stats, no identity)."""
    out: Dict = {k: 0.0 for k in SKILL_NUMERIC_KEYS}
    out["type"] = ""
    out["name"] = ""
    return out


def _is_empty_skill(slot: Dict) -> bool:
    return not slot.get("__name__")


def load_skills() -> List[Tuple[str, Dict]]:
    """
    Load the 3 equipped skill slots from skills.txt.

    Returns a list of (slot_label, data_dict) for slots that actually
    hold a skill (empty slots are skipped). Order follows S1, S2, S3.
    """
    slots: Dict[str, Dict] = {s: empty_skill() for s in SKILL_SLOTS}
    if not os.path.isfile(SKILLS_FILE):
        return []

    current: Optional[str] = None
    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                tag = line[1:-1].strip()
                current = tag if tag in SKILL_SLOTS else None
                continue
            if current is None or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__", "type"):
                slots[current][key] = val
            elif key == "__level__":
                try:
                    slots[current][key] = int(val)
                except ValueError:
                    log.warning("skills.txt: invalid level for %s = %r",
                                current, val)
            else:
                try:
                    slots[current][key] = float(val)
                except ValueError:
                    log.warning("skills.txt: invalid value for %s.%s = %r",
                                current, key, val)

    # Mirror __name__ into "name" so the simulator's SkillInstance keeps
    # working without changes.
    for slot in slots.values():
        if slot.get("__name__"):
            slot["name"] = slot["__name__"]

    return [(s, slots[s]) for s in SKILL_SLOTS if not _is_empty_skill(slots[s])]


def load_skill_slots() -> Dict[str, Dict]:
    """Like load_skills() but returns the raw {slot: dict} mapping
    including empty slots — used by the UI."""
    slots: Dict[str, Dict] = {s: empty_skill() for s in SKILL_SLOTS}
    if not os.path.isfile(SKILLS_FILE):
        return slots
    for label, data in load_skills():
        slots[label] = data
    return slots


def save_skills(skills_by_slot: Dict[str, Dict]) -> None:
    """Persist the 3 skill slots to skills.txt."""
    _ensure_parent_dir(SKILLS_FILE)
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active skills (3 slots, editable by hand)\n")
        f.write("# ============================================================\n\n")
        for slot in SKILL_SLOTS:
            data = skills_by_slot.get(slot) or empty_skill()
            f.write(f"[{slot}]\n")
            if data.get("__name__"):
                f.write(f"{'__name__':14s} = {data['__name__']}\n")
            if data.get("__rarity__"):
                f.write(f"{'__rarity__':14s} = {data['__rarity__']}\n")
            if data.get("__level__"):
                f.write(f"{'__level__':14s} = {int(data['__level__'])}\n")
            if data.get("type"):
                f.write(f"{'type':14s} = {data['type']}\n")
            for k in SKILL_NUMERIC_KEYS:
                f.write(f"{k:14s} = {data.get(k, 0.0)}\n")
            f.write("\n")
