"""
============================================================
  FORGE MASTER — Weapon attack-speed breakpoints

  Helpers around the pre-computed breakpoint JSON tables stored
  in ``helper/weapon atq speed/``. The actual file loading is
  handled by ``data.libraries`` so the codebase only ever
  has one chargeur JSON (V2 of the architecture plan).

  Public API:
      load_weapon_breakpoints(weapon_key)   -> dict | None
      weapon_key_from_name(age, item_name)  -> str
      list_known_weapons()                  -> list[str]
      get_current_cycle(bp)                 -> float | None
      get_current_double_cycle(bp)          -> float | None
      get_current_windup(bp)                -> float | None
      get_meta_windup(bp)                   -> dict | None
      get_next_breakpoint(bp, current_speed_pct, table=...) -> dict | None
      all_breakpoints(bp, table=...)        -> list[dict]
      clear_cache()                         -> None
============================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data import libraries as _libs


# Re-export so callers can keep using the same import surface.
load_weapon_breakpoints = _libs.load_weapon_breakpoints
list_known_weapons = _libs.list_known_weapon_breakpoints


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
    # Use the central loader to probe for the file's existence.
    if load_weapon_breakpoints(candidate) is not None:
        return candidate
    target = candidate.lower()
    for known in list_known_weapons():
        if known.lower() == target:
            return known
    return ""


def clear_cache():
    """Clear the centralised breakpoint cache."""
    _libs._bp_cache.clear()
