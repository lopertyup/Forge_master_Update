"""
============================================================
  FORGE MASTER — Opponent capture offset table

  All offsets are RELATIVE to the upper-left corner of the
  opponent capture (the bbox saved under zone_key="opponent"
  in zones.json). They are stored as ratios of the capture's
  full width / height so the same numbers stay valid whether
  the user plays in a 380×640 mobile layout or a 1080×1920
  one.

  Two layouts are supported:

    * Default ratios (this file)   — derived from the sample
      capture provided with the chantier brief. Good first
      guess; calibrate against your real screenshot via
      tools/calibrate_offsets.py if matches feel off.

    * data/opponent_offsets.json   — overrides written by the
      calibration tool. When present, overrides this file
      entry by entry. Missing keys fall back to defaults.

  Slot order is the canonical one used everywhere:

      Helmet, Body, Gloves, Necklace, Ring, Weapon, Shoe, Belt
============================================================
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...data.libraries import DATA_DIR

log = logging.getLogger(__name__)

SLOT_ORDER: Tuple[str, ...] = (
    "Helmet", "Body", "Gloves", "Necklace", "Ring",
    "Weapon", "Shoe", "Belt",
)


# ────────────────────────────────────────────────────────────
#  Default ratios — measured visually on the chantier's
#  reference capture (≈ 400 × 640 portrait, opponent panel
#  fills the full bbox).
# ────────────────────────────────────────────────────────────
#
# Each tuple is (x, y, w, h) expressed as fractions of the
# capture's (W, H). Keep precision modest — these are rough
# defaults intended to be overridden by per-user calibration.

# 8 equipment slots: 5 across × 2 rows, the second row's 4th
# cell being a wider "mount" tile.
EQUIPMENT_RATIOS: List[Tuple[float, float, float, float]] = [
    # Row 1 — Helmet, Body, Gloves, Necklace, Ring
    (0.045, 0.405, 0.155, 0.105),
    (0.215, 0.405, 0.155, 0.105),
    (0.385, 0.405, 0.155, 0.105),
    (0.555, 0.405, 0.155, 0.105),
    (0.725, 0.405, 0.155, 0.105),
    # Row 2 — Weapon, Shoe, Belt (3 first cells)
    (0.045, 0.535, 0.155, 0.105),
    (0.215, 0.535, 0.155, 0.105),
    (0.385, 0.535, 0.155, 0.105),
]

# Mount sits in the 4th cell of row 2 (wider, green frame).
MOUNT_RATIO: Tuple[float, float, float, float] = (0.555, 0.535, 0.325, 0.105)

# Bottom row: 3 skills (red circles) followed by 3 pets (red squares).
SKILL_RATIOS: List[Tuple[float, float, float, float]] = [
    (0.060, 0.690, 0.085, 0.060),
    (0.180, 0.690, 0.085, 0.060),
    (0.300, 0.690, 0.085, 0.060),
]
PET_RATIOS: List[Tuple[float, float, float, float]] = [
    (0.420, 0.690, 0.085, 0.060),
    (0.540, 0.690, 0.085, 0.060),
    (0.660, 0.690, 0.085, 0.060),
]

# For every equipment cell, two derived patches feed the
# colour heuristics:
#   * a 5%-wide vertical strip on the right edge → rarity
#   * a 5%-square at the centre               → age
def _border_strip(eq: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    x, y, w, h = eq
    return (x + w - 0.012, y + h * 0.20, 0.012, h * 0.60)


def _bg_patch(eq: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
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


_OVERRIDES_PATH = DATA_DIR / "opponent_offsets.json"


def _load_overrides() -> Dict[str, list]:
    """Read data/opponent_offsets.json if it exists.

    Schema:
        {
          "equipment": [[x,y,w,h], ...]    // 8 entries
          "border":    [[x,y,w,h], ...]    // 8 entries (optional)
          "bg":        [[x,y,w,h], ...]    // 8 entries (optional)
          "mount":     [x,y,w,h]
          "pets":      [[x,y,w,h], ...]    // 0..3 entries
          "skills":    [[x,y,w,h], ...]    // 0..3 entries
        }

    All values are RATIOS just like the defaults.
    """
    if not _OVERRIDES_PATH.is_file():
        return {}
    try:
        return json.loads(_OVERRIDES_PATH.read_text())
    except Exception:
        log.exception("opponent_offsets.json malformed — using defaults")
        return {}


def _maybe(overrides: dict, key: str, default):
    val = overrides.get(key)
    if val is None:
        return default
    return val


# ────────────────────────────────────────────────────────────
#  Public API — pixel offsets for a given capture size
# ────────────────────────────────────────────────────────────


def _to_pixels(ratio: Tuple[float, float, float, float],
               w: int, h: int) -> Tuple[int, int, int, int]:
    x, y, rw, rh = ratio
    return (int(round(x * w)), int(round(y * h)),
            int(round((x + rw) * w)), int(round((y + rh) * h)))


def offsets_for_capture(width: int, height: int) -> Dict[str, List[Tuple[int, int, int, int]]]:
    """Return all bbox tuples in absolute pixel coordinates.

    Output shape (lists, not Optional, to keep the consumer simple):

        {
          "equipment": [(x0,y0,x1,y1) × 8],
          "border":    [(x0,y0,x1,y1) × 8],
          "bg":        [(x0,y0,x1,y1) × 8],
          "mount":     [(x0,y0,x1,y1)] | [],
          "pets":      [(x0,y0,x1,y1) × N],
          "skills":    [(x0,y0,x1,y1) × N],
          "slot_order": ("Helmet", ...),
        }
    """
    overrides = _load_overrides()

    equipment_r = _maybe(overrides, "equipment", EQUIPMENT_RATIOS)
    border_r    = _maybe(overrides, "border",    BORDER_RATIOS)
    bg_r        = _maybe(overrides, "bg",        BG_RATIOS)
    mount_r     = _maybe(overrides, "mount",     MOUNT_RATIO)
    pet_r       = _maybe(overrides, "pets",      PET_RATIOS)
    skill_r     = _maybe(overrides, "skills",    SKILL_RATIOS)

    out: Dict[str, list] = {
        "equipment": [_to_pixels(tuple(r), width, height) for r in equipment_r],
        "border":    [_to_pixels(tuple(r), width, height) for r in border_r],
        "bg":        [_to_pixels(tuple(r), width, height) for r in bg_r],
        "pets":      [_to_pixels(tuple(r), width, height) for r in pet_r],
        "skills":    [_to_pixels(tuple(r), width, height) for r in skill_r],
        "slot_order": SLOT_ORDER,
    }
    if mount_r is None:
        out["mount"] = []
    else:
        out["mount"] = [_to_pixels(tuple(mount_r), width, height)]

    return out


def write_overrides(payload: Dict) -> None:
    """Persist a calibration result. The calibration tool calls this."""
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDES_PATH.write_text(json.dumps(payload, indent=2))
    log.info("opponent_offsets.json: wrote %d keys", len(payload))


def overrides_path() -> Path:
    return _OVERRIDES_PATH
