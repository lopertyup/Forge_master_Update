"""
============================================================
  FORGE MASTER — Enemy stat calculation libraries

  Lazy-loaded JSON resources used to recompute an opponent's
  HP/Dmg from his identified gear. The reference data lives
  under ``data/`` at the project root (game-exported JSONs +
  sprite atlases). All loads are memoised at module level so
  the cost is paid at most once per process.

  Public API:

      load_libs() -> dict[str, dict]
          Returns every JSON the calculator needs, in a single
          dict keyed by short library name.

      get_lib(name: str) -> dict
          Convenience accessor returning a single library.

      DATA_DIR, SPRITES_DIR
          Resolved Path objects pointing at the resource folders.
          Useful for the icon identifier (Phase 2).

  Library names returned by ``load_libs()``:

      item_balancing_library, item_balancing_config,
      weapon_library, projectiles_library,
      pet_library, pet_upgrade_library, pet_balancing_library,
      mount_upgrade_library,
      skill_library, skill_passive_library,
      pvp_base_config, secondary_stat_library,
      ascension_configs_library,
      auto_item_mapping, manual_sprite_mapping
============================================================
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# Reference data layout (JSONs + spritesheets) lives at the project root
# in ``data/``. Walking one level up from this file's package directory
# (``backend/``) lands on the project root.
DATA_DIR    = Path(__file__).resolve().parent.parent / "data"
SPRITES_DIR = DATA_DIR / "sprites"

# Backwards-compatible private alias used by the rest of this module.
_DATA_DIR = DATA_DIR

# (file_basename, exported_attribute_name)
_LIB_FILES = {
    "item_balancing_library":   "ItemBalancingLibrary.json",
    "item_balancing_config":    "ItemBalancingConfig.json",
    "weapon_library":           "WeaponLibrary.json",
    "projectiles_library":      "ProjectilesLibrary.json",
    "pet_library":              "PetLibrary.json",
    "pet_upgrade_library":      "PetUpgradeLibrary.json",
    "mount_upgrade_library":    "MountUpgradeLibrary.json",
    "skill_library":            "SkillLibrary.json",
    "skill_passive_library":    "SkillPassiveLibrary.json",
    "pvp_base_config":          "PvpBaseConfig.json",
    "secondary_stat_library":   "SecondaryStatLibrary.json",
    "ascension_configs_library": "AscensionConfigsLibrary.json",
    # Mapping tables used by the future icon identifier (Phase 2).
    "auto_item_mapping":        "AutoItemMapping.json",
    "manual_sprite_mapping":    "ManualSpriteMapping.json",
}

# PetBalancingLibrary.json is referenced by statEngine.ts but is NOT shipped
# under data/. We default every pet type to neutral multipliers so the
# calculator still runs. If the file appears later it will be picked up
# automatically by the loader.
_PET_BALANCING_DEFAULT: Dict[str, Dict[str, float]] = {
    "Balanced":   {"DamageMultiplier": 1.0, "HealthMultiplier": 1.0},
    "Tank":       {"DamageMultiplier": 0.5, "HealthMultiplier": 1.5},
    "Damage":     {"DamageMultiplier": 1.5, "HealthMultiplier": 0.5},
    "Glasscannon": {"DamageMultiplier": 2.0, "HealthMultiplier": 0.0},
}

_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        log.debug("enemy_libraries: %s missing", path.name)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001 - blanket catch is intentional, we log + return None
        log.exception("enemy_libraries: failed to load %s", path.name)
        return None


def load_libs() -> Dict[str, Any]:
    """Load every JSON the calculator needs (cached after the first call)."""
    if _cache:
        return _cache

    with _cache_lock:
        if _cache:
            return _cache

        loaded: Dict[str, Any] = {}
        for short_name, file_name in _LIB_FILES.items():
            data = _read_json(_DATA_DIR / file_name)
            loaded[short_name] = data or {}

        # PetBalancingLibrary may or may not be shipped — fall back to
        # neutral multipliers when it is missing.
        pet_balancing = _read_json(_DATA_DIR / "PetBalancingLibrary.json")
        loaded["pet_balancing_library"] = pet_balancing or dict(_PET_BALANCING_DEFAULT)

        _cache.update(loaded)
        log.info("enemy_libraries: loaded %d libraries from %s",
                 len(_cache), _DATA_DIR)
        return _cache


def get_lib(name: str) -> Any:
    """Single-library accessor. Returns ``{}`` if unknown."""
    return load_libs().get(name, {})


def reset_cache() -> None:
    """Clear the module cache. Useful in tests."""
    with _cache_lock:
        _cache.clear()


# ────────────────────────────────────────────────────────────
#  Sprite path helpers (used by the Phase 2 icon identifier)
# ────────────────────────────────────────────────────────────

# Spritesheets shipped with the project. Their names match the file basenames
# under ``data/sprites/``; values are the integer ``Age`` index used as the
# first component of an ItemBalancingLibrary key.
AGE_TO_SPRITESHEET: Dict[int, str] = {
    0: "PrimitiveAgeItems.png",
    1: "MedievalAgeItems.png",
    2: "EarlyModernAgeItems.png",
    3: "ModernAgeItems.png",
    4: "SpaceAgeItems.png",
    5: "InterstellarAgeItems.png",
    6: "MultiverseAgeItems.png",
    7: "QuantumAgeItems.png",
    8: "UnderworldAgeItems.png",
    9: "DivineAgeItems.png",
}

PETS_ATLAS_NAME   = "Pets.png"
MOUNTS_ATLAS_NAME = "MountIcons.png"
SKILLS_ATLAS_NAME = "SkillIcons.png"


def sprite_path(filename: str) -> Path:
    """Resolve a sprite filename against ``data/sprites/``.

    Returns the Path even when the file is missing — caller decides
    how to handle that.
    """
    return SPRITES_DIR / filename


def age_spritesheet_path(age: int) -> Optional[Path]:
    """Path to the items spritesheet of the given Age, or None when
    the Age is unknown."""
    name = AGE_TO_SPRITESHEET.get(age)
    return SPRITES_DIR / name if name else None


def pets_atlas_path() -> Path:
    return SPRITES_DIR / PETS_ATLAS_NAME


def mounts_atlas_path() -> Path:
    return SPRITES_DIR / MOUNTS_ATLAS_NAME


def skills_atlas_path() -> Path:
    return SPRITES_DIR / SKILLS_ATLAS_NAME
