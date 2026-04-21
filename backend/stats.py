"""
============================================================
  FORGE MASTER — Stats math (pure, no I/O)
  Transformations on profile dictionaries: applying
  equipment, companions, finalizing, etc.
============================================================
"""

from typing import Dict

from .constants import PERCENT_STATS_KEYS


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
    """Extract the stats needed to simulate a fight."""
    return {
        "hp":              profile["hp_total"],
        "attack":          profile["attack_total"],
        "crit_chance":     profile["crit_chance"],
        "crit_damage":     profile["crit_damage"],
        "health_regen":    profile["health_regen"],
        "lifesteal":       profile["lifesteal"],
        "double_chance":   profile["double_chance"],
        "attack_speed":    profile["attack_speed"],
        "skill_damage":    profile["skill_damage"],
        "skill_cooldown":  profile["skill_cooldown"],
        "block_chance":    profile["block_chance"],
        "attack_type":     profile["attack_type"],
    }


def _recompute_totals(profile: Dict) -> None:
    """Recompute hp_total and attack_total from bases and percentages."""
    profile["hp_total"] = profile["hp_base"] * (1 + profile["health_pct"] / 100)

    atk_type = profile.get("attack_type", "melee")
    bonus = profile["damage_pct"] + (
        profile["ranged_pct"] if atk_type == "ranged" else profile["melee_pct"])
    profile["attack_total"] = profile["attack_base"] * (1 + bonus / 100)


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


# Back-compat aliases
apply_pet   = apply_companion
apply_mount = apply_companion
