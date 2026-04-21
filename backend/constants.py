"""
============================================================
  FORGE MASTER — Shared constants
  All backend "configuration parameters" live here to avoid
  scattering them across modules.
============================================================
"""

import os

# ── Paths ───────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE         = os.path.join(_DIR, "profile.txt")
SKILLS_FILE          = os.path.join(_DIR, "skills.txt")
PETS_FILE            = os.path.join(_DIR, "pets.txt")
MOUNT_FILE           = os.path.join(_DIR, "mount.txt")
PETS_LIBRARY_FILE    = os.path.join(_DIR, "pets_library.txt")
MOUNT_LIBRARY_FILE   = os.path.join(_DIR, "mount_library.txt")

# ── Simulation parameters ───────────────────────────────────
TICK                    = 0.01
DEFAULT_MAX_DURATION    = 300.0   # simulated seconds per fight (profile vs opponent)
COMPANION_MAX_DURATION  = 60.0    # shorter for "me vs me" (avoid infinite fights)
BASE_SPEED              = 0.5
RANGED_LEAD             = 3.0
N_SIMULATIONS           = 1000    # number of fights per test

# ── Stat schemas ────────────────────────────────────────────

STATS_KEYS = [
    "hp_total", "attack_total",
    "hp_base", "attack_base",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
    "crit_chance", "crit_damage", "health_regen",
    "lifesteal", "double_chance", "attack_speed",
    "skill_damage", "skill_cooldown", "block_chance",
]

# Pets and mount share exactly the same schema
COMPANION_STATS_KEYS = [
    "hp_flat", "damage_flat", "health_pct", "damage_pct",
    "melee_pct", "ranged_pct", "crit_chance", "crit_damage",
    "health_regen", "lifesteal", "double_chance", "attack_speed",
    "skill_damage", "skill_cooldown", "block_chance",
]

# Back-compat aliases — pets and mount used to have their own constants
PETS_STATS_KEYS  = COMPANION_STATS_KEYS
MOUNT_STATS_KEYS = COMPANION_STATS_KEYS

# Percentage stats shared by profile / equipment / companion
PERCENT_STATS_KEYS = [
    "crit_chance", "crit_damage", "health_regen", "lifesteal",
    "double_chance", "attack_speed", "skill_damage",
    "skill_cooldown", "block_chance",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
]
