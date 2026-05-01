"""OCR-only parser for pet and mount popups."""

from __future__ import annotations

from typing import Dict

import re

from .common import (
    _FLAT_RE,
    extract,
    extract_level,
    extract_substats,
    extract_tag_name,
    first_flat,
    missing_fields,
    normalise_tag,
    parse_flat,
)

_COMPANION_STATS_KEYS = (
    "hp_flat",
    "damage_flat",
    "health_pct",
    "damage_pct",
    "melee_pct",
    "ranged_pct",
    "crit_chance",
    "crit_damage",
    "health_regen",
    "lifesteal",
    "double_chance",
    "attack_speed",
    "skill_damage",
    "skill_cooldown",
    "block_chance",
)


def parse_companion_text(text: str) -> Dict[str, object]:
    tag, name = extract_tag_name(text)
    rarity, _age = normalise_tag(tag)
    out: Dict[str, object] = {
        "__name__": name,
        "__level__": extract_level(text),
        "__rarity__": rarity or "",
        "hp_flat": first_flat(text, (rf"{_FLAT_RE}\s*Health(?!\s*Regen)(?!\s*%)",)),
        "damage_flat": first_flat(text, (rf"{_FLAT_RE}\s*Damage(?!\s*%)",)),
        "substats": extract_substats(text),
    }
    out["missing_fields"] = missing_fields(out, ("__name__", "__level__", "__rarity__"))
    return out


def _empty_companion() -> Dict[str, float]:
    return {key: 0.0 for key in _COMPANION_STATS_KEYS}


def parse_companion(text: str) -> Dict[str, float]:
    """Legacy parser for pet or mount stat blocks."""
    clean = re.sub(r"\n(?![+\-\[\d])", " ", text or "")
    companion = _empty_companion()

    match = re.search(r"([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)", clean, re.IGNORECASE)
    if match:
        companion["hp_flat"] = parse_flat(match.group(1))

    match = re.search(r"([\d.]+[kmb]?)\s*Damage(?!\s*%)", clean, re.IGNORECASE)
    if match:
        companion["damage_flat"] = parse_flat(match.group(1))

    companion["crit_chance"] = extract(clean, [r"\+([\d. ]+)%\s*Critical Chance"])
    companion["crit_damage"] = extract(clean, [r"\+([\d. ]+)%\s*Critical Damage"])
    companion["health_regen"] = extract(clean, [r"\+([\d. ]+)%\s*Health Regen"])
    companion["lifesteal"] = extract(clean, [r"\+([\d. ]+)%\s*Lifesteal"])
    companion["double_chance"] = extract(clean, [r"\+([\d. ]+)%\s*Double Chance"])
    companion["attack_speed"] = extract(clean, [r"\+([\d. ]+)%\s*Attack Speed"])
    companion["skill_damage"] = extract(clean, [r"\+([\d. ]+)%\s*Skill Damage"])
    companion["skill_cooldown"] = extract(clean, [r"([+-][\d. ]+)%\s*Skill Cooldown"])
    companion["block_chance"] = extract(clean, [r"\+([\d. ]+)%\s*Block Chance"])
    companion["health_pct"] = extract(clean, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    companion["damage_pct"] = extract(clean, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    companion["melee_pct"] = extract(clean, [r"\+([\d. ]+)%\s*Melee Damage"])
    companion["ranged_pct"] = extract(clean, [r"\+([\d. ]+)%\s*Ranged Damage"])

    return companion


def parse_companion_meta(text: str) -> Dict[str, object]:
    tag, name = extract_tag_name(text or "")
    rarity, _age = normalise_tag(tag)
    level = extract_level(text or "") or None
    return {
        "name": name or None,
        "rarity": rarity.lower() if isinstance(rarity, str) else rarity,
        "level": level,
        "stats": parse_companion(text or ""),
    }


parse_pet = parse_companion
parse_mount = parse_companion


__all__ = [
    "parse_companion_text",
    "parse_companion",
    "parse_companion_meta",
    "parse_pet",
    "parse_mount",
]
