"""
============================================================
  FORGE MASTER -- Player equipment-panel offset table (scan/)

  Layout of the player's "Equipement" screen (the in-game grid
  that shows your 8 equipped pieces). Same shape as the
  opponent profile panel BUT typically captured on its own
  screen, so the panel may fill the entire bbox -- no pets,
  no mount, no skills, just the 8 equipment cells.

  Two layouts:

    * Default ratios (this file)
    * ``data/player_equipment_offsets.json`` -- per-user
      overrides written by ``tools/calibrate_player_equipment.py``

  Slot order is the canonical one:

      Helmet, Body, Gloves, Necklace, Ring, Weapon, Shoe, Belt

  Direct port of the legacy player offsets. Same
  numbers, same JSON schema. Phase 7 of the refactor (cf.
  PLAN_REFACTO_SCAN.txt).
============================================================
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Path constants — single source of truth
# ────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


SLOT_ORDER: Tuple[str, ...] = (
    "Helmet", "Body", "Gloves", "Necklace", "Ring",
    "Weapon", "Shoe", "Belt",
)


# ────────────────────────────────────────────────────────────
#  Default ratios -- same layout as the opponent profile panel
#  (5 cells on row 1, 3 cells + mount on row 2). The player's
#  "Equipement" screen has the IDENTICAL pixel arrangement, so
#  we mirror the calibrated ``enemy_icon_offsets`` numbers
#  rather than re-deriving them from scratch.
#
#  Calibrate against your own screenshot via
#  ``tools/calibrate_player_equipment.py`` if matches feel off.
# ────────────────────────────────────────────────────────────

EQUIPMENT_RATIOS: List[Tuple[float, float, float, float]] = [
    # Row 1 -- Helmet, Body, Gloves, Necklace, Ring
    (0.103, 0.365, 0.146, 0.097),
    (0.269, 0.365, 0.146, 0.097),
    (0.432, 0.365, 0.136, 0.097),
    (0.598, 0.365, 0.133, 0.097),
    (0.761, 0.365, 0.136, 0.097),
    # Row 2 -- Weapon, Shoe, Belt
    (0.103, 0.466, 0.136, 0.097),
    (0.269, 0.466, 0.133, 0.097),
    (0.432, 0.466, 0.136, 0.097),
]


# Border / background patches derive from the icon rectangles
# the same way they do on the opponent side.
def _border_strip(eq: Tuple[float, float, float, float]
                  ) -> Tuple[float, float, float, float]:
    x, y, w, h = eq
    return (x + w - 0.012, y + h * 0.20, 0.012, h * 0.60)


def _bg_patch(eq: Tuple[float, float, float, float]
              ) -> Tuple[float, float, float, float]:
    x, y, w, h = eq
    cx, cy = x + w * 0.5, y + h * 0.5
    s = min(w, h) * 0.18
    return (cx - s / 2, cy - s / 2, s, s)


BORDER_RATIOS: List[Tuple[float, float, float, float]] = [
    _border_strip(eq) for eq in EQUIPMENT_RATIOS
]
BG_RATIOS: List[Tuple[float, float, float, float]] = [
    _bg_patch(eq) for eq in EQUIPMENT_RATIOS
]


# ────────────────────────────────────────────────────────────
#  Override loader
# ────────────────────────────────────────────────────────────

_OVERRIDES_PATH = _DATA_DIR / "player_equipment_offsets.json"


def _load_overrides() -> Dict[str, list]:
    """Read ``data/player_equipment_offsets.json`` if present.

    Schema (all ratios)::

        {
          "equipment": [[x,y,w,h], ...]    // exactly 8 entries
          "border":    [[x,y,w,h], ...]    // 8 entries (optional)
          "bg":        [[x,y,w,h], ...]    // 8 entries (optional)
        }
    """
    if not _OVERRIDES_PATH.is_file():
        return {}
    try:
        return json.loads(_OVERRIDES_PATH.read_text())
    except Exception:
        log.exception(
            "player_equipment_offsets.json malformed -- using defaults")
        return {}


def _maybe(overrides: dict, key: str, default):
    val = overrides.get(key)
    if val is None:
        return default
    return val


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────


def _to_pixels(ratio: Tuple[float, float, float, float],
               w: int, h: int) -> Tuple[int, int, int, int]:
    x, y, rw, rh = ratio
    return (int(round(x * w)),       int(round(y * h)),
            int(round((x + rw) * w)), int(round((y + rh) * h)))


def offsets_for_capture(width: int, height: int) -> Dict[str, list]:
    """Return absolute pixel offsets for the 8 equipment cells.

    Output::

        {
          "equipment":  [(x0,y0,x1,y1) x 8],
          "border":     [(x0,y0,x1,y1) x 8],
          "bg":         [(x0,y0,x1,y1) x 8],
          "slot_order": ("Helmet", ...),
        }
    """
    overrides = _load_overrides()
    equipment_r = _maybe(overrides, "equipment", EQUIPMENT_RATIOS)
    border_r    = _maybe(overrides, "border",    BORDER_RATIOS)
    bg_r        = _maybe(overrides, "bg",        BG_RATIOS)

    return {
        "equipment":  [_to_pixels(tuple(r), width, height) for r in equipment_r],
        "border":     [_to_pixels(tuple(r), width, height) for r in border_r],
        "bg":         [_to_pixels(tuple(r), width, height) for r in bg_r],
        "slot_order": SLOT_ORDER,
    }


def write_overrides(payload: Dict) -> None:
    """Persist a calibration result. ``tools/calibrate_player_equipment.py``
    calls this."""
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDES_PATH.write_text(json.dumps(payload, indent=2))
    log.info("player_equipment_offsets.json: wrote %d keys", len(payload))


def overrides_path() -> Path:
    return _OVERRIDES_PATH


__all__ = [
    "SLOT_ORDER",
    "EQUIPMENT_RATIOS",
    "BORDER_RATIOS",
    "BG_RATIOS",
    "offsets_for_capture",
    "write_overrides",
    "overrides_path",
]
