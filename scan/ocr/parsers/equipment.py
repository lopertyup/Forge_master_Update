"""OCR-only equipment popup parser."""

from __future__ import annotations

import re
from typing import Dict, Optional

from data.canonical import canonical_equipment_slot

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

_RE_ITEM_BOUNDARY = re.compile(r"(?=^\[)", re.MULTILINE)


def parse_equipment_popup_text(text: str, *, slot: str) -> Dict[str, object]:
    canonical_slot = canonical_equipment_slot(slot) or slot
    tag, name = extract_tag_name(text)
    _rarity, age = normalise_tag(tag)
    damage_match = re.search(rf"{_FLAT_RE}\s*Damage\s*(?:\(([^)]*)\))?(?!\s*%)", text or "", re.IGNORECASE)
    attack_type = ""
    if damage_match:
        suffix = damage_match.group(2) or ""
        attack_type = "ranged" if re.search("ranged", suffix, re.IGNORECASE) else ("melee" if canonical_slot == "Weapon" else "")

    out: Dict[str, object] = {
        "__name__": name,
        "__level__": extract_level(text),
        "__age__": int(age or 0),
        "__rarity__": "",
        "__idx__": 0,
        "hp_flat": first_flat(text, (rf"{_FLAT_RE}\s*Health(?!\s*Regen)(?!\s*%)",)),
        "damage_flat": first_flat(text, (rf"{_FLAT_RE}\s*Damage\s*(?:\([^)]*\))?(?!\s*%)",)),
        "substats": extract_substats(text),
        "attack_type": attack_type,
        "weapon_attack_range": 0.0,
        "weapon_windup": 0.0,
        "weapon_recovery": 0.0,
        "projectile_speed": 0.0,
        "projectile_travel_time": 0.0,
    }
    out["missing_fields"] = missing_fields(out, ("__name__", "__level__", "__age__"))
    return out


def _parse_single_equipment(text: str) -> Dict[str, Optional[float]]:
    eq: Dict[str, Optional[float]] = {key: 0.0 for key in _COMPANION_STATS_KEYS}
    eq["attack_type"] = None

    match = re.search(r"([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)", text, re.IGNORECASE)
    if match:
        eq["hp_flat"] = parse_flat(match.group(1))

    match = re.search(r"([\d.]+[kmb]?)\s*Damage(\s*\([^)]*\))?(?!\s*%)", text, re.IGNORECASE)
    if match:
        eq["damage_flat"] = parse_flat(match.group(1))
        suffix = match.group(2) or ""
        eq["attack_type"] = "ranged" if re.search("ranged", suffix, re.IGNORECASE) else "melee"

    eq["crit_chance"] = extract(text, [r"\+([\d. ]+)%\s*Critical\s*Chance"])
    eq["crit_damage"] = extract(text, [r"\+([\d. ]+)%\s*Critical\s*Damage"])
    eq["health_regen"] = extract(text, [r"\+([\d. ]+)%\s*Health\s*Regen"])
    eq["lifesteal"] = extract(text, [r"\+([\d. ]+)%\s*Lifesteal"])
    eq["double_chance"] = extract(text, [r"\+([\d. ]+)%\s*Double\s*Chance"])
    eq["attack_speed"] = extract(text, [r"\+([\d. ]+)%\s*Attack\s*Speed"])
    eq["skill_damage"] = extract(text, [r"\+([\d. ]+)%\s*Skill\s*Damage"])
    eq["skill_cooldown"] = extract(text, [r"([+-][\d. ]+)%\s*Skill\s*Cooldown"])
    eq["block_chance"] = extract(text, [r"\+([\d. ]+)%\s*Block\s*Chance"])
    eq["health_pct"] = extract(text, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    eq["damage_pct"] = extract(text, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    eq["melee_pct"] = extract(text, [r"\+([\d. ]+)%\s*Melee\s*Damage"])
    eq["ranged_pct"] = extract(text, [r"\+([\d. ]+)%\s*Ranged\s*Damage"])

    first_line = text.strip().splitlines()[0] if text.strip() else ""
    match = re.match(r"^\[\s*([A-Za-z]+)\s*\]\s*(.+?)\s*$", first_line, re.IGNORECASE)
    if match:
        eq["rarity"] = match.group(1).strip().lower()
        eq["name"] = match.group(2).strip()

    return eq


def parse_equipment(text: str) -> Dict[str, Optional[float]]:
    """Legacy parser for one or two equipment blocks."""
    blocks = [block.strip() for block in _RE_ITEM_BOUNDARY.split(text or "") if block.strip()]
    if len(blocks) == 1:
        return _parse_single_equipment(blocks[0])
    if len(blocks) >= 2:
        return {
            "equipped": _parse_single_equipment(blocks[0]),
            "candidate": _parse_single_equipment(blocks[1]),
        }
    eq: Dict[str, Optional[float]] = {key: 0.0 for key in _COMPANION_STATS_KEYS}
    eq["attack_type"] = None
    return eq


__all__ = ["parse_equipment_popup_text", "parse_equipment"]
