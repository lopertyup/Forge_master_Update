"""Legacy-compatible profile OCR text parser."""

from __future__ import annotations

from typing import Dict

from .common import extract, extract_flat


def parse_profile_text(text: str) -> Dict[str, float]:
    """Parse the player stat block copied from the game."""
    hp_total = extract_flat(text, [r"([\d.]+[km]?)\s*Total Health"])
    attack_total = extract_flat(text, [r"([\d.]+[km]?)\s*Total Damage"])
    health_pct = extract(text, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    damage_pct = extract(text, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    melee_pct = extract(text, [r"\+([\d. ]+)%\s*Melee Damage"])
    ranged_pct = extract(text, [r"\+([\d. ]+)%\s*Ranged Damage"])
    hp_base = hp_total / (1 + health_pct / 100) if health_pct else hp_total

    return {
        "hp_total": hp_total,
        "attack_total": attack_total,
        "hp_base": hp_base,
        "attack_base": attack_total,
        "health_pct": health_pct,
        "damage_pct": damage_pct,
        "melee_pct": melee_pct,
        "ranged_pct": ranged_pct,
        "crit_chance": extract(text, [r"\+([\d. ]+)%\s*Critical Chance"]),
        "crit_damage": extract(text, [r"\+([\d. ]+)%\s*Critical Damage"]),
        "health_regen": extract(text, [r"\+([\d. ]+)%\s*Health Regen"]),
        "lifesteal": extract(text, [r"\+([\d. ]+)%\s*Lifesteal"]),
        "double_chance": extract(text, [r"\+([\d. ]+)%\s*Double Chance"]),
        "attack_speed": extract(text, [r"\+([\d. ]+)%\s*Attack Speed"]),
        "skill_damage": extract(text, [r"\+([\d. ]+)%\s*Skill Damage"]),
        "skill_cooldown": extract(text, [r"([+-][\d. ]+)%\s*Skill Cooldown"]),
        "block_chance": extract(text, [r"\+([\d. ]+)%\s*Block Chance"]),
    }


__all__ = ["parse_profile_text"]
