"""
============================================================
  FORGE MASTER — Persistence package

  Read and write profile.txt, pets.txt, mount.txt, skills.txt,
  zones.json and window.json.

  Historically this was a single 600-line module. It has been
  split into focused submodules (one per domain) while keeping
  the same import surface: every previous public name is still
  reachable via `from backend.persistence import X`.

  Submodules:
      _io          shared helpers  (_ensure_parent_dir,
                                    empty_companion, _LIBRARY_KEYS)
      profile      profile.txt       (save_profile, load_profile)
      skills       skills.txt        (SKILL_SLOTS, empty_skill,
                                      load_skills, load_skill_slots,
                                      save_skills)
      companions   pets.txt + mount.txt
                                    (load_pets, save_pets,
                                     load_mount, save_mount)
      libraries    *_library.txt    (load_pets_library,
                                     save_pets_library, ...)
      zones        zones.json       (load_zones, save_zones)
      window       window.json      (load_window_state,
                                     save_window_state,
                                     remember_window)
============================================================
"""

from __future__ import annotations

# Shared helpers -------------------------------------------------------------
from ._io import (
    _ensure_parent_dir,
    empty_companion,
    pet_vide,
    mount_vide,
    _LIBRARY_KEYS,
)

# Profile --------------------------------------------------------------------
from .profile import (
    save_profile,
    load_profile,
    _read_section,
)

# Skills ---------------------------------------------------------------------
from .skills import (
    SKILL_SLOTS,
    empty_skill,
    _is_empty_skill,
    load_skills,
    load_skill_slots,
    save_skills,
)

# Pets + mount ---------------------------------------------------------------
from .companions import (
    load_pets,
    save_pets,
    load_mount,
    save_mount,
)

# Libraries (pets, mount, skills at Lv.1) ------------------------------------
from .libraries import (
    _load_library,
    _save_library,
    load_pets_library,
    save_pets_library,
    load_mount_library,
    save_mount_library,
    load_skills_library,
    save_skills_library,
)

# OCR zones ------------------------------------------------------------------
from .zones import (
    _zone_defaults,
    load_zones,
    save_zones,
)

# Window geometry ------------------------------------------------------------
from .window import (
    load_window_state,
    save_window_state,
    remember_window,
)

__all__ = [
    # _io
    "_ensure_parent_dir",
    "empty_companion",
    "pet_vide",
    "mount_vide",
    "_LIBRARY_KEYS",
    # profile
    "save_profile",
    "load_profile",
    "_read_section",
    # skills
    "SKILL_SLOTS",
    "empty_skill",
    "_is_empty_skill",
    "load_skills",
    "load_skill_slots",
    "save_skills",
    # companions
    "load_pets",
    "save_pets",
    "load_mount",
    "save_mount",
    # libraries
    "_load_library",
    "_save_library",
    "load_pets_library",
    "save_pets_library",
    "load_mount_library",
    "save_mount_library",
    "load_skills_library",
    "save_skills_library",
    # zones
    "_zone_defaults",
    "load_zones",
    "save_zones",
    # window
    "load_window_state",
    "save_window_state",
    "remember_window",
]
