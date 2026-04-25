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
SKILLS_LIBRARY_FILE  = os.path.join(_DIR, "skills_library.txt")
ZONES_FILE           = os.path.join(_DIR, "zones.json")
WINDOW_STATE_FILE    = os.path.join(_DIR, "window.json")

# Default zones used if zones.json is missing or incomplete.
# `captures` = number of successive screen grabs the user performs
# for this zone (2 means they scroll between clicks). All bboxes
# are initialised to zero until the user sends the real coords.
ZONE_DEFAULTS = {
    "profile":   {"captures": 2, "bboxes": [[0, 0, 0, 0], [0, 0, 0, 0]]},
    "opponent":  {"captures": 2, "bboxes": [[0, 0, 0, 0], [0, 0, 0, 0]]},
    "equipment": {"captures": 1, "bboxes": [[0, 0, 0, 0]]},
    "pet":       {"captures": 1, "bboxes": [[0, 0, 0, 0]]},
    "mount":     {"captures": 1, "bboxes": [[0, 0, 0, 0]]},
    "skill":     {"captures": 1, "bboxes": [[0, 0, 0, 0]]},
    # Player's equipped weapon icon -- a single 1-bbox zone the user
    # configures by drawing a tight box around the weapon icon on
    # their own character screen. Consumed by the player_weapon
    # scanner to derive windup / recovery / projectile_travel_time.
    "player_weapon": {"captures": 1, "bboxes": [[0, 0, 0, 0]]},
}

# ── Simulation parameters ───────────────────────────────────
TICK                    = 0.01
DEFAULT_MAX_DURATION    = 60.0    # PvP time limit
COMPANION_MAX_DURATION  = 60.0    # same cap for swap-comparison fights
N_SIMULATIONS           = 1000    # number of fights per test

# ── PvP model ───────────────────────────────────────────────
# HP pool = hp_total × PVP_HP_MULTIPLIER, same scaling for both sides.
# Regen is computed on hp_total (pre-PvP), not on the ×5 pool.
PVP_HP_MULTIPLIER        = 5.0
PVP_RESOLUTION_EPSILON   = 1e-5   # HP% tie threshold at timeout

# ── Attack timing (windup-style) ────────────────────────────
# One hit takes ATTACK_INTERVAL seconds, reducible by attack_speed:
#   swing_time = ATTACK_INTERVAL * (2 if double_hit else 1) / speed_mult
ATTACK_INTERVAL          = 0.25

# ── Skill timing ────────────────────────────────────────────
# Fixed base delay before a skill's FIRST cast (same for all
# skills). The skill_cooldown stat does NOT reduce this delay —
# it only scales the library cooldown between subsequent casts.
INITIAL_SKILL_DELAY      = 3.8

# Multi-hit "pure damage" skills release all their hits within
# this window (seconds) after the cast starts. Exception:
# damage skills with buff_duration > 0 (e.g. Drone) spread
# their hits over buff_duration instead, and their cooldown
# only begins once all hits have fired.
CAST_BURST_DURATION      = 2.0

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

# ── Skills schema (chantier b) ──────────────────────────────
#
# A skill slot holds:
#   - identity     : __name__, __rarity__, __level__, type
#   - active part  : damage (per hit), hits, cooldown,
#                    buff_duration, buff_atk, buff_hp
#   - passive part : passive_damage (always-on +Base Damage),
#                    passive_hp     (always-on +Base Health)
#
# Library entries (Lv.1) hold the same keys minus the leading-underscore
# identity ones (rarity/type are stored as plain keys).
SKILL_NUMERIC_KEYS = [
    "damage", "hits", "cooldown",
    "buff_duration", "buff_atk", "buff_hp",
    "passive_damage", "passive_hp",
]
SKILL_IDENTITY_KEYS = ("__name__", "__rarity__", "__level__")
SKILL_TYPE_DAMAGE = "damage"
SKILL_TYPE_BUFF   = "buff"

# Lv.1 always-on passives, keyed by rarity tier (×8 per tier).
# +10 / +80 at Common up to +328k / +2.62M at Mythic.
SKILL_PASSIVE_LV1 = {
    "common":    {"passive_damage":      10.0, "passive_hp":         80.0},
    "rare":      {"passive_damage":      80.0, "passive_hp":        640.0},
    "epic":      {"passive_damage":     640.0, "passive_hp":      5_120.0},
    "legendary": {"passive_damage":   5_120.0, "passive_hp":     40_960.0},
    "ultimate":  {"passive_damage":  40_960.0, "passive_hp":    327_680.0},
    "mythic":    {"passive_damage": 327_680.0, "passive_hp":  2_621_440.0},
}

# Percentage stats shared by profile / equipment / companion
PERCENT_STATS_KEYS = [
    "crit_chance", "crit_damage", "health_regen", "lifesteal",
    "double_chance", "attack_speed", "skill_damage",
    "skill_cooldown", "block_chance",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
]
