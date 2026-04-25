"""
============================================================
  FORGE MASTER — Weapon attack-speed breakpoints
  Loader + helpers around the pre-computed JSON tables
  stored in ``helper/weapon atq speed/``.
============================================================
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


_ROOT = Path(__file__).resolve().parent.parent
WEAPON_ATQ_SPEED_DIR = _ROOT / "helper" / "weapon atq speed"


def _candidate_paths(weapon_key):
    return [
        WEAPON_ATQ_SPEED_DIR / f"{weapon_key}.json",
        WEAPON_ATQ_SPEED_DIR / f"{weapon_key}.txt",
    ]


@lru_cache(maxsize=None)
def load_weapon_breakpoints(weapon_key):
    if not weapon_key:
        return None
    for path in _candidate_paths(weapon_key):
        if path.exists():
            try:
                with path.open(encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError):
                return None
    return None


def list_known_weapons():
    if not WEAPON_ATQ_SPEED_DIR.exists():
        return []
    keys = set()
    for path in WEAPON_ATQ_SPEED_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in (".json", ".txt"):
            keys.add(path.stem)
    return sorted(keys)


def _table(bp, name):
    if not bp:
        return []
    rows = bp.get(name)
    return rows if isinstance(rows, list) else []


def get_current_cycle(bp):
    for row in _table(bp, "primary_weapon_cycle"):
        if row.get("status") == "CURRENT":
            t = row.get("time")
            return float(t) if t is not None else None
    return None


def get_current_double_cycle(bp):
    for row in _table(bp, "double_attack_cycle"):
        if row.get("status") == "CURRENT":
            t = row.get("time")
            return float(t) if t is not None else None
    return None


def get_current_windup(bp):
    for row in _table(bp, "rhythmic_windup_steps"):
        if row.get("status") == "CURRENT":
            t = row.get("time")
            return float(t) if t is not None else None
    return None


def get_meta_windup(bp):
    for row in _table(bp, "rhythmic_windup_steps"):
        if row.get("status") == "META":
            return row
    return None


def get_next_breakpoint(bp, current_speed_pct, table="primary_weapon_cycle"):
    candidates = []
    for row in _table(bp, table):
        if row.get("status") in ("REACHED", "CURRENT"):
            continue
        req = row.get("req_speed")
        if req is None:
            continue
        try:
            req_f = float(req)
        except (TypeError, ValueError):
            continue
        if req_f > current_speed_pct:
            candidates.append((req_f, row))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def all_breakpoints(bp, table="primary_weapon_cycle"):
    return [dict(r) for r in _table(bp, table)]


AGE_FILE_NAMES = {
    0:     "Primitive",
    1:     "Medieval",
    2:     "Earlymodern",
    3:     "Modern",
    4:     "Space",
    5:     "Interstellar",
    6:     "Multiverse",
    7:     "Quantum",
    8:     "Underworld",
    9:     "Divine",
    10000: "Divine",
}


def _normalise_item_name(item_name):
    if not item_name:
        return ""
    txt = item_name.replace("&", "and")
    txt = "".join(ch for ch in txt if ch.isalnum())
    if not txt:
        return ""
    return txt[0].upper() + txt[1:].lower()


def weapon_key_from_name(age, item_name):
    age_name = AGE_FILE_NAMES.get(age, "")
    clean = _normalise_item_name(item_name)
    if not age_name or not clean:
        return ""
    candidate = f"{age_name}Weapon{clean}"
    for path in _candidate_paths(candidate):
        if path.exists():
            return candidate
    target = candidate.lower()
    for known in list_known_weapons():
        if known.lower() == target:
            return known
    return ""


def clear_cache():
    load_weapon_breakpoints.cache_clear()
