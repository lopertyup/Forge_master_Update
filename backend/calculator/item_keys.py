"""
============================================================
  FORGE MASTER — JSON key helpers (public API)

  The reference JSONs (``ItemBalancingLibrary``, ``WeaponLibrary``,
  ``PetLibrary``, ``PetUpgradeLibrary``, ``MountUpgradeLibrary``,
  ``SkillPassiveLibrary``, ...) all use string-encoded Python
  dicts as their keys. This module owns the BIT-FOR-BIT
  reproductions of those strings so the calculator and the
  scanner agree on a single canonical form.

  These helpers used to live as private functions
  (``_item_key`` / ``_pet_key`` / ``_stat_type`` / ``_level_info_for``)
  inside ``backend.calculator.combat``. They were promoted to
  a public module so the player-side scanners stop reaching into
  another module's privates.

  Public API
  ----------
      item_key(age, type_name, idx)   -> str
      pet_key(rarity, pet_id)         -> str
      stat_type(stat_node_wrapper)    -> str
      level_info_for(upgrade, level)  -> dict | None
============================================================
"""

from __future__ import annotations

from typing import Any


# ────────────────────────────────────────────────────────────
#  Stringly-typed JSON keys
# ────────────────────────────────────────────────────────────


def item_key(age: int, type_name: str, idx: int) -> str:
    """Return the ``ItemBalancingLibrary`` / ``WeaponLibrary`` key
    for one piece of gear. The format mirrors what
    ``statEngine.ts`` builds at runtime — single quotes, spaces
    after the commas, mandatory double-digit-safe ``%d``.
    """
    return "{'Age': %d, 'Type': '%s', 'Idx': %d}" % (age, type_name, idx)


def pet_key(rarity: str, pet_id: int) -> str:
    """Return the ``PetLibrary`` key for one pet."""
    return "{'Rarity': '%s', 'Id': %d}" % (rarity, pet_id)


# ────────────────────────────────────────────────────────────
#  Generic helpers
# ────────────────────────────────────────────────────────────


def stat_type(stat_node_wrapper: Any) -> str:
    """Extract ``StatNode.UniqueStat.StatType`` defensively.

    ``StatNode`` blocks come in many shapes across the dumps
    (sometimes the wrapper is missing, sometimes ``UniqueStat``
    is null). Returning the empty string lets callers treat the
    value as "stat unknown" without an explicit None check.
    """
    if not isinstance(stat_node_wrapper, dict):
        return ""
    stat_node = stat_node_wrapper.get("StatNode") or {}
    unique = stat_node.get("UniqueStat") or {}
    return str(unique.get("StatType") or "")


def level_info_for(upgrade_data: Any, level: int) -> Any:
    """Pet/Mount/Skill upgrade libraries are keyed by rarity, then
    have a list of LevelInfo entries with a 0-indexed ``Level``
    field. The user-facing level is 1-indexed, so we look for
    ``Level == level - 1`` and fall back to the first entry on
    miss (matches the TS reference behaviour).
    """
    if not isinstance(upgrade_data, dict):
        return None
    info_list = upgrade_data.get("LevelInfo")
    if not isinstance(info_list, list) or not info_list:
        return None

    target = max(0, int(level) - 1)
    for entry in info_list:
        if isinstance(entry, dict) and entry.get("Level") == target:
            return entry
    return info_list[0]


# ────────────────────────────────────────────────────────────
#  Backwards-compatible private aliases
# ────────────────────────────────────────────────────────────
#
# Old code (notably the few tests that imported the originally
# private names) keeps working until callers are migrated.

_item_key       = item_key
_pet_key        = pet_key
_stat_type      = stat_type
_level_info_for = level_info_for
