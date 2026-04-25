"""
============================================================
  FORGE MASTER -- Weapon projectile travel time
  Loader + helpers around ProjectilesLibrary.json and the
  per-name fallback table from the chantier doc.
============================================================
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_DATA_PATH = _ROOT / "data" / "ProjectilesLibrary.json"


# Range constants -- AttackRange in WeaponLibrary is either
# 0.30 (melee, 36 weapons) or 7.00 (ranged, 27 weapons).
# These are the in-game weapon "leash" values.
RANGE_RANGED = 7.0
RANGE_MELEE  = 0.3

# Effective travel distance in PvP. Both fighters close in until
# they fire, so the actual gap projectiles cross is far below the
# weapon's nominal AttackRange. Real-combat measurement on a Speed
# 20 weapon (Blackgun): impact lands ~0.05-0.10 s after the shot,
# which puts the effective distance at roughly 1.0-2.0 units. We
# default to 1.5 -- to be revisited as more capture data comes in.
PVP_COMBAT_DISTANCE = 1.5


# Hardcoded fallback used when ProjectilesLibrary.json cannot be
# read. Keyed by the canonical helper-folder weapon name (first
# letter upper, rest lower, & -> "and"). See the chantier doc.
PROJECTILE_SPEEDS = {
    "Blowgun": 20, "Rock": 15, "Slinger": 20, "Bow": 20,
    "Tomahawk": 15, "Crossbow": 25, "Musket": 20, "Dualpistol": 20,
    "Ak": 20, "M4": 20, "Sniper": 20, "Uzi": 20, "Blaster": 25,
    "Spacegun": 20, "Spacepistol": 25, "Ionicblaster": 20,
    "Plasmarifle": 25, "Raygun": 25, "Simulatedbow": 25,
    "Virtualgun": 20, "Blackbow": 20, "Blackgun": 20,
    "Quantumstaff": 30, "Abyssalfork": 30, "Infernaltrident": 30,
    "Staff": 30, "Staffofwisdom": 20,
}


@lru_cache(maxsize=None)
def _load_projectile_lib():
    """Parse ProjectilesLibrary.json once. Returns {} on failure."""
    if not _DATA_PATH.exists():
        return {}
    try:
        with _DATA_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def get_projectile_speed_by_id(projectile_id, lib=None):
    """Look up a projectile speed via its numeric ProjectileId.

    Returns None if the id cannot be resolved. The ``lib`` arg
    accepts a pre-loaded ProjectilesLibrary dict (for tests); when
    omitted the on-disk JSON is used.
    """
    if projectile_id is None:
        return None
    if lib is None:
        lib = _load_projectile_lib()
    if not lib:
        return None
    entry = lib.get(str(projectile_id))
    if entry is None and isinstance(projectile_id, int):
        # Some pipelines key by int instead of str.
        entry = lib.get(projectile_id)
    if not entry:
        return None
    speed = entry.get("Speed")
    return float(speed) if speed else None


def _normalise_weapon_name(name):
    """Same casing rule as weapon_breakpoints._normalise_item_name."""
    if not name:
        return ""
    txt = name.replace("&", "and")
    txt = "".join(ch for ch in txt if ch.isalnum())
    if not txt:
        return ""
    return txt[0].upper() + txt[1:].lower()


def get_projectile_speed(weapon_name=None, projectile_id=None, lib=None):
    """Resolve a projectile speed for a ranged weapon.

    Priority:
      1. ProjectilesLibrary.json keyed by ``projectile_id``
      2. Hardcoded fallback table keyed by ``weapon_name``
    Returns None when nothing matches (caller should treat as
    melee / no travel time).
    """
    if projectile_id is not None:
        speed = get_projectile_speed_by_id(projectile_id, lib=lib)
        if speed is not None and speed > 0:
            return speed
    if weapon_name:
        clean = _normalise_weapon_name(weapon_name)
        for k, v in PROJECTILE_SPEEDS.items():
            if k.lower() == clean.lower():
                return float(v)
    return None


def get_travel_time(weapon_name=None, projectile_id=None, lib=None,
                    weapon_range=None):
    """Compute the in-flight delay for one projectile.

    The distance crossed by a PvP projectile is NOT the weapon's
    nominal AttackRange (7.0 units) -- in real combat the fighters
    close in before firing, so the effective gap is closer to
    PVP_COMBAT_DISTANCE (~1.5 units). ``weapon_range`` is used only to decide whether the weapon is melee (range below
    the ranged threshold => 0 s travel time); ranged weapons all
    use PVP_COMBAT_DISTANCE.
    """
    rng = float(weapon_range) if weapon_range is not None else RANGE_RANGED
    if rng < (RANGE_RANGED * 0.5):     # melee weapon, no travel time
        return 0.0
    speed = get_projectile_speed(weapon_name, projectile_id, lib=lib)
    if speed is None or speed <= 0:
        return 0.0
    return PVP_COMBAT_DISTANCE / speed


def clear_cache():
    """Clear the in-memory ProjectilesLibrary cache (tests only)."""
    _load_projectile_lib.cache_clear()
