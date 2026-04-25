"""
============================================================
  FORGE MASTER — Enemy stat calculator

  Recompute an opponent's HP and Damage from the ground up
  using the same formulas as the in-game ``StatEngine``. Game
  reference data is loaded from ``data/`` via
  ``backend.enemy_libraries``.

  Why recompute when the OCR already reads the displayed
  totals? Because the OCR is unreliable on multi-digit values
  with k/m/b suffixes and on highly stylised numerals. By
  identifying the gear (icons + levels) and replaying the
  formula we get a stable, validated total — and we get it
  even when the OCR misreads the headline numbers.

  Pipeline (no Tech Tree, no Ascension, no Skin/Set — none of
  these are visible to the OCR):

      base_dmg / base_hp
        + items (Σ EquipmentStats × 1.01^(level-1))
        + pets  (LevelInfo[level-1] × type_multi)
        + mount (LevelInfo[level-1])
        + skill passives (LevelStats[level-1])

      → split weapon vs other items so weapon × 1.6 if melee
      → multiply by (1 + DamageMulti substat) globally
      → multiply by (1 + Melee/RangedDamageMulti substat) finally

  The function is pure: it takes an ``EnemyIdentifiedProfile``
  + the JSON libraries and returns an ``EnemyComputedStats``.
============================================================
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

from .enemy_ocr_types import (
    EnemyComputedStats,
    EnemyIdentifiedProfile,
    IdentifiedItem,
    SLOT_TO_JSON_TYPE,
)

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  JSON key helpers
# ────────────────────────────────────────────────────────────
#
# The reference JSONs (ItemBalancingLibrary, WeaponLibrary, etc.)
# use string-encoded Python dicts as their keys. We must reproduce
# them BIT-FOR-BIT — including the single quotes and the spaces
# around the commas — to match the exact strings that statEngine.ts
# builds.

def _item_key(age: int, type_name: str, idx: int) -> str:
    return "{'Age': %d, 'Type': '%s', 'Idx': %d}" % (age, type_name, idx)


def _pet_key(rarity: str, pet_id: int) -> str:
    return "{'Rarity': '%s', 'Id': %d}" % (rarity, pet_id)


def _level_info_for(upgrade_data: Any, level: int) -> Any:
    """Pet/Mount/Skill upgrade libraries are keyed by rarity, then
    have a list of LevelInfo entries with a 0-indexed ``Level``
    field. The user-facing level is 1-indexed, so we look for
    ``Level == level - 1`` and fall back to the first entry on
    miss (matches the TS reference behaviour).
    """
    if not isinstance(upgrade_data, dict):
        return None
    info_list = upgrade_data.get("LevelInfo")
    if not isinstance(info_list, list) or not info_list:
        return None

    target = max(0, int(level) - 1)
    for entry in info_list:
        if isinstance(entry, dict) and entry.get("Level") == target:
            return entry
    return info_list[0]


def _stat_type(stat_node_wrapper: Any) -> str:
    """Extract ``StatNode.UniqueStat.StatType`` defensively."""
    if not isinstance(stat_node_wrapper, dict):
        return ""
    stat_node = stat_node_wrapper.get("StatNode") or {}
    unique = stat_node.get("UniqueStat") or {}
    return str(unique.get("StatType") or "")


# ────────────────────────────────────────────────────────────
#  Per-bucket aggregations
# ────────────────────────────────────────────────────────────


def _aggregate_items(
    items: list[IdentifiedItem],
    item_balancing_library: dict,
    weapon_library: dict,
    projectiles_library: dict,
    level_scaling_base: float,
) -> Dict[str, float]:
    """Sum item Damage/Health and extract weapon meta data.

    Returns a dict with keys: ``item_damage``, ``item_health``,
    ``weapon_damage``, ``is_ranged``, ``weapon_range``,
    ``weapon_windup``, ``weapon_duration``, ``projectile_speed``.
    """
    item_damage = 0.0
    item_health = 0.0
    weapon_damage = 0.0
    is_ranged = False
    weapon_range = 0.3
    weapon_windup = 0.5
    weapon_duration = 1.5
    projectile_speed = 0.0

    for item in items:
        json_type = SLOT_TO_JSON_TYPE.get(item.slot, item.slot)
        key = _item_key(item.age, json_type, item.idx)
        item_data = item_balancing_library.get(key)
        if not isinstance(item_data, dict):
            log.debug("calculator: item not found %s", key)
            continue

        equip_stats = item_data.get("EquipmentStats") or []
        level_factor = math.pow(level_scaling_base, max(0, int(item.level) - 1))

        dmg = 0.0
        hp = 0.0
        for stat in equip_stats:
            stype = _stat_type(stat)
            value = float(stat.get("Value") or 0.0) * level_factor
            if stype == "Damage":
                dmg += value
            elif stype == "Health":
                hp += value

        item_damage += dmg
        item_health += hp

        if item.slot == "Weapon":
            weapon_damage = dmg
            w_key = _item_key(item.age, "Weapon", item.idx)
            w_data = weapon_library.get(w_key)
            if isinstance(w_data, dict):
                attack_range = float(w_data.get("AttackRange") or 0.0)
                is_ranged = attack_range >= 1.0
                weapon_range = attack_range or weapon_range
                weapon_windup = float(w_data.get("WindupTime") or weapon_windup)
                weapon_duration = float(w_data.get("AttackDuration") or weapon_duration)
                proj_id = w_data.get("ProjectileId")
                if isinstance(proj_id, int) and proj_id > -1:
                    proj = projectiles_library.get(str(proj_id))
                    if isinstance(proj, dict):
                        projectile_speed = float(proj.get("Speed") or 0.0)

    return {
        "item_damage": item_damage,
        "item_health": item_health,
        "weapon_damage": weapon_damage,
        "is_ranged": is_ranged,
        "weapon_range": weapon_range,
        "weapon_windup": weapon_windup,
        "weapon_duration": weapon_duration,
        "projectile_speed": projectile_speed,
    }


def _aggregate_pets(
    pets, pet_library: dict, pet_upgrade_library: dict, pet_balancing_library: dict
) -> Dict[str, float]:
    pet_damage = 0.0
    pet_health = 0.0

    for pet in pets:
        upgrade = pet_upgrade_library.get(pet.rarity)
        level_info = _level_info_for(upgrade, pet.level)
        if not isinstance(level_info, dict):
            continue
        stats_block = (level_info.get("PetStats") or {}).get("Stats") or []

        pet_data = pet_library.get(_pet_key(pet.rarity, pet.id)) or {}
        pet_type = pet_data.get("Type") or "Balanced"
        type_multi = pet_balancing_library.get(pet_type) or {
            "DamageMultiplier": 1.0, "HealthMultiplier": 1.0,
        }
        dmg_multi = float(type_multi.get("DamageMultiplier", 1.0))
        hp_multi = float(type_multi.get("HealthMultiplier", 1.0))

        for stat in stats_block:
            stype = _stat_type(stat)
            value = float(stat.get("Value") or 0.0)
            if stype == "Damage":
                pet_damage += value * dmg_multi
            elif stype == "Health":
                pet_health += value * hp_multi

    return {"pet_damage": pet_damage, "pet_health": pet_health}


def _aggregate_mount(mount, mount_upgrade_library: dict) -> Dict[str, float]:
    if mount is None:
        return {"mount_damage": 0.0, "mount_health": 0.0}

    upgrade = mount_upgrade_library.get(mount.rarity)
    level_info = _level_info_for(upgrade, mount.level)
    if not isinstance(level_info, dict):
        return {"mount_damage": 0.0, "mount_health": 0.0}

    stats_block = (level_info.get("MountStats") or {}).get("Stats") or []
    mount_damage = 0.0
    mount_health = 0.0
    for stat in stats_block:
        stype = _stat_type(stat)
        value = float(stat.get("Value") or 0.0)
        if stype == "Damage":
            mount_damage += value
        elif stype == "Health":
            mount_health += value

    return {"mount_damage": mount_damage, "mount_health": mount_health}


def _aggregate_skill_passives(
    skills, skill_library: dict, skill_passive_library: dict
) -> Dict[str, float]:
    """Skill passives contribute FLAT (additive) Damage/Health.

    Per the TS reference, each skill's contribution is floored
    independently before summing — the game rounds before display.
    """
    passive_damage = 0
    passive_health = 0

    for skill in skills:
        skill_data = skill_library.get(skill.id)
        if not isinstance(skill_data, dict):
            continue
        rarity = skill.rarity or skill_data.get("Rarity") or "Common"

        passive_data = skill_passive_library.get(rarity)
        if not isinstance(passive_data, dict):
            continue
        level_stats = passive_data.get("LevelStats") or []
        if not level_stats:
            continue
        idx = max(0, min(int(skill.level) - 1, len(level_stats) - 1))
        level_info = level_stats[idx]
        stats_block = (level_info or {}).get("Stats") or []

        skill_dmg = 0.0
        skill_hp = 0.0
        for stat in stats_block:
            stype = _stat_type(stat)
            value = float(stat.get("Value") or 0.0)
            if stype == "Damage":
                skill_dmg += value
            elif stype == "Health":
                skill_hp += value
        passive_damage += int(math.floor(skill_dmg))
        passive_health += int(math.floor(skill_hp))

    return {
        "skill_passive_damage": float(passive_damage),
        "skill_passive_health": float(passive_health),
    }


# ────────────────────────────────────────────────────────────
#  Public entry point
# ────────────────────────────────────────────────────────────


def calculate_enemy_stats(
    profile: EnemyIdentifiedProfile,
    libs: Dict[str, Any],
) -> EnemyComputedStats:
    """Recompute HP, Damage and combat substats for one opponent.

    ``libs`` is the dict returned by ``enemy_libraries.load_libs()``.

    The returned object always has ``displayed_*`` and ``*_accuracy``
    populated so callers can sanity-check the recomputation against
    what the OCR actually read.
    """
    config = libs.get("item_balancing_config") or {}
    base_damage = float(config.get("PlayerBaseDamage") or 10.0)
    base_health = float(config.get("PlayerBaseHealth") or 80.0)
    base_crit_damage = float(config.get("PlayerBaseCritDamage") or 0.20)
    melee_multiplier = float(config.get("PlayerMeleeDamageMultiplier") or 1.6)
    level_scaling_base = float(config.get("LevelScalingBase") or 1.01)

    item_balancing_library = libs.get("item_balancing_library") or {}
    weapon_library = libs.get("weapon_library") or {}
    projectiles_library = libs.get("projectiles_library") or {}
    pet_library = libs.get("pet_library") or {}
    pet_upgrade_library = libs.get("pet_upgrade_library") or {}
    pet_balancing_library = libs.get("pet_balancing_library") or {}
    mount_upgrade_library = libs.get("mount_upgrade_library") or {}
    skill_library = libs.get("skill_library") or {}
    skill_passive_library = libs.get("skill_passive_library") or {}

    items_agg = _aggregate_items(
        profile.items,
        item_balancing_library,
        weapon_library,
        projectiles_library,
        level_scaling_base,
    )
    pets_agg = _aggregate_pets(
        profile.pets, pet_library, pet_upgrade_library, pet_balancing_library,
    )
    mount_agg = _aggregate_mount(profile.mount, mount_upgrade_library)
    skill_agg = _aggregate_skill_passives(
        profile.skills, skill_library, skill_passive_library,
    )

    # ── Substats from OCR (already aggregated globally) ──────
    # Game prints values as "+50.1%" — i.e. percentage points. The
    # calculator works in decimal multipliers, so /100 here.
    pp = profile.substat                         # alias
    damage_multi          = pp("DamageMulti") / 100.0
    health_multi          = pp("HealthMulti") / 100.0
    melee_damage_multi    = pp("MeleeDamageMulti") / 100.0
    ranged_damage_multi   = pp("RangedDamageMulti") / 100.0
    crit_chance           = pp("CriticalChance") / 100.0
    crit_damage_extra     = pp("CriticalDamage") / 100.0
    block_chance          = pp("BlockChance") / 100.0
    double_chance         = pp("DoubleDamageChance") / 100.0
    attack_speed          = pp("AttackSpeed") / 100.0
    life_steal            = pp("LifeSteal") / 100.0
    health_regen          = pp("HealthRegen") / 100.0
    skill_damage_multi    = pp("SkillDamageMulti") / 100.0
    skill_cooldown_multi  = pp("SkillCooldownMulti") / 100.0

    # ── Damage finalisation (mirrors finalizeCalculation) ────
    is_ranged = bool(items_agg["is_ranged"])
    weapon_dmg = items_agg["weapon_damage"]
    item_dmg = items_agg["item_damage"]
    item_hp  = items_agg["item_health"]

    weapon_with_melee = weapon_dmg if is_ranged else weapon_dmg * melee_multiplier
    other_item_damage = item_dmg - weapon_dmg

    common_damage_multi = 1.0 + damage_multi
    common_health_multi = 1.0 + health_multi
    # No Forge Ascension data ⇒ equip multi == common multi
    equip_damage_multi = common_damage_multi
    equip_health_multi = common_health_multi

    equip_contrib_dmg = (base_damage + weapon_with_melee + other_item_damage) * equip_damage_multi
    system_contrib_dmg = (
        pets_agg["pet_damage"]
        + skill_agg["skill_passive_damage"]
        + mount_agg["mount_damage"]
    ) * common_damage_multi

    equip_contrib_hp = (base_health + item_hp) * equip_health_multi
    pet_contrib_hp    = pets_agg["pet_health"]            * common_health_multi
    skill_contrib_hp  = skill_agg["skill_passive_health"] * common_health_multi
    mount_contrib_hp  = mount_agg["mount_health"]         * common_health_multi
    system_contrib_hp = pet_contrib_hp + skill_contrib_hp + mount_contrib_hp

    damage_before_global = equip_contrib_dmg + system_contrib_dmg
    health_before_global = equip_contrib_hp + system_contrib_hp

    # Skin/Set: not visible to OCR — defaults to neutral (×1).
    skin_damage_factor = 1.0
    skin_health_factor = 1.0

    damage_after_global = damage_before_global * skin_damage_factor
    health_after_global = health_before_global * skin_health_factor

    specific_damage_multi = (
        1.0 + (ranged_damage_multi if is_ranged else melee_damage_multi)
    )
    final_damage = damage_after_global * specific_damage_multi
    final_health = health_after_global

    # Per-bucket HP sub-totals after the same skin factor as the
    # aggregate. Used downstream by simulation.pvp_hp_total to
    # apply the per-source PvP weighting (1.0 / 0.5 / 0.5 / 2.0).
    equip_health_final = equip_contrib_hp * skin_health_factor
    pet_health_final   = pet_contrib_hp   * skin_health_factor
    skill_health_final = skill_contrib_hp * skin_health_factor
    mount_health_final = mount_contrib_hp * skin_health_factor

    # ── Validation ───────────────────────────────────────────
    displayed_dmg = float(profile.total_damage_displayed or 0.0)
    displayed_hp  = float(profile.total_health_displayed or 0.0)

    dmg_acc = abs(final_damage - displayed_dmg) / displayed_dmg * 100.0 if displayed_dmg > 0 else 0.0
    hp_acc  = abs(final_health - displayed_hp)  / displayed_hp  * 100.0 if displayed_hp  > 0 else 0.0

    return EnemyComputedStats(
        total_damage=final_damage,
        total_health=final_health,
        equip_health=equip_health_final,
        pet_health=pet_health_final,
        mount_health=mount_health_final,
        skill_passive_health=skill_health_final,
        critical_chance=crit_chance,
        critical_damage=1.0 + base_crit_damage + crit_damage_extra,
        block_chance=block_chance,
        double_damage_chance=double_chance,
        attack_speed_multiplier=1.0 + attack_speed,
        life_steal=life_steal,
        health_regen=health_regen,
        skill_damage_multiplier=1.0 + skill_damage_multi,
        skill_cooldown_reduction=skill_cooldown_multi,
        is_ranged_weapon=is_ranged,
        weapon_attack_range=items_agg["weapon_range"],
        weapon_windup_time=items_agg["weapon_windup"],
        weapon_attack_duration=items_agg["weapon_duration"],
        projectile_speed=items_agg["projectile_speed"],
        displayed_damage=displayed_dmg,
        displayed_health=displayed_hp,
        damage_accuracy=dmg_acc,
        health_accuracy=hp_acc,
    )
