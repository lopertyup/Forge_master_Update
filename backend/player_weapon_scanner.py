"""
============================================================
  FORGE MASTER -- Player weapon scanner

  Light wrapper around the enemy icon identifier so we can
  identify the PLAYER's equipped weapon from a screenshot
  crop and look up its windup / recovery / projectile data
  in the same JSON libraries the enemy pipeline already
  loads.

  Intended use:
    * The user configures a 1-bbox zone "player_weapon"
      pointing at the on-screen weapon icon (just the icon,
      not the whole equipment screen).
    * The controller captures that bbox and calls
      scan_player_weapon_image(crop).
    * The returned dict is merged into the player profile so
      the simulator picks up windup / recovery /
      projectile_travel_time exactly like it already does for
      the OCR-recomputed opponent.

  Pure function -- no I/O beyond the labeled-icon folder and
  the JSON libraries; safe to call from a background thread.
============================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from PIL import Image

from .enemy_icon_identifier import (
    identify_age_from_color,
    identify_item,
    identify_rarity_from_color,
)
from .enemy_libraries import load_libs
from .enemy_stat_calculator import _item_key
from .weapon_projectiles import RANGE_RANGED, get_travel_time

log = logging.getLogger(__name__)


# These ratios are the same the enemy pipeline applies to each
# equipment cell. Reproduced here so we don't pull in the full
# offset machinery (the player scanner only ever sees a single
# weapon icon, never a multi-slot panel).
_BORDER_STRIP = (1.0 - 0.05, 0.20, 0.05, 0.60)   # x, y, w, h (relative)
_BG_PATCH     = (0.41, 0.41, 0.18, 0.18)         # 18%-square centred


def _crop_relative(img: Image.Image,
                   ratio_xywh: tuple) -> Image.Image:
    """Take a (x, y, w, h) ratio tuple in [0..1] and return the crop."""
    W, H = img.size
    x, y, w, h = ratio_xywh
    x0 = max(0, int(round(x * W)))
    y0 = max(0, int(round(y * H)))
    x1 = min(W, int(round((x + w) * W)))
    y1 = min(H, int(round((y + h) * H)))
    if x1 <= x0 or y1 <= y0:
        return img.copy()
    return img.crop((x0, y0, x1, y1))


def scan_player_weapon_image(
    icon_crop: Image.Image,
    libs: Optional[Dict] = None,
) -> Optional[Dict]:
    """Identify the player's weapon from an isolated icon crop.

    Returns a dict with:
        weapon_age, weapon_idx     -- diagnostic ids
        weapon_rarity              -- rarity name (info only)
        weapon_windup              -- WindupTime from WeaponLibrary
        weapon_recovery            -- AttackDuration - WindupTime
        weapon_attack_range        -- raw AttackRange (0.3 melee, 7.0 ranged)
        attack_type                -- "melee" or "ranged"
        projectile_speed           -- units / s, 0.0 if melee
        projectile_travel_time     -- range / speed, 0.0 if melee or unknown

    Returns None when identification or lookup fails. The caller
    should leave the player's weapon stats untouched in that case.
    """
    if icon_crop is None:
        return None

    bg_crop     = _crop_relative(icon_crop, _BG_PATCH)
    border_crop = _crop_relative(icon_crop, _BORDER_STRIP)

    age = identify_age_from_color(bg_crop)
    rarity = identify_rarity_from_color(border_crop)
    if age is None:
        log.warning("scan_player_weapon: could not infer age from background")
        return None

    item = identify_item(icon_crop, "Weapon", int(age))
    if not item:
        log.warning(
            "scan_player_weapon: identify_item failed (age=%s rarity=%s) -- "
            "is helper/icons_organized populated for this age?", age, rarity,
        )
        return None

    libs = libs or load_libs()
    weapon_lib = libs.get("weapon_library") or {}
    projectiles_lib = libs.get("projectiles_library") or {}

    key = _item_key(int(item["age"]), "Weapon", int(item["idx"]))
    w_data = weapon_lib.get(key)
    if not isinstance(w_data, dict):
        log.warning("scan_player_weapon: weapon_library miss for %s", key)
        return None

    windup    = float(w_data.get("WindupTime") or 0.5)
    duration  = float(w_data.get("AttackDuration") or 1.5)
    range_raw = float(w_data.get("AttackRange") or 0.3)
    is_ranged = range_raw >= 1.0
    recovery  = max(duration - windup, 0.0)

    proj_id = w_data.get("ProjectileId")
    speed = 0.0
    travel = 0.0
    if is_ranged:
        # Prefer the on-disk JSON; fall back to the static table in
        # weapon_projectiles when ProjectilesLibrary doesn't know
        # this id (tests, malformed data, etc.).
        from .weapon_projectiles import get_projectile_speed
        speed_lookup = get_projectile_speed(
            weapon_name=None,
            projectile_id=int(proj_id) if isinstance(proj_id, int) else None,
            lib=projectiles_lib,
        )
        if speed_lookup and speed_lookup > 0.0:
            speed = float(speed_lookup)
            travel = range_raw / speed if speed > 0 else 0.0
        else:
            # Last-resort: the centralised helper applies its own
            # heuristics (range default = RANGE_RANGED, etc.).
            travel = get_travel_time(
                projectile_id=int(proj_id) if isinstance(proj_id, int) else None,
                weapon_range=range_raw,
                lib=projectiles_lib,
            )

    return {
        "weapon_age":             int(item["age"]),
        "weapon_idx":             int(item["idx"]),
        "weapon_rarity":          str(rarity or ""),
        "weapon_windup":          windup,
        "weapon_recovery":        recovery,
        "weapon_attack_range":    range_raw,
        "attack_type":            "ranged" if is_ranged else "melee",
        "projectile_speed":       speed,
        "projectile_travel_time": travel,
    }
