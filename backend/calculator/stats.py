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

from ..constants import (
    ATTACK_INTERVAL,
    PERCENT_STATS_KEYS,
    PVP_HP_BASE_MULTIPLIER,
    PVP_HP_MOUNT_MULTIPLIER,
    PVP_HP_MULTIPLIER,
    PVP_HP_PET_MULTIPLIER,
    PVP_HP_SKILL_MULTIPLIER,
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

    Confirmed against the in-game UI: a double swing is one full
    single cycle (windup + recovery + 0.2 s post) plus a stepped
    0.25 s sequential gap to the second hit. The 0.2 s post-attack
    window is *not* paid a second time -- the next swing starts
    immediately after the second projectile is fired.
    """
    mult = speed_mult(attack_speed_pct)
    if mult <= 0:
        mult = 1.0
    base = swing_time_discrete(windup, recovery, attack_speed_pct)
    gap  = _step_down(DOUBLE_ATTACK_GAP / mult)
    return base + gap


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
        # Per-source HP sub-totals AFTER health_pct is applied.
        # Optional -- when absent the simulator falls back to the
        # legacy single-multiplier path on hp_total. The controller
        # injects them via compute_hp_buckets() so the PvP engine
        # can apply 1.0 / 0.5 / 0.5 / 2.0 to equip / pet / skill /
        # mount independently.
        "hp_equip":          profile.get("hp_equip"),
        "hp_pet":            profile.get("hp_pet"),
        "hp_mount":          profile.get("hp_mount"),
        "hp_skill_passive":  profile.get("hp_skill_passive"),
        # Travel time of the weapon's projectile in seconds. 0.0 for
        # melee or unknown weapons; > 0 for ranged. The simulator
        # queues a deferred impact when this is > 0 so a slow
        # projectile (Tomahawk, Rock) doesn't deal damage on the
        # same tick the swing was released.
        "projectile_travel_time": profile.get("projectile_travel_time", 0.0),
    }


def compute_hp_buckets(
    profile:   Dict,
    pets:      Optional[Dict[str, Dict]] = None,
    mount:     Optional[Dict] = None,
    skills:    Optional[list] = None,
    equipment: Optional[Dict[str, Dict]] = None,
) -> Dict[str, float]:
    """Decompose ``profile.hp_total`` into 4 source buckets.

    Pets, mount and skill passives store their HP contributions
    individually (``hp_flat`` for companions, ``passive_hp`` for
    skills). The equipment bucket is computed in one of two ways:

      * If ``equipment`` is provided (a dict of 8 EQUIP_* slots,
        each with ``hp_flat``), its sum + the 80 HP player base is
        used directly. This is the preferred path -- it removes the
        legacy subtraction and matches the game's TS calculation.
      * Otherwise, the equipment bucket is derived by subtraction
        ``hp_base - pet_pre - mount_pre - skill_pre`` (legacy).

    Each bucket is then scaled by ``(1 + health_pct/100)`` -- the
    same global multiplier the game applies on the in-game Total HP
    display -- so the four returned values sum back to ``hp_total``
    when the inputs are consistent.

    Returns ``{"hp_equip", "hp_pet", "hp_mount", "hp_skill_passive"}``,
    every value in absolute (post-percentage) HP units. Caller may
    inject this dict directly into the combat stats dict; the
    simulator picks them up and applies the per-source PvP
    weighting.
    """
    hp_base = float(profile.get("hp_base", 0.0) or 0.0)

    pet_pre = 0.0
    if isinstance(pets, dict):
        for entry in pets.values():
            if isinstance(entry, dict):
                pet_pre += float(entry.get("hp_flat", 0.0) or 0.0)

    mount_pre = 0.0
    if isinstance(mount, dict):
        mount_pre = float(mount.get("hp_flat", 0.0) or 0.0)

    skill_pre = 0.0
    if skills:
        for item in skills:
            data = item[1] if isinstance(item, tuple) else item
            if isinstance(data, dict):
                skill_pre += float(data.get("passive_hp", 0.0) or 0.0)

    # Preferred path: sum the equipment-piece hp_flat directly when
    # the 8-slot Build is known. ``equipment`` is the dict returned
    # by GameController.get_equipment(), keyed by EQUIP_*. Slots
    # with no piece equipped store hp_flat == 0 / None and contribute
    # nothing.
    equip_known = False
    equip_pre = 0.0
    if isinstance(equipment, dict):
        equip_pieces_sum = 0.0
        any_piece = False
        for entry in equipment.values():
            if not isinstance(entry, dict):
                continue
            hp_flat = entry.get("hp_flat") or 0.0
            try:
                hp_flat = float(hp_flat)
            except (TypeError, ValueError):
                hp_flat = 0.0
            if hp_flat > 0.0:
                any_piece = True
            equip_pieces_sum += hp_flat
        if any_piece:
            # 80 HP is the PlayerBaseHealth from ItemBalancingConfig --
            # it is part of the equipment-side pool in the TS engine.
            equip_pre   = equip_pieces_sum + 80.0
            equip_known = True

    if not equip_known:
        equip_pre = hp_base - pet_pre - mount_pre - skill_pre
        if equip_pre < 0.0:
            equip_pre = 0.0

    mult = 1.0 + float(profile.get("health_pct", 0.0) or 0.0) / 100.0
    return {
        "hp_equip":         equip_pre  * mult,
        "hp_pet":           pet_pre    * mult,
        "hp_mount":         mount_pre  * mult,
        "hp_skill_passive": skill_pre  * mult,
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


def apply_change_flat_only(profile: Dict, old_eq: Dict, new_eq: Dict) -> Dict:
    """Swap only the FLAT hp/damage of an equipment piece.

    Used by the comparator when the equipped piece is taken from the
    persisted profile_store -- which caches level-scaled hp_flat /
    damage_flat / attack_type, but NOT per-piece substats (those still
    live aggregated in the profile store). Substat fields on the profile are
    therefore left untouched, and the candidate's substats are
    SHOWN but not folded back in.

    The simulator still gets a meaningful new profile: the flat HP and
    flat damage swap reflects the upgrade, while the % substats stay
    as the player's CURRENT totals -- which is the most honest answer
    we can produce until per-piece substats are tracked.
    """
    new = dict(profile)

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
    profile -- the active part (damage/hits/cooldown/buff_*) is
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
    """Final HP pool used as the fighter's hp_max.

    Two paths:
      * Per-source weighted sum (preferred). When the combat
        stats dict carries the four sub-totals -- hp_equip,
        hp_pet, hp_mount, hp_skill_passive -- the pool is:

            equip * PVP_HP_BASE_MULTIPLIER
          + pet   * PVP_HP_PET_MULTIPLIER
          + skill * PVP_HP_SKILL_MULTIPLIER
          + mount * PVP_HP_MOUNT_MULTIPLIER

        which mirrors data/PvpBaseConfig.json (1.0 / 0.5 / 0.5 /
        2.0). The controller fills these via compute_hp_buckets
        before each simulate(); the enemy pipeline fills them in
        EnemyComputedStats.
      * Legacy fallback. When none of the four keys are present,
        the function falls back to hp_total * PVP_HP_MULTIPLIER
        with the historical 5.0 factor (back-compat for tests
        and partial profiles).
    """
    eq = stats.get("hp_equip")
    pe = stats.get("hp_pet")
    mo = stats.get("hp_mount")
    sk = stats.get("hp_skill_passive")
    if eq is None and pe is None and mo is None and sk is None:
        return float(stats.get("hp_total", 0.0) or 0.0) * PVP_HP_MULTIPLIER
    eq = float(eq or 0.0)
    pe = float(pe or 0.0)
    mo = float(mo or 0.0)
    sk = float(sk or 0.0)
    return (eq * PVP_HP_BASE_MULTIPLIER
            + pe * PVP_HP_PET_MULTIPLIER
            + sk * PVP_HP_SKILL_MULTIPLIER
            + mo * PVP_HP_MOUNT_MULTIPLIER)


def pvp_regen_per_second(stats: Dict) -> float:
    """Regen amount per second. Computed on the PRE-PvP HP
    (hp_total), not on the per-source pool, so it scales weaker
    in PvP. Only kicks in while the fighter is below its current
    hp_max (handled by the simulator).
    """
    hp_total  = float(stats.get("hp_total",     0.0) or 0.0)
    regen_pct = float(stats.get("health_regen", 0.0) or 0.0)
    return hp_total * regen_pct / 100.0
