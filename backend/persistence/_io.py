"""
Shared low-level helpers for the persistence package.

Kept deliberately tiny: path hygiene, empty-companion factory, and the
library-file key set. No file I/O here apart from `_ensure_parent_dir`.
"""

from __future__ import annotations

import os
from typing import Dict

from ..constants import COMPANION_STATS_KEYS


def _ensure_parent_dir(path: str) -> None:
    """Create the parent directory of `path` if it doesn't exist.

    A no-op when the parent is the current working directory (i.e.
    `os.path.dirname(path) == ""`). Called before every write so a
    fresh install with no `config/` or `data/` folders yet doesn't
    crash on first save.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def empty_companion() -> Dict[str, float]:
    """Zero-valued stats dict shared by pets and the mount."""
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


# Back-compat aliases kept for existing callers.
pet_vide   = empty_companion
mount_vide = empty_companion


# Library files (pets_library.txt, mount_library.txt) store three fields
# per entry. Skill libraries have their own shape — see libraries.py.
_LIBRARY_KEYS = ("rarity", "hp_flat", "damage_flat")
