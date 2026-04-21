"""
============================================================
  FORGE MASTER — Backend (compatibility shim)

  The backend has been split into thematic modules:
    - backend/constants.py    : all constants
    - backend/parser.py       : parsers (text -> dict)
    - backend/stats.py        : pure math on stat dicts
    - backend/persistence.py  : .txt read / write
    - backend/simulation.py   : combat engine
    - backend/optimizer.py    : marginal stat optimizer

  This file re-exports the public API to keep backward
  compatibility with existing code. New modules should
  import directly from the targeted sub-modules.
============================================================
"""

# Constants -----------------------------------------------------
from .constants import (  # noqa: F401
    BASE_SPEED,
    COMPANION_MAX_DURATION,
    COMPANION_STATS_KEYS,
    DEFAULT_MAX_DURATION,
    MOUNT_FILE,
    MOUNT_STATS_KEYS,
    N_SIMULATIONS,
    PERCENT_STATS_KEYS,
    PETS_FILE,
    PETS_STATS_KEYS,
    PROFILE_FILE,
    RANGED_LEAD,
    SKILLS_FILE,
    STATS_KEYS,
    TICK,
)

# Parser --------------------------------------------------------
from .parser import (  # noqa: F401
    extract,
    extract_flat,
    parse_companion,
    parse_equipment,
    parse_flat,
    parse_mount,
    parse_pet,
    parse_profile_text,
)

# Stats math ----------------------------------------------------
from .stats import (  # noqa: F401
    apply_change,
    apply_companion,
    apply_mount,
    apply_pet,
    combat_stats,
    finalize_bases,
)

# Persistence ---------------------------------------------------
from .persistence import (  # noqa: F401
    empty_companion,
    load_mount,
    load_pets,
    load_profile,
    load_skills,
    mount_vide,
    pet_vide,
    save_mount,
    save_pets,
    save_profile,
)

# Simulation ----------------------------------------------------
from .simulation import (  # noqa: F401
    Fighter,
    SkillInstance,
    simulate,
    simulate_batch,
)

# Compat: some callers used to read fm.DUREE_MAX to patch it.
# We expose the value but new callers must pass max_duration as
# an argument to simulate() / simulate_batch().
MAX_DURATION = DEFAULT_MAX_DURATION
