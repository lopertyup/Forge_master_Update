"""
============================================================
  FORGE MASTER — Stats math (pure, no I/O)
  Transformations on profile dictionaries: applying
  equipment, companions, finalizing, etc.

  This module does the math; simulation.py does the fight.
============================================================
"""

from typing import Dict

from .constants import (
    ATTACK_INTERVAL,
    PERCENT_STATS_KEYS,
    PVP_HP_MULTIPLIER,
)


# ════════════════════════════════════════════════════════════
#  DERIVED SCALARS
# ════════════════════════════════════════════════════════════

def speed_mult(attack_speed_pct: float) -> float:
    """% attack_speed → raw multiplier applied to the swing duration."""
    return 1.0 + (attack_speed_pct or 0.0) / 100.0


def crit_multi(crit_damage_pct: float) -> float:
    """% crit_damage → damage multiplier applied on a crit roll."""
    return 1.172 + (crit_damage_pct or 0.0) / 99.0


def swing_time(attack_speed_pct: float) -> float:
    """
    Time (seconds) for ONE basic-attack swing, reducible by attack_speed.
    A double-hit swing takes twice this duration (simulation.py handles
    that by multiplying by 2 on the fly).
    """
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

    Uses `.get()` with zero defaults for numeric fields so a partially-
    filled profile (e.g. a fresh install where OCR has only captured
    some stats yet) does not KeyError halfway through a background
    simulation thread — the simulator will simply treat missing stats
    as zero.
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
    """Final HP pool used as the fighter's hp_max: `hp_total × 5`."""
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
