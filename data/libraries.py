"""
============================================================
  FORGE MASTER — Game data libraries (lazy-loaded)

  Centralised lazy-loader for every JSON resource under
  ``data/``. Each library is cached after first read so the
  cost is paid at most once per process.

  Public API:

      load_libs() -> dict[str, dict]
          Returns every JSON the calculators need, keyed by
          short library name.

      get_lib(name: str) -> dict
          Convenience accessor returning a single library.

      DATA_DIR, ICONS_DIR
          Resolved Path objects pointing at the resource folders.

  Note on naming
  --------------
  This module used to live under the name "enemy_libraries.py"
  because it was first written for the opponent recompute
  pipeline. It is now used by the player pipeline too — the
  filename is kept for backwards compatibility but the public
  API is general-purpose.
============================================================
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonical import AGE_INT_TO_NAME, EQUIPMENT_SLOT_TO_ICON_FOLDER

log = logging.getLogger(__name__)


# ============================================================
#  Paths
# ============================================================

# Lives directly in the runtime ``data/`` folder at project root.
DATA_DIR  = Path(__file__).resolve().parent
ICONS_DIR = DATA_DIR / "icons"

# Backwards-compatible private alias used by the rest of this module.
_DATA_DIR = DATA_DIR


# ============================================================
#  Library file map
# ============================================================

_LIB_FILES: Dict[str, str] = {
    "item_balancing_library":   "ItemBalancingLibrary.json",
    "weapon_library":           "WeaponLibrary.json",
    "stat_config_library":      "StatConfigLibrary.json",
    "ascension_configs_library":"AscensionConfigsLibrary.json",

    # Pets
    "pet_library":              "PetLibrary.json",
    "pet_balancing_library":    "PetBalancingLibrary.json",
    "pet_upgrade_library":      "PetUpgradeLibrary.json",

    # Mounts
    "mount_library":            "MountLibrary.json",
    "mount_upgrade_library":    "MountUpgradeLibrary.json",

    # Skills
    "skill_library":            "SkillLibrary.json",
    "skill_passive_library":    "SkillPassiveLibrary.json",

    # Identification mappings (name <-> id)
    "auto_item_mapping":        "AutoItemMapping.json",
    "auto_pet_mapping":         "AutoPetMapping.json",
    "auto_mount_mapping":       "AutoMountMapping.json",
    "auto_skill_mapping":       "AutoSkillMapping.json",
}

_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        log.warning("libraries: %s missing", path.name)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("libraries: failed to load %s", path.name)
        return None


def load_libs() -> Dict[str, Any]:
    """Load every JSON the calculators need (cached after first call)."""
    if _cache:
        return _cache
    with _cache_lock:
        if _cache:
            return _cache
        loaded: Dict[str, Any] = {}
        for short_name, file_name in _LIB_FILES.items():
            data = _read_json(_DATA_DIR / file_name)
            loaded[short_name] = data or {}
        _cache.update(loaded)
        log.info("libraries: loaded %d libraries from %s",
                  len(_cache), _DATA_DIR)
        return _cache


def get_lib(name: str) -> Any:
    """Single-library accessor. Returns ``{}`` if unknown."""
    return load_libs().get(name, {})


def reset_cache() -> None:
    """Clear the module cache. Useful in tests."""
    with _cache_lock:
        _cache.clear()
    _bp_cache.clear()


# ============================================================
#  Weapon attack-speed breakpoints (helper/ folder)
# ============================================================
#
# The pre-computed breakpoint tables live in
# ``<project_root>/helper/weapon atq speed/`` (one JSON or TXT per
# weapon). They are read on demand and cached by weapon key so the
# breakpoints helper module ``backend.weapon.breakpoints`` does not
# need its own loader — V2 of the architecture plan.

_PROJECT_ROOT = DATA_DIR.parent
WEAPON_ATQ_SPEED_DIR = _PROJECT_ROOT / "helper" / "weapon atq speed"
_bp_cache: Dict[str, Optional[Any]] = {}


def _bp_candidate_paths(weapon_key: str):
    return [
        WEAPON_ATQ_SPEED_DIR / f"{weapon_key}.json",
        WEAPON_ATQ_SPEED_DIR / f"{weapon_key}.txt",
    ]


def load_weapon_breakpoints(weapon_key: str) -> Optional[Any]:
    """Return the pre-computed breakpoint table for one weapon key,
    or ``None`` when no file matches. Cached per key.
    """
    if not weapon_key:
        return None
    if weapon_key in _bp_cache:
        return _bp_cache[weapon_key]
    for path in _bp_candidate_paths(weapon_key):
        if path.exists():
            try:
                with path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                _bp_cache[weapon_key] = data
                return data
            except (OSError, json.JSONDecodeError):
                _bp_cache[weapon_key] = None
                return None
    _bp_cache[weapon_key] = None
    return None


def list_known_weapon_breakpoints() -> List[str]:
    if not WEAPON_ATQ_SPEED_DIR.exists():
        return []
    keys = set()
    for path in WEAPON_ATQ_SPEED_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in (".json", ".txt"):
            keys.add(path.stem)
    return sorted(keys)


# ============================================================
#  Icon path helpers
# ============================================================

AGE_INT_TO_FOLDER: Dict[int, str] = dict(AGE_INT_TO_NAME)
SLOT_TO_FOLDER: Dict[str, str] = dict(EQUIPMENT_SLOT_TO_ICON_FOLDER)


def equipment_icon_path(age: int, slot: str, sprite_name: str) -> Path:
    """Resolve an equipment icon path given its identity."""
    age_folder = AGE_INT_TO_FOLDER.get(age, str(age))
    slot_folder = SLOT_TO_FOLDER.get(slot, slot)
    return ICONS_DIR / "equipment" / age_folder / slot_folder / f"{sprite_name}.png"


def pet_icon_path(sprite_name: str) -> Path:
    return ICONS_DIR / "pets" / f"{sprite_name}.png"


def mount_icon_path(sprite_name: str) -> Path:
    return ICONS_DIR / "mount" / f"{sprite_name}.png"


def skill_icon_path(sprite_name: str) -> Path:
    return ICONS_DIR / "skills" / f"{sprite_name}.png"
