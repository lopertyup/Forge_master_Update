"""
============================================================
  FORGE MASTER — Stats math (pure, no I/O)
  Transformations on profile dictionaries: applying
  equipment, companions, finalizing, etc.

  This module does the math; simulation.py does the fight.
============================================================
"""

import math
from typing import Dict, Optional

from .constants import (
    ATTACK_INTERVAL,
    PERCENT_STATS_KEYS,
    PVP_HP_MULTIPLIER,
)


# ════════════════════════════════════════════════════════════
#  DERIVED SCALARS
# ════════════════════════════════════════════════════════════

# Fixed post-attack window the game adds at the end of every
# basic attack — applied AFTER the wind-up + recovery phases
# have been stepped down to the nearest 0.1 s. This is the same
# constant in every age and weapon class.
POST_ATTACK_FIXED = 0.2

# Sequential delay between the two hits of a double-attack swing,
# also subject to 0.1 s rounding by the in-game tick.
DOUBLE_ATTACK_GAP = 0.25


def speed_mult(attack_speed_pct: float) -> float:
    """% attack_speed → raw multiplier applied to the swing duration."""
    return 1.0 + (attack_speed_pct or 0.0) / 100.0


def crit_multi(crit_damage_pct: float) -> float:
    """% crit_damage → damage multiplier applied on a crit roll."""
    return 1.172 + (crit_damage_pct or 0.0) / 99.0


# ────────────────────────────────────────────────────────────
#  Attack-speed cycle helpers
# ────────────────────────────────────────────────────────────
#
#  The game does NOT scale attack speed continuously: it floors
#  the wind-up and the recovery to the nearest 0.1 s SEPARATELY
#  before adding the constant 0.2 s post-attack window. As a
#  result the DPS curve is staircase-shaped — there are discrete
#  "breakpoints" of attack speed where the cycle drops by 0.1 s
#  and missing one by a hair brings no improvement.
#
#  Two flavours below:
#    * swing_time_discrete()  — single-hit cycle
#    * swing_time_double()    — double-hit cycle (one extra
#      sequential 0.25 s gap, also stepped)
#
#  The legacy linear helper swing_time() now dispatches to the
#  discrete formula when wind-up / recovery are provided, and
#  preserves the old behaviour when they are not (so older code
#  paths and tests calling swing_time(pct) keep working).
# ────────────────────────────────────────────────────────────


def _step_down(value: float) -> float:
    """Floor ``value`` to the nearest 0.1 s tick, never below zero."""
    if value <= 0:
        return 0.0
    return math.floor(value * 10.0) / 10.0


def swing_time_discrete(
    windup: float,
    recovery: float,
    attack_speed_pct: float = 0.0,
) -> float:
    """Real cycle time of a single basic attack (in seconds).

    Formula::

        m  = 1 + attack_speed_pct / 100
        sw = floor(windup / m * 10) / 10
        sr = floor(recovery / m * 10) / 10
        cycle = sw + sr + 0.2
    """
    mult = speed_mult(attack_speed_pct)
    if mult <= 0:
        mult = 1.0
    sw = _step_down(windup / mult)
    sr = _step_down(recovery / mult)
    return sw + sr + POST_ATTACK_FIXED


def swing_time_double(
    windup: float,
    recovery: float,
    attack_speed_pct: float = 0.0,
) -> float:
    """Double-attack cycle: single cycle + a stepped 0.25 s gap.

    The second hit is fired sequentially after a 0.25 s window
    that is also subject to the 0.1 s tick. The fixed 0.2 s
    post-attack delay is added a second time after the second
    hit.
    """
    mult = speed_mult(attack_speed_pct)
    if mult <= 0:
        mult = 1.0
    base = swing_time_discrete(windup, recovery, attack_speed_pct)
    gap  = _step_down(DOUBLE_ATTACK_GAP / mult)
    return base + gap + POST_ATTACK_FIXED


def swing_time(
    attack_speed_pct: float,
    windup: Optional[float]   = None,
    recovery: Optional[float] = None,
) -> float:
    """Cycle time of one basic-attack swing.

    Two modes:
      * Legacy (windup/recovery omitted): falls back to the linear
        ``ATTACK_INTERVAL / speed_mult`` formula. This keeps
        every existing simulator code path working unchanged.
      * Discrete (both windup and recovery supplied): uses
        :func:`swing_time_discrete` with the 0.1 s breakpoint
        rounding.

    A double-hit swing takes :func:`swing_time_double` seconds in
    the discrete mode, or twice the legacy value otherwise — the
    simulator handles the doubling itself today.
    """
    if windup is not None and recovery is not None:
        return swing_time_discrete(float(windup), float(recovery),
                                   attack_speed_pct)
    return ATTACK_INTERVAL / speed_mult(attack_speed_pct)


# ════════════════════════════════════════════════════════════
#  PROFILE FINALIZATION
# ════════════════════════════════════════════════════════════

def finalize_bases(profile: Dict) -> Dict:
    """
    Compute attack_base from attack_total and percentages.
    Mutates and returns the profile.
    """
    atk_type   = profile.get("attack_type", "melee")
    damage_pct = profile.get("damage_pct", 0.0)
    melee_pct  = profile.get("melee_pct", 0.0)
    ranged_pct = profile.get("ranged_pct", 0.0)

    bonus = damage_pct + (ranged_pct if atk_type == "ranged" else melee_pct)
    total = profile.get("attack_total", 0.0)
    profile["attack_base"] = total / (1 + bonus / 100) if bonus else total
    return profile


def combat_stats(profile: Dict) -> Dict:
    """Extract the stats needed to simulate a fight.

    Uses ``.get()`` with zero defaults for numeric fields so a
    partially-filled profile (e.g. a fresh install where OCR has
    only captured some stats yet) does not KeyError halfway
    through a background simulation thread — the simulator will
    simply treat missing stats as zero.

    Wind-up / recovery come from the WeaponLibrary; they default
    to ``None`` here so the simulator can fall back to the legacy
    linear timing when they are unavailable.
    """
    return {
        "hp_total":        profile.get("hp_total",       0.0),
        "attack_total":    profile.get("attack_total",   0.0),
        "crit_chance":     profile.get("crit_chance",    0.0),
        "crit_damage":     profile.get("crit_damage",    0.0),
        "health_regen":    profile.get("health_regen",   0.0),
        "lifesteal":       profile.get("lifesteal",      0.0),
        "double_chance":   profile.get("double_chance",  0.0),
        "attack_speed":    profile.get("attack_speed",   0.0),
        "skill_damage":    profile.get("skill_damage",   0.0),
        "skill_cooldown":  profile.get("skill_cooldown", 0.0),
        "block_chance":    profile.get("block_chance",   0.0),
        "attack_type":     profile.get("attack_type",    "melee"),
        "weapon_windup":   profile.get("weapon_windup"),
        "weapon_recovery": profile.get("weapon_recovery"),
        # Travel time of the weapon's projectile in seconds. 0.0 for
        # melee or unknown weapons; > 0 for ranged. The simulator
        # queues a deferred impact when this is > 0 so a slow
        # projectile (Tomahawk, Rock) doesn't deal damage on the
        # same tick the swing was released.
        "projectile_travel_time": profile.get("projectile_travel_time", 0.0),
    }


def _recompute_totals(profile: Dict) -> None:
    """Recompute hp_total and attack_total from bases and percentages."""
    profile["hp_total"] = profile["hp_base"] * (1 + profile["health_pct"] / 100)

    atk_type = profile.get("attack_type", "melee")
    bonus = profile["damage_pct"] + (
        profile["ranged_pct"] if atk_type == "ranged" else profile["melee_pct"])
    profile["attack_total"] = profile["attack_base"] * (1 + bonus / 100)


# ════════════════════════════════════════════════════════════
#  SWAP HELPERS (equipment / companion / skill)
# ════════════════════════════════════════════════════════════

def apply_change(profile: Dict, old_eq: Dict, new_eq: Dict) -> Dict:
    """Replace one equipment piece with another. Returns a new dict."""
    new = dict(profile)

    for k in PERCENT_STATS_KEYS:
        new[k] = round(
            profile.get(k, 0.0) - old_eq.get(k, 0.0) + new_eq.get(k, 0.0), 6)

    if new_eq.get("attack_type") is not None:
        new["attack_type"] = new_eq["attack_type"]

    new["hp_base"]     = profile["hp_base"]     - old_eq.get("hp_flat",     0) + new_eq.get("hp_flat",     0)
    new["attack_base"] = profile["attack_base"] - old_eq.get("damage_flat", 0) + new_eq.get("damage_flat", 0)

    _recompute_totals(new)
    return new


def apply_companion(profile: Dict, old: Dict, new_c: Dict) -> Dict:
    """Replace a pet or mount with another. Returns a new dict."""
    new = dict(profile)

    for k in PERCENT_STATS_KEYS:
        new[k] = round(
            profile.get(k, 0.0) - old.get(k, 0.0) + new_c.get(k, 0.0), 6)

    new["hp_base"]     = profile["hp_base"]     - old.get("hp_flat",     0) + new_c.get("hp_flat",     0)
    new["attack_base"] = profile["attack_base"] - old.get("damage_flat", 0) + new_c.get("damage_flat", 0)

    _recompute_totals(new)
    return new


def apply_skill(profile: Dict, old: Dict, new_s: Dict) -> Dict:
    """
    Replace one equipped skill with another. Only the always-on
    PASSIVE part (passive_damage / passive_hp) feeds into the
    profile — the active part (damage/hits/cooldown/buff_*) is
    consumed at simulation time by SkillInstance.
    """
    new = dict(profile)
    new["hp_base"]     = profile["hp_base"]     - float(old.get("passive_hp",     0.0)) + float(new_s.get("passive_hp",     0.0))
    new["attack_base"] = profile["attack_base"] - float(old.get("passive_damage", 0.0)) + float(new_s.get("passive_damage", 0.0))
    _recompute_totals(new)
    return new


# Back-compat aliases
apply_pet   = apply_companion
apply_mount = apply_companion


# ════════════════════════════════════════════════════════════
#  PvP SCALARS
# ════════════════════════════════════════════════════════════

def pvp_hp_total(stats: Dict) -> float:
    """Final HP pool used as the fighter's hp_max: ``hp_total × 5``."""
    return float(stats.get("hp_total", 0.0) or 0.0) * PVP_HP_MULTIPLIER


def pvp_regen_per_second(stats: Dict) -> float:
    """
    Regen amount per second. Computed on the PRE-PvP HP (hp_total),
    not on the ×5 pool, so it's weaker in relative terms. Only kicks
    in while the fighter is below its current hp_max (handled by the
    simulator).
    """
    hp_total  = float(stats.get("hp_total",     0.0) or 0.0)
    regen_pct = float(stats.get("health_regen", 0.0) or 0.0)
    return hp_total * regen_pct / 100.0
 amount per second. Computed on the PRE-PvP HP (hp_total),
    not on the ×5 pool, so it's weaker in relative terms. Only kicks
    in while the fighter is below its current hp_max (handled by the
    simulator).
    """
    hp_total  = float(stats.get("hp_total",     0.0) or 0.0)
    regen_pct = float(stats.get("health_regen", 0.0) or 0.0)
    return hp_total * regen_pct / 100.0
