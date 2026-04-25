"""
Window state — window.json I/O (geometry between sessions).

A simple {window_id: geometry_string} dict. The geometry string is the
native Tk format used by `wm geometry`: "WIDTHxHEIGHT+X+Y".

Keys currently used:
    - "main"           → ForgeMasterApp main window
    - "profile_dialog" → Dashboard "Update Profile" dialog
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict

from ..constants import WINDOW_STATE_FILE
from ._io import _ensure_parent_dir

log = logging.getLogger(__name__)


def load_window_state() -> Dict[str, str]:
    """Load saved window geometries. Returns {} on missing/invalid file."""
    if not os.path.isfile(WINDOW_STATE_FILE):
        return {}
    try:
        with open(WINDOW_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("window.json unreadable (%s) — ignoring", e)
        return {}
    if not isinstance(data, dict):
        return {}
    # Keep only string values — malformed entries are discarded.
    return {k: v for k, v in data.items() if isinstance(v, str)}


def save_window_state(state: Dict[str, str]) -> None:
    """Persist the window geometry dict to window.json."""
    try:
        _ensure_parent_dir(WINDOW_STATE_FILE)
        with open(WINDOW_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
    except OSError as e:
        log.warning("Failed to save window.json: %s", e)


def remember_window(window_id: str, geometry: str) -> None:
    """Convenience helper: update a single entry and flush to disk."""
    state = load_window_state()
    state[window_id] = geometry
    save_window_state(state)
