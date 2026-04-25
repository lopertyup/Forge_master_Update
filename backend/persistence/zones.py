"""
OCR zones — zones.json I/O.

Each entry:   { "captures": int, "bboxes": [[x1,y1,x2,y2], ...] }
  - captures = nb of successive screen grabs (2 = scroll between)
  - bboxes   = one bbox per capture, screen-absolute coordinates

`load_zones()` tolerates a missing / malformed file by falling back to
ZONE_DEFAULTS. Any key missing from the JSON is backfilled from the
defaults so new zones work without having to regenerate the file by
hand.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

from ..constants import ZONE_DEFAULTS, ZONES_FILE
from ._io import _ensure_parent_dir

log = logging.getLogger(__name__)


def _zone_defaults() -> Dict[str, Dict]:
    """Deep-copy of ZONE_DEFAULTS so callers can mutate safely."""
    return {
        k: {"captures": int(v["captures"]),
            "bboxes":   [list(b) for b in v["bboxes"]]}
        for k, v in ZONE_DEFAULTS.items()
    }


def load_zones() -> Dict[str, Dict]:
    """Load OCR zones from zones.json, filling in missing keys from defaults."""
    defaults = _zone_defaults()
    if not os.path.isfile(ZONES_FILE):
        return defaults
    try:
        with open(ZONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("zones.json unreadable (%s) — using defaults", e)
        return defaults

    if not isinstance(data, dict):
        log.warning("zones.json is not a dict — using defaults")
        return defaults

    # Sanitise each entry, backfilling from defaults where needed.
    for key, default_entry in defaults.items():
        entry = data.get(key)
        if not isinstance(entry, dict):
            data[key] = default_entry
            continue
        captures = int(entry.get("captures", default_entry["captures"]))
        raw_boxes = entry.get("bboxes") or default_entry["bboxes"]
        bboxes: List[List[int]] = []
        for b in raw_boxes:
            try:
                bboxes.append([int(c) for c in b])
            except (TypeError, ValueError):
                bboxes.append([0, 0, 0, 0])
        # Make sure we have at least `captures` boxes.
        while len(bboxes) < captures:
            bboxes.append([0, 0, 0, 0])
        data[key] = {"captures": captures, "bboxes": bboxes}
    return data


def save_zones(zones: Dict[str, Dict]) -> None:
    """Persist the full zones dict back to zones.json."""
    _ensure_parent_dir(ZONES_FILE)
    with open(ZONES_FILE, "w", encoding="utf-8") as f:
        json.dump(zones, f, indent=2)
        f.write("\n")
