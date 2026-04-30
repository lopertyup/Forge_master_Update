"""
============================================================
  FORGE MASTER — Weapon-slot enrichment

  Direct port of ``backend/scanner/weapon.py`` — narrowed to
  the WeaponLibrary + ProjectilesLibrary lookup, without any
  per-tile colour heuristic or icon matching of its own. The
  visual identification is now handled upstream
  (player_equipment.py for the 8-tile flow, equipment_popup.py
  for the single-slot flow) — both call this helper after they
  have an (age, idx) for the Weapon slot.

  Public API:

      enrich_weapon_slot(slot_dict, *, libs=None) -> slot_dict

  Mutates ``slot_dict`` in place AND returns it for convenience.
  Adds the following keys when the WeaponLibrary lookup
  succeeds:

      attack_type            — "melee" or "ranged"
      weapon_attack_range    — raw AttackRange (0.3 melee,
                               7.0 ranged baseline)
      weapon_windup          — WindupTime (default 0.5)
      weapon_recovery        — AttackDuration - WindupTime
      projectile_speed       — units / s, 0.0 if melee
      projectile_travel_time — PvP travel time, 0.0 if melee
                               or unknown projectile id

  These are the same field names ``scan_player_weapon_image``
  used to expose; downstream consumers (Simulator,
  Dashboard) keep their existing reads.
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def enrich_weapon_slot(
    slot_dict: Dict[str, Any],
    *,
    libs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inject WeaponLibrary-derived fields into a Weapon slot_dict.

    Parameters
    ----------
    slot_dict : dict
        A slot_dict produced by player_equipment.py /
        equipment_popup.py. Must already carry ``__age__`` and
        ``__idx__`` for the lookup to succeed; otherwise the
        function is a no-op (logs a debug line).
    libs : optional
        Pre-loaded ``data/libraries`` dict. When None, this
        helper imports ``backend.data.libraries.load_libs`` and
        calls it. Callers wiring a batch of slots should pass
        the libs once for performance.

    Returns
    -------
    dict
        The same ``slot_dict``, mutated in place. When the
        WeaponLibrary entry is missing, the dict is returned
        unchanged — the caller's existing fields stay intact
        and downstream code falls back to the legacy timing
        defaults exactly like before.
    """
    if not isinstance(slot_dict, dict):
        return slot_dict

    age = slot_dict.get("__age__")
    idx = slot_dict.get("__idx__")
    if age is None or idx is None:
        log.debug("enrich_weapon_slot: missing age/idx, skipping")
        return slot_dict

    # Lazy-load libraries to keep scan/ importable on headless
    # test runs that stub data/.
    if libs is None:
        try:
            from backend.data.libraries import load_libs as _load
            libs = _load() or {}
        except Exception:  # pragma: no cover - defensive
            log.exception("enrich_weapon_slot: load_libs() failed")
            return slot_dict

    weapon_lib      = libs.get("weapon_library") or {}
    projectiles_lib = libs.get("projectiles_library") or {}

    try:
        from backend.calculator.item_keys import item_key as _item_key
    except Exception:  # pragma: no cover - defensive
        log.exception("enrich_weapon_slot: item_keys helper unavailable")
        return slot_dict

    key = _item_key(int(age), "Weapon", int(idx))
    w_data = weapon_lib.get(key)
    if not isinstance(w_data, dict):
        log.warning("enrich_weapon_slot: weapon_library miss for %s", key)
        return slot_dict

    windup    = float(w_data.get("WindupTime") or 0.5)
    duration  = float(w_data.get("AttackDuration") or 1.5)
    range_raw = float(w_data.get("AttackRange") or 0.3)
    is_ranged = range_raw >= 1.0
    recovery  = max(duration - windup, 0.0)

    proj_id = w_data.get("ProjectileId")
    speed = 0.0
    travel = 0.0
    if is_ranged:
        try:
            from backend.weapon.projectiles import (
                PVP_COMBAT_DISTANCE,
                get_projectile_speed,
                get_travel_time,
            )
        except Exception:  # pragma: no cover - defensive
            log.exception("enrich_weapon_slot: projectiles helper unavailable")
            return slot_dict

        speed_lookup = get_projectile_speed(
            weapon_name=None,
            projectile_id=int(proj_id) if isinstance(proj_id, int) else None,
            lib=projectiles_lib,
        )
        if speed_lookup and speed_lookup > 0.0:
            speed = float(speed_lookup)
            travel = PVP_COMBAT_DISTANCE / speed
        else:
            travel = float(get_travel_time(
                projectile_id=int(proj_id) if isinstance(proj_id, int) else None,
                weapon_range=range_raw,
                lib=projectiles_lib,
            ) or 0.0)

    slot_dict["attack_type"]            = "ranged" if is_ranged else "melee"
    slot_dict["weapon_attack_range"]    = range_raw
    slot_dict["weapon_windup"]          = windup
    slot_dict["weapon_recovery"]        = recovery
    slot_dict["projectile_speed"]       = speed
    slot_dict["projectile_travel_time"] = travel
    return slot_dict


__all__ = ["enrich_weapon_slot"]
